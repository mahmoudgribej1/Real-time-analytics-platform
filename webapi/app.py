import os, json, asyncio
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import math
from datetime import datetime

PG_DSN = os.getenv("PG_DSN", "postgresql://airflow:airflow@postgres:5432/airflow")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pool: asyncpg.Pool | None = None
clients: set[WebSocket] = set()

# ------------------------------
# Startup / shutdown
# ------------------------------
@app.on_event("startup")
async def on_start():
    global pool
    pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=5)

@app.on_event("shutdown")
async def on_stop():
    if pool:
        await pool.close()

# ------------------------------
# Health
# ------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

# ------------------------------
# Models
# ------------------------------
class NotifyIn(BaseModel):
    id: int
    created_at: str | None = None
    type: str
    severity: str
    title: str
    details: dict | str | None = None
    link: str | None = None

class EtaReq(BaseModel):
    # adapt to your model features if needed
    distance_km: float
    items_count: int
    is_raining: int
    hour_of_day: int
    city_name: str | None = None

class MuteReq(BaseModel):
    city: str
    minutes: int = 15
    user: str | None = "demo"

class SurgeReq(BaseModel):
    city: str
    multiplier: float = 2.0
    minutes: int = 15
    user: str | None = "demo"

# --- add model ---
class SimEstimateReq(BaseModel):
    city: str
    promo_factor: float = 1.0    # e.g., 1.5 for +50% demand
    outage_pct: float = 0.0      # e.g., 0.3 for 30% fewer couriers
    rain_on: bool = False
    minutes_window: int = 120

def _clamp(x, lo, hi): return max(lo, min(hi, x))

async def _avg_breaches_per_min(con, city: str, mins: int = 30) -> float:
    q = """
      SELECT COALESCE(AVG(breaches)::float, 0)
      FROM ops.sla_breaches_per_minute
      WHERE city_name=$1 AND ts >= NOW() - make_interval(mins => $2::int)
    """
    v = await con.fetchval(q, city, mins)
    return float(v or 0.0)

async def _latest_pressure_row(con, city: str, window: int):
    q = """
      SELECT ts, pressure_score, order_count, avg_delivery_time, available_couriers, demand_per_available
      FROM ops.city_pressure_minute
      WHERE city_name = $1 AND ts >= NOW() - make_interval(mins => $2::int)
      ORDER BY ts DESC
      LIMIT 1
    """
    r = await con.fetchrow(q, city, window)
    if not r:
        return None
    return dict(r)

async def _eta_typical(city: str, rain: bool) -> float:
    """
    Try MLflow ETA model; fall back to a reasonable default if not available.
    """
    try:
        import mlflow.pyfunc  # type: ignore
        import pandas as pd   # type: ignore
    except Exception:
        # fallback ~ 25 min typical
        return 25.0

    global _model
    try:
        _model  # noqa: F821
    except NameError:
        try:
            _model = mlflow.pyfunc.load_model("models:/eta_model/Production")
        except Exception:
            return 25.0

    df = pd.DataFrame([{
        "distance_km": 3.0,
        "items_count": 3,
        "is_raining": 1 if rain else 0,
        "hour_of_day": datetime.now().hour,
        "city_name": city
    }])
    try:
        y = _model.predict(df)
        return float(y[0])
    except Exception:
        return 25.0

@app.post("/api/sim/estimate")
async def sim_estimate(req: SimEstimateReq):
    async with pool.acquire() as con:
        base = await _latest_pressure_row(con, req.city, req.minutes_window)
        if not base:
            raise HTTPException(status_code=404, detail="No recent pressure metrics for city.")
        base_bpm = await _avg_breaches_per_min(con, req.city, 30)

    # Baseline values
    b_press = float(base.get("pressure_score") or 0.0)
    b_ord   = float(base.get("order_count") or 0.0)
    b_avail = float(base.get("available_couriers") or 0.0)
    b_dpa   = float(base.get("demand_per_available") or (b_ord / (b_avail or 1)))
    b_adm   = float(base.get("avg_delivery_time") or 25.0)  # minutes

    # What-if
    n_ord   = b_ord * max(0.1, req.promo_factor)
    n_avail = b_avail * (1.0 - _clamp(req.outage_pct, 0.0, 0.95))
    n_avail = max(1.0, n_avail)  # avoid div by zero
    n_dpa   = n_ord / n_avail

    # Pressure change: ~18 pts per doubling of DPA, +8 if raining
    # (18 ~= aggressive but sane; tune later)
    ratio = max(0.25, n_dpa / max(0.25, b_dpa))
    delta_from_dpa = 18.0 * (math.log(ratio, 2))
    delta_from_rain = 8.0 if req.rain_on else 0.0
    n_press = _clamp(b_press + delta_from_dpa + delta_from_rain, 0.0, 100.0)

    # Avg delivery time: scale by pressure uplift and rain penalty (~8%)
    # pressure_scale ~ 1 + 0.25 * (Δpressure/100)
    pressure_scale = 1.0 + 0.25 * ((n_press - b_press) / 100.0)
    rain_scale = 1.08 if req.rain_on else 1.0
    n_adm = max(5.0, b_adm * pressure_scale * rain_scale)

    # Breaches per minute: scale with pressure ^1.2 and small rain penalty
    base_den = max(1.0, b_press + 1.0)
    n_bpm = max(0.0, base_bpm * ((n_press + 1.0) / base_den) ** 1.2)
    if req.rain_on:
        n_bpm *= 1.05

    # Typical ETA via model (if available) + supply effect from DPA change
    eta_base = await _eta_typical(req.city, False)
    eta_rain = await _eta_typical(req.city, True) if req.rain_on else eta_base
    # supply/demand effect: +15% per +1 in DPA over baseline (capped)
    dpa_uplift = _clamp(0.15 * max(0.0, n_dpa - b_dpa), 0.0, 0.5)
    n_eta_typical = (eta_rain if req.rain_on else eta_base) * (1.0 + dpa_uplift)

    return {
        "baseline": {
            "pressure_score": round(b_press, 1),
            "order_count": round(b_ord, 1),
            "available_couriers": round(b_avail, 1),
            "demand_per_available": round(b_dpa, 3),
            "avg_delivery_time": round(b_adm, 2),
            "breaches_per_min": round(base_bpm, 3),
            "eta_typical": round(eta_base, 2)
        },
        "predicted": {
            "pressure_score": round(n_press, 1),
            "order_count": round(n_ord, 1),
            "available_couriers": round(n_avail, 1),
            "demand_per_available": round(n_dpa, 3),
            "avg_delivery_time": round(n_adm, 2),
            "breaches_per_min": round(n_bpm, 3),
            "eta_typical": round(n_eta_typical, 2)
        },
        "deltas": {
            "pressure_score": round(n_press - b_press, 1),
            "demand_per_available": round(n_dpa - b_dpa, 3),
            "avg_delivery_time": round(n_adm - b_adm, 2),
            "breaches_per_min": round(n_bpm - base_bpm, 3),
            "eta_typical": round(n_eta_typical - eta_base, 2)
        }
    }

# ------------------------------
# WebSocket client management
# ------------------------------
@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            # keep the socket alive; we don't need payload from client
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)

async def broadcast(message: dict):

    """Send a JSON message to all connected clients."""
    dead = []
    for c in clients:
        try:
            await c.send_json(message)
        except Exception:
            dead.append(c)
    for d in dead:
        clients.discard(d)

async def _broadcast(title: str, typ: str = "SCENARIO", severity: str = "info", details: dict | None = None):
    # Reuse the in-process websocket broadcaster (no HTTP hop)
    payload = {
        "id": 0,
        "type": typ,
        "severity": severity,
        "title": title,
        "details": details or {}
    }
    await broadcast(payload)

async def toast(title: str, typ: str = "PLAYBOOK", severity: str = "info", details: dict | None = None):
    """Push a notification to the UI via WS."""
    await broadcast({"id": 0, "type": typ, "severity": severity, "title": title, "details": details or {}})



# ------------------------------
# KPI / data endpoints
# ------------------------------
@app.get("/api/kpi")
async def kpi():
    async with pool.acquire() as con:
        # Orders per minute, last 60s
        opm = await con.fetchval("""
            SELECT COALESCE(SUM(order_count), 0)
            FROM city_orders_per_minute
            WHERE window_end >= NOW() - INTERVAL '60 seconds'
        """)

        # SLA today
        sla = await con.fetchval("""
            SELECT COUNT(*)
            FROM sla_violations
            WHERE created_at >= date_trunc('day', NOW())
        """)

        # ETA MAE (1h) -- handle both with/without created_at
        has_created = await con.fetchval("""
            SELECT EXISTS (
              SELECT 1
              FROM information_schema.columns
              WHERE table_schema = 'public'
                AND table_name = 'eta_model_performance'
                AND column_name = 'created_at'
            )
        """)
        if has_created:
            mae = await con.fetchval("""
                SELECT COALESCE(ROUND(AVG(ABS(absolute_error))::numeric, 2), 0)
                FROM eta_model_performance
                WHERE created_at >= NOW() - INTERVAL '1 hour'
            """)
        else:
            mae = await con.fetchval("""
                SELECT COALESCE(ROUND(AVG(ABS(absolute_error))::numeric, 2), 0)
                FROM eta_model_performance
            """)

    return {
        "orders_per_min": int(opm or 0),
        "sla_today": int(sla or 0),
        "eta_mae_1h": float(mae or 0.0)
    }

@app.get("/api/sla")
async def api_sla(limit: int = 50):
    async with pool.acquire() as con:
        rows = await con.fetch("""
            SELECT order_id, city_name, delivery_person_id, courier_name, delay_minutes, created_at
            FROM sla_violations
            ORDER BY order_id DESC
            LIMIT $1
        """, limit)
    return [dict(r) for r in rows]

@app.get("/api/city_demand")
async def city_demand(minutes: int = 60):
    # use make_interval to accept numeric minutes
    async with pool.acquire() as con:
        rows = await con.fetch("""
          SELECT window_start AS ts, city_name, order_count, avg_delivery_time, window_end
          FROM city_orders_per_minute
          WHERE window_end >= NOW() - make_interval(mins => $1::int)
          ORDER BY ts ASC
        """, minutes)
    return [dict(r) for r in rows]

# Notifier posts here; relay to clients
@app.post("/api/notify")
async def notify(evt: NotifyIn):
    await broadcast(evt.model_dump())
    return JSONResponse({"ok": True})

# ------------------------------
# ETA prediction (lazy MLflow import so API starts even if MLflow not installed)
# ------------------------------
@app.post("/api/eta/predict")
async def eta_predict(req: EtaReq):
    try:
        import mlflow.pyfunc  # type: ignore
        import pandas as pd   # type: ignore
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MLflow not available: {e}")

    global _model
    try:
        _model  # noqa: F821
    except NameError:
        _model = mlflow.pyfunc.load_model("models:/eta_model/Production")  # adjust if needed

    df = pd.DataFrame([req.model_dump()])
    y = _model.predict(df)
    return {"predicted_minutes": float(y[0])}

# ------------------------------
# Actions + audit
# ------------------------------
@app.get("/api/actions/mutes")
async def list_mutes():
    async with pool.acquire() as con:
        rows = await con.fetch("""
            SELECT city_name, until
            FROM ops.alert_mutes
            WHERE until > NOW()
            ORDER BY until DESC
        """)
    return [{"city_name": r["city_name"], "until": r["until"].isoformat()} for r in rows]

@app.get("/api/actions/log")
async def actions_log(limit: int = 50):
    async with pool.acquire() as con:
        rows = await con.fetch("""
            SELECT ts, action, user_name, params, result
            FROM ops.actions_log
            ORDER BY ts DESC
            LIMIT $1
        """, limit)
    return [
        {
            "ts": r["ts"].isoformat(),
            "action": r["action"],
            "user_name": r["user_name"],
            "params": r["params"],
            "result": r["result"],
        } for r in rows
    ]

@app.post("/api/actions/mute_city")
async def mute_city(req: MuteReq):
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO ops.alert_mutes(city_name, until) "
            "VALUES ($1, NOW() + make_interval(mins => $2::int)) "
            "ON CONFLICT (city_name) DO UPDATE SET until = EXCLUDED.until",
            req.city, req.minutes
        )
        await con.execute(
            "INSERT INTO ops.actions_log(action, params, user_name, result) "
            "VALUES($1,$2::jsonb,$3,$4)",
            "mute_city", json.dumps(req.model_dump()), req.user, "ok"
        )
    msg = f"Muted {req.city} alerts for {req.minutes}m"
    await toast(msg)
    return {"ok": True, "message": msg}

@app.post("/api/actions/unmute_city")
async def unmute_city(req: MuteReq):
    async with pool.acquire() as con:
        await con.execute("DELETE FROM ops.alert_mutes WHERE city_name=$1", req.city)
        await con.execute(
            "INSERT INTO ops.actions_log(action, params, user_name, result) "
            "VALUES($1,$2::jsonb,$3,$4)",
            "unmute_city", json.dumps(req.model_dump()), req.user, "ok"
        )
    msg = f"Unmuted {req.city}"
    await toast(msg)
    return {"ok": True, "message": msg}

@app.post("/api/actions/trigger_surge")
async def trigger_surge(req: SurgeReq):
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO ops.surge_overrides(city_name, multiplier, until) "
            "VALUES ($1,$2, NOW() + make_interval(mins => $3::int)) "
            "ON CONFLICT (city_name) DO UPDATE SET multiplier=EXCLUDED.multiplier, until=EXCLUDED.until",
            req.city, req.multiplier, req.minutes
        )
        await con.execute(
            "INSERT INTO ops.actions_log(action, params, user_name, result) "
            "VALUES($1,$2::jsonb,$3,$4)",
            "trigger_surge", json.dumps(req.model_dump()), req.user, "recorded"
        )
    msg = f"Surge set for {req.city}: x{req.multiplier} for {req.minutes}m"
    await toast(msg)
    return {"ok": True, "message": msg}

# -------- Pressure endpoints --------
@app.get("/api/pressure/top")
async def pressure_top(minutes: int = 10, limit: int = 8):
    q = """
    WITH latest AS (
      SELECT DISTINCT ON (city_name)
             city_name, ts, pressure_score, order_count, avg_delivery_time, available_couriers, demand_per_available
      FROM ops.city_pressure_minute
      WHERE ts >= NOW() - make_interval(mins => $1::int)
      ORDER BY city_name, ts DESC
    )
    SELECT *
    FROM latest
    ORDER BY pressure_score DESC NULLS LAST
    LIMIT $2
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, minutes, limit)
    return [dict(r) for r in rows]

@app.get("/api/pressure/series")
async def pressure_series(city: str, minutes: int = 120):
    q = """
    SELECT ts, pressure_score, order_count, avg_delivery_time, available_couriers, demand_per_available
    FROM ops.city_pressure_minute
    WHERE city_name = $1 AND ts >= NOW() - make_interval(mins => $2::int)
    ORDER BY ts
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, city, minutes)
    return [dict(r) for r in rows]

# -------- Recommendations (rule-based for now) --------
def _reason_for_surge(row: dict) -> str:
    parts = []
    if (row.get("available_couriers") or 0) <= 1: parts.append("low supply")
    if (row.get("order_count") or 0) >= 50: parts.append("high demand")
    if (row.get("demand_per_available") or 0) >= 2: parts.append("overloaded couriers")
    return ", ".join(parts) or "elevated pressure"

@app.get("/api/recommendations/list")
async def recommendations_list(minutes: int = 10):
    # Compute suggestions on the fly from latest pressure
    q = """
    WITH latest AS (
      SELECT DISTINCT ON (city_name)
             city_name, ts, pressure_score, order_count, avg_delivery_time, available_couriers, demand_per_available
      FROM ops.city_pressure_minute
      WHERE ts >= NOW() - make_interval(mins => $1::int)
      ORDER BY city_name, ts DESC
    )
    SELECT *
    FROM latest
    WHERE pressure_score >= 75
    ORDER BY pressure_score DESC
    """
    async with pool.acquire() as con:
        rows = [dict(r) for r in await con.fetch(q, minutes)]
    # Build surge suggestions
    recs = []
    for r in rows:
        mult = 1.5 if r["pressure_score"] < 85 else 2.0
        recs.append({
            "city_name": r["city_name"],
            "kind": "SURGE_CITY",
            "score": float(r["pressure_score"]),
            "rationale": _reason_for_surge(r),
            "suggested_params": {"multiplier": mult, "minutes": 15}
        })
    return recs

class RecAction(BaseModel):
    city_name: str
    kind: str
    score: float
    suggested_params: dict
    user: str | None = "demo"

@app.post("/api/recommendations/approve")
async def recommendations_approve(rec: RecAction):
    if rec.kind == "SURGE_CITY":
        minutes = int(rec.suggested_params.get("minutes", 15))
        mult    = float(rec.suggested_params.get("multiplier", 1.5))
        # record recommendation as approved
        async with pool.acquire() as con:
            await con.execute("""
              INSERT INTO ops.recommendations(city_name, kind, score, rationale, suggested_params, status, decided_at, decided_by)
              VALUES ($1,$2,$3,$4,$5::jsonb,'approved', NOW(), $6)
            """, rec.city_name, rec.kind, rec.score, "approved via UI",
                              json.dumps(rec.suggested_params), rec.user)
        # trigger surge using your existing action
        # (reuse existing endpoint logic by calling into DB directly then toast)
        await mute_or_surge("SURGE", rec.city_name, minutes, mult)
        return {"ok": True}

    # other kinds can be added later (THROTTLE_RESTAURANT, PRIORITIZE_ORDERS)
    return {"ok": False, "message": "Unknown recommendation kind"}

@app.post("/api/recommendations/dismiss")
async def recommendations_dismiss(rec: RecAction):
    async with pool.acquire() as con:
        await con.execute("""
          INSERT INTO ops.recommendations(city_name, kind, score, rationale, suggested_params, status, decided_at, decided_by)
          VALUES ($1,$2,$3,$4,$5::jsonb,'dismissed', NOW(), $6)
        """, rec.city_name, rec.kind, rec.score, "dismissed via UI",
                          json.dumps(rec.suggested_params), rec.user)
    # toast so the room sees it
    await toast(f"Dismissed {rec.kind} for {rec.city_name}")
    return {"ok": True}

# helper used by approve (keeps same toast style as your actions)
async def mute_or_surge(kind: str, city: str, minutes: int, mult: float):
    if kind == "SURGE":
        async with pool.acquire() as con:
            await con.execute(
                "INSERT INTO ops.surge_overrides(city_name, multiplier, until) "
                "VALUES ($1,$2, NOW() + make_interval(mins => $3::int)) "
                "ON CONFLICT (city_name) DO UPDATE SET multiplier=EXCLUDED.multiplier, until=EXCLUDED.until",
                city, mult, minutes
            )
            await con.execute(
                "INSERT INTO ops.actions_log(action, params, user_name, result) VALUES($1,$2::jsonb,$3,$4)",
                "trigger_surge",
                json.dumps({"city":city,"multiplier":mult,"minutes":minutes}),
                "demo",
                "recorded"
            )
        await toast(f"Surge set for {city}: x{mult} for {minutes}m")

# -------- Incident Replay --------
@app.get("/api/replay")
async def replay(city: str, minutes: int = 120):
    async with pool.acquire() as con:
        pres = await con.fetch("""
          SELECT ts, pressure_score FROM ops.city_pressure_minute
          WHERE city_name = $1 AND ts >= NOW() - make_interval(mins => $2::int)
          ORDER BY ts
        """, city, minutes)
        br = await con.fetch("""
          SELECT ts, SUM(breaches)::int AS breaches
          FROM ops.sla_breaches_per_minute
          WHERE city_name=$1 AND ts >= NOW() - make_interval(mins => $2::int)
          GROUP BY ts ORDER BY ts
        """, city, minutes)
        acts = await con.fetch("""
          SELECT ts, action, params, result
          FROM ops.actions_log
          WHERE ts >= NOW() - make_interval(mins => $1::int)
            AND ( (params->>'city') = $2 OR action IN ('mute_city','unmute_city','trigger_surge') )
          ORDER BY ts
        """, minutes, city)
    return {
        "pressure": [dict(r) for r in pres],
        "breaches": [dict(r) for r in br],
        "actions":  [ {"ts":r["ts"].isoformat(),"action":r["action"],"params":r["params"],"result":r["result"]} for r in acts ]
    }

class RainReq(BaseModel):
    city: str           # 'Tunis' or '6'
    on: bool = True
    minutes: int = 30
    user: str | None = "demo"

class PromoReq(BaseModel):
    city: str
    factor: float = 1.5
    minutes: int = 20
    user: str | None = "demo"

class OutageReq(BaseModel):
    city: str
    pct_offline: float = 0.3
    minutes: int = 10
    user: str | None = "demo"

@app.get("/api/sim/list")
async def sim_list():
    async with pool.acquire() as con:
        rows = await con.fetch(
            "SELECT key, city_name, params, until FROM ops.simulation_flags WHERE until > NOW() ORDER BY until DESC")
    return [dict(r) for r in rows]

@app.post("/api/sim/rain")
async def sim_rain(req: RainReq):
    async with pool.acquire() as con:
        await con.execute("""
          INSERT INTO ops.simulation_flags(key, city_name, params, until)
          VALUES ('rain',$1,$2::jsonb, NOW() + ($3::int) * INTERVAL '1 minute')
          ON CONFLICT (key, city_name) DO UPDATE
            SET params=EXCLUDED.params, until=EXCLUDED.until
        """, req.city, json.dumps({"on": req.on}), req.minutes)
        await con.execute(
            "INSERT INTO ops.actions_log(action, params, user_name, result) VALUES($1,$2::jsonb,$3,$4)",
            "sim_rain", json.dumps(req.model_dump()), req.user, "recorded"
        )
    await _broadcast(f"{'Started' if req.on else 'Stopped'} rain in {req.city} for {req.minutes}m")
    return {"ok": True}

@app.post("/api/sim/promo")
async def sim_promo(req: PromoReq):
    async with pool.acquire() as con:
        await con.execute("""
          INSERT INTO ops.simulation_flags(key, city_name, params, until)
          VALUES ('promo',$1,$2::jsonb, NOW() + ($3::int) * INTERVAL '1 minute')
          ON CONFLICT (key, city_name) DO UPDATE
            SET params=EXCLUDED.params, until=EXCLUDED.until
        """, req.city, json.dumps({"factor": req.factor}), req.minutes)
        await con.execute(
            "INSERT INTO ops.actions_log(action, params, user_name, result) VALUES($1,$2::jsonb,$3,$4)",
            "sim_promo", json.dumps(req.model_dump()), req.user, "recorded"
        )
    await _broadcast(f"Promo in {req.city}: x{req.factor} for {req.minutes}m")
    return {"ok": True}

@app.post("/api/sim/outage")
async def sim_outage(req: OutageReq):
    async with pool.acquire() as con:
        await con.execute("""
          INSERT INTO ops.simulation_flags(key, city_name, params, until)
          VALUES ('courier_outage',$1,$2::jsonb, NOW() + ($3::int) * INTERVAL '1 minute')
          ON CONFLICT (key, city_name) DO UPDATE
            SET params=EXCLUDED.params, until=EXCLUDED.until
        """, req.city, json.dumps({"pct_offline": req.pct_offline}), req.minutes)
        await con.execute(
            "INSERT INTO ops.actions_log(action, params, user_name, result) VALUES($1,$2::jsonb,$3,$4)",
            "sim_outage", json.dumps(req.model_dump()), req.user, "recorded"
        )
    await _broadcast(f"Courier outage in {req.city}: {int(req.pct_offline*100)}% for {req.minutes}m")
    return {"ok": True}

@app.get("/api/sentiment")
async def api_sentiment(minutes: int = 60):
    async with pool.acquire() as con:
        rows = await con.fetch("""
            WITH src AS (
              SELECT
                c.city_name,
                orv.posted_at,
                orv.rating,
                orv.sentiment
              FROM order_reviews      AS orv
              JOIN orders             AS o  ON o.order_id      = orv.order_id
              JOIN restaurants        AS r  ON r.restaurant_id = o.restaurant_id
              JOIN cities             AS c  ON c.city_id       = r.city_id
              WHERE orv.posted_at >= (NOW()::timestamp - ($1::int * interval '1 minute'))
            )
            SELECT
              city_name,
              COUNT(*)                                           AS reviews,
              ROUND(AVG(rating)::numeric, 2)                     AS avg_rating,
              SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) AS pos,
              SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) AS neg
            FROM src
            GROUP BY city_name
            ORDER BY reviews DESC
        """, minutes)
    return [dict(r) for r in rows]

@app.get("/api/revenue/kpis")
async def revenue_kpis(minutes: int = 60):
    async with pool.acquire() as con:
        # Completion timestamp = COALESCE(pickup_time, order_timestamp) + time_taken_minutes
        gmv_window = await con.fetchval("""
          SELECT COALESCE(SUM(total_price),0)
          FROM orders
          WHERE status='Completed'
            AND (COALESCE(pickup_time, order_timestamp)
                 + (COALESCE(time_taken_minutes,0) || ' minutes')::interval)
                >= (NOW() - ($1::int * interval '1 minute'))
        """, minutes)

        orders_window = await con.fetchval("""
          SELECT COUNT(*) FROM orders
          WHERE status='Completed'
            AND (COALESCE(pickup_time, order_timestamp)
                 + (COALESCE(time_taken_minutes,0) || ' minutes')::interval)
                >= (NOW() - ($1::int * interval '1 minute'))
        """, minutes)

        aov_window = (gmv_window / orders_window) if orders_window else 0.0

        gmv_today = await con.fetchval("""
          SELECT COALESCE(SUM(total_price),0)
          FROM orders
          WHERE status='Completed'
            AND order_timestamp >= date_trunc('day', NOW())
        """)
        orders_today = await con.fetchval("""
          SELECT COUNT(*) FROM orders
          WHERE status='Completed'
            AND order_timestamp >= date_trunc('day', NOW())
        """)

    return {
        "gmv_window": float(gmv_window or 0),
        "orders_window": int(orders_window or 0),
        "aov_window": float(aov_window or 0),
        "gmv_today": float(gmv_today or 0),
        "orders_today": int(orders_today or 0),
    }

@app.get("/api/revenue/by_city")
async def revenue_by_city(minutes: int = 60):
    async with pool.acquire() as con:
        rows = await con.fetch("""
          SELECT c.city_name,
                 COALESCE(SUM(o.total_price),0)::float AS gmv,
                 COUNT(*) AS orders,
                 (CASE WHEN COUNT(*)>0 THEN AVG(o.total_price)::float ELSE 0 END) AS aov
          FROM orders o
          JOIN cities c ON c.city_id = o.city_id
          WHERE o.status='Completed'
            AND (COALESCE(o.pickup_time, o.order_timestamp)
                 + (COALESCE(o.time_taken_minutes,0) || ' minutes')::interval)
                >= (NOW() - ($1::int * interval '1 minute'))
          GROUP BY c.city_name
          ORDER BY gmv DESC
        """, minutes)
    return [dict(r) for r in rows]

