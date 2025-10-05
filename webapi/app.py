import os, json, asyncio, math, time
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
from aiokafka import AIOKafkaProducer
from fastapi import Query
from typing import Optional
from fastapi import Body

from contextlib import suppress
from aiokafka import AIOKafkaConsumer

_producer: Optional[AIOKafkaProducer] = None
# Optional JWT auth (dev-friendly: allow if secret not set)
try:
    import jwt  # pyjwt
except Exception:
    jwt = None

JWT_SECRET = os.getenv("JWT_SECRET")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
COURIER_TOPIC   = os.getenv("COURIER_FEATURES_TOPIC", "courier_features_live")
USE_FLINK_SINKS = os.getenv("USE_FLINK_SINKS", "false").lower() in ("1","true","yes")



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

async def _consume_courier_features():
    consumer = AIOKafkaConsumer(
        COURIER_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="webapi-courier-ui-upserter",
        enable_auto_commit=True,
        auto_offset_reset="latest",
        key_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
    )
    await consumer.start()
    try:
        batch, last = [], 0.0
        async for msg in consumer:
            key = msg.key or {}
            val = msg.value or {}
            courier_id = key.get("delivery_person_id") or val.get("delivery_person_id")
            if not courier_id:
                continue
            payload = {
                "report_timestamp": val.get("report_timestamp"),
                "active_deliveries_count": val.get("active_deliveries_count"),
                "avg_delivery_speed_today": val.get("avg_delivery_speed_today"),
            }
            batch.append((int(courier_id), json.dumps(payload)))
            now = asyncio.get_event_loop().time()
            if len(batch) >= 200 or now - last > 1.0:
                async with pool.acquire() as con:
                    await con.executemany(
                        """
                        INSERT INTO ops.courier_activity_ui (delivery_person_id, payload, last_update)
                        VALUES ($1, $2::jsonb, NOW())
                        ON CONFLICT (delivery_person_id)
                        DO UPDATE SET payload = EXCLUDED.payload, last_update = NOW();
                        """,
                        batch,
                    )
                batch, last = [], now
    finally:
        await consumer.stop()


# --- utility to choose a live source table -----------------------------------
async def _pick_table(con, candidates: list[str], minutes: int = 240) -> str:
    """
    Return the first table/view name from `candidates` that has at least 1 row
    in the last `minutes`. Falls back to the last candidate if none match.
    """
    for name in candidates:
        try:
            cnt = await con.fetchval(
                f"SELECT COUNT(*) FROM {name} WHERE ts >= NOW() - make_interval(mins => $1::int)",
                minutes
            )
            if cnt and int(cnt) > 0:
                return name
        except Exception:
            # table/view may not exist; try the next one
            continue
    return candidates[-1]

# ------------------------------
# Startup / shutdown
# ------------------------------
@app.on_event("startup")
async def on_start():
    global pool, _producer
    pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=5)
    try:
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda d: json.dumps(d).encode("utf-8")
        )
        await _producer.start()
    except Exception:
        _producer = None  # optional
    # >>> ADDED: launch the Kafka -> Postgres upserter as a background task
    app.state._courier_consumer = asyncio.create_task(_consume_courier_features())
    print("[courier-consumer] started", flush=True)

@app.on_event("shutdown")
async def on_stop():
    # >>> ADDED: cancel the background consumer cleanly
    t = getattr(app.state, "_courier_consumer", None)
    if t:
        t.cancel()
        from contextlib import suppress
        import asyncio
        with suppress(asyncio.CancelledError):
            await t
        print("[courier-consumer] stopped", flush=True)

    if pool: await pool.close()
    if _producer:
        try: await _producer.stop()
        except Exception: pass


# ------------------------------
# Health
# ------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

# ------------------------------
# Models
# ------------------------------
class NotifyCompat(BaseModel):
    # legacy shape (from notifier)
    id: int = 0
    created_at: Optional[str] = None
    type: str
    severity: str = "info"
    title: str
    details: Optional[Any] = None
    link: Optional[str] = None
    city: Optional[str] = None


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

class MessageV1(BaseModel):
    type: str = Field(..., description="event type, e.g., 'sla_violation', 'sentiment_update'")
    title: str
    severity: str = "info"  # info|warning|critical
    city: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

def _allow_dev() -> bool:
    return not JWT_SECRET  # if no secret, allow all

def verify_jwt_or_allow(token: Optional[str]) -> None:
    if _allow_dev():
        return
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    if not jwt:
        raise HTTPException(status_code=500, detail="JWT not available on server")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

async def require_bearer(authorization: Optional[str] = Header(None)):
    if _allow_dev():
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1]
    verify_jwt_or_allow(token)


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
async def ws(ws: WebSocket, token: Optional[str] = Query(default=None)):
    # optional auth
    try:
        verify_jwt_or_allow(token)
    except HTTPException:
        await ws.close(code=4401)  # policy violation
        return
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await asyncio.sleep(30)  # keepalive
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
            "eta_mae_1h": float(mae or 0.0),
            "window_ms": 60000,
            "calculated_at": datetime.utcnow().isoformat()+"Z"
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
async def notify(evt: Dict[str, Any], _auth=Depends(require_bearer)):
    """
    Accept either MessageV1 or the legacy NotifyCompat and broadcast MessageV1.
    """
    try:
        # First try V1
        v1 = MessageV1(**evt)
    except Exception:
        # Try compat and convert
        c = NotifyCompat(**evt)
        v1 = MessageV1(type=c.type, title=c.title, severity=c.severity,
                       city=c.city, payload=c.details if isinstance(c.details, dict) else {"details": c.details})
    await broadcast(v1.model_dump())
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
    async with pool.acquire() as con:
        src = await _pick_table(
            con,
            ["ops.city_pressure_minute_mv", "ops.city_pressure_minute"],
            minutes
        )
        rows = await con.fetch(f"""
            WITH latest AS (
              SELECT DISTINCT ON (city_name)
                     city_name, ts,
                     pressure_score, order_count, avg_delivery_time,
                     available_couriers, demand_per_available
              FROM {src}
              WHERE ts >= NOW() - make_interval(mins => $1::int)
              ORDER BY city_name, ts DESC
            )
            SELECT *
            FROM latest
            ORDER BY COALESCE(pressure_score,0) DESC NULLS LAST
            LIMIT $2
        """, minutes, limit)
    return [dict(r) for r in rows]


@app.get("/api/pressure/series")
async def pressure_series(city: str, minutes: int = 120):
    async with pool.acquire() as con:
        src = await _pick_table(
            con,
            ["ops.city_pressure_minute_mv", "ops.city_pressure_minute"],
            minutes
        )
        rows = await con.fetch(f"""
            SELECT ts,
                   pressure_score, order_count, avg_delivery_time,
                   available_couriers, demand_per_available
            FROM {src}
            WHERE city_name = $1
              AND ts >= NOW() - make_interval(mins => $2::int)
            ORDER BY ts
        """, city, minutes)
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
async def publish_decision(topic: str, payload: dict):
    if _producer:
        await _producer.send_and_wait(topic, payload)

async def recommendations_approve(rec: RecAction):
    if rec.kind == "SURGE_CITY":
        minutes = int(rec.suggested_params.get("minutes", 15))
        mult    = float(rec.suggested_params.get("multiplier", 1.5))
        # record recommendation as approved
        async with pool.acquire() as con:
            await con.execute("""
              INSERT INTO ops.recommendations(city_name, kind, score, rationale, suggested_params, status, decided_at, decided_by)
              VALUES ($1,$2,$3,$4,$5::jsonb,'approved', NOW(), $6)
            """, rec.city_name, rec.kind, rec.score, "approved via UI",json.dumps(rec.suggested_params), rec.user)
            await publish_decision("ops.decisions", {
                "kind": "SURGE_CITY",
                "city": rec.city_name,
                "multiplier": float(rec.suggested_params.get("multiplier", 1.5)),
                "minutes": int(rec.suggested_params.get("minutes", 15)),
                "decided_by": rec.user or "demo",
                "ts": time.time()
            })
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
        pressure_src = await _pick_table(
            con,
            ["ops.city_pressure_minute_mv", "ops.city_pressure_minute"],
            minutes
        )
        breaches_src = await _pick_table(
            con,
            ["ops.sla_breaches_per_minute_mv", "ops.sla_breaches_per_minute"],
            minutes
        )

        pres = await con.fetch(
            f"""SELECT ts, pressure_score
                FROM {pressure_src}
                WHERE city_name = $1
                  AND ts >= NOW() - make_interval(mins => $2::int)
                ORDER BY ts""",
            city, minutes
        )

        br = await con.fetch(
            f"""SELECT ts, SUM(breaches)::int AS breaches
                FROM {breaches_src}
                WHERE city_name = $1
                  AND ts >= NOW() - make_interval(mins => $2::int)
                GROUP BY ts
                ORDER BY ts""",
            city, minutes
        )

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
        "actions":  [{"ts": r["ts"].isoformat(),
                      "action": r["action"],
                      "params": r["params"],
                      "result": r["result"]} for r in acts]
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
async def api_sentiment(minutes: int = 60, kind: str = "restaurant"):
    """
    Sentiment by entity:
      - kind=restaurant -> per restaurant (with city)
      - kind=courier    -> per courier (with city)
    Returns: [{entity_id, entity_name, city_name, reviews, avg_rating, pos, neg}, ...]
    """
    kind = (kind or "restaurant").lower()

    async def table_exists(con, table_name: str) -> bool:
        return await con.fetchval("""
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_schema='public' AND table_name=$1
            )
        """, table_name)

    async with pool.acquire() as con:
        use_flink = USE_FLINK_SINKS
        if use_flink:
            # Only use sinks if they actually exist
            if kind == "restaurant":
                use_flink = await table_exists(con, "restaurant_live_sentiment")
            else:
                use_flink = await table_exists(con, "courier_live_sentiment")

        if use_flink and kind == "restaurant":
            # --- FLINK SINK: restaurant_live_sentiment (5-min windows), roll up over N minutes
            rows = await con.fetch("""
                SELECT
                  r.restaurant_id                                              AS entity_id,
                  COALESCE(r.name, 'Restaurant ' || r.restaurant_id::text)     AS entity_name,
                  c.city_name,
                  SUM(rs.review_count)::bigint                                 AS reviews,
                  ROUND((
                    SUM(rs.avg_rating * rs.review_count)
                    / NULLIF(SUM(rs.review_count), 0)
                  )::numeric, 2)                                               AS avg_rating,
                  SUM(rs.pos_reviews)::bigint                                  AS pos,
                  SUM(rs.neg_reviews)::bigint                                  AS neg
                FROM restaurant_live_sentiment rs
                JOIN restaurants r ON r.restaurant_id = rs.restaurant_id
                JOIN cities      c ON c.city_id       = r.city_id
                WHERE rs.window_end >= NOW() - ($1::int) * INTERVAL '1 minute'
                GROUP BY r.restaurant_id, entity_name, c.city_name
                ORDER BY reviews DESC
            """, minutes)

        elif use_flink and kind == "courier":
            # --- FLINK SINK: courier_live_sentiment (5-min windows), roll up over N minutes
            rows = await con.fetch("""
                SELECT
                  dp.delivery_person_id                                         AS entity_id,
                  COALESCE(dp.name, 'Courier ' || dp.delivery_person_id::text)  AS entity_name,
                  c.city_name,
                  SUM(cls.review_count)::bigint                                 AS reviews,
                  ROUND((
                    SUM(cls.avg_rating * cls.review_count)
                    / NULLIF(SUM(cls.review_count), 0)
                  )::numeric, 2)                                               AS avg_rating,
                  SUM(cls.pos_reviews)::bigint                                  AS pos,
                  SUM(cls.neg_reviews)::bigint                                  AS neg
                FROM courier_live_sentiment cls
                JOIN delivery_personnel dp ON dp.delivery_person_id = cls.delivery_person_id
                JOIN cities            c  ON c.city_id             = dp.city_id
                WHERE cls.window_end >= NOW() - ($1::int) * INTERVAL '1 minute'
                GROUP BY dp.delivery_person_id, entity_name, c.city_name
                ORDER BY reviews DESC
            """, minutes)

        elif kind == "courier":
            # --- FALLBACK (no sinks): join source tables by courier
            rows = await con.fetch("""
                WITH src AS (
                  SELECT
                    dp.delivery_person_id                                        AS entity_id,
                    COALESCE(dp.name, 'Courier ' || dp.delivery_person_id::text) AS entity_name,
                    c.city_name,
                    orv.rating,
                    orv.sentiment
                  FROM order_reviews      AS orv
                  JOIN orders             AS o  ON o.order_id            = orv.order_id
                  JOIN delivery_personnel AS dp ON dp.delivery_person_id = o.delivery_person_id
                  JOIN cities             AS c  ON c.city_id             = dp.city_id
                  WHERE orv.posted_at >= NOW() - ($1::int) * INTERVAL '1 minute'
                )
                SELECT
                  entity_id,
                  entity_name,
                  city_name,
                  COUNT(*)                                           AS reviews,
                  ROUND(AVG(rating)::numeric, 2)                     AS avg_rating,
                  SUM(CASE WHEN sentiment='positive' THEN 1 ELSE 0 END) AS pos,
                  SUM(CASE WHEN sentiment='negative' THEN 1 ELSE 0 END) AS neg
                FROM src
                GROUP BY entity_id, entity_name, city_name
                ORDER BY reviews DESC
            """, minutes)

        else:
            # --- FALLBACK (no sinks): join source tables by restaurant
            rows = await con.fetch("""
                WITH src AS (
                  SELECT
                    r.restaurant_id                                             AS entity_id,
                    COALESCE(r.name, 'Restaurant ' || r.restaurant_id::text)    AS entity_name,
                    c.city_name,
                    orv.rating,
                    orv.sentiment
                  FROM order_reviews AS orv
                  JOIN orders        AS o ON o.order_id      = orv.order_id
                  JOIN restaurants   AS r ON r.restaurant_id = o.restaurant_id
                  JOIN cities        AS c ON c.city_id       = r.city_id
                  WHERE orv.posted_at >= NOW() - ($1::int) * INTERVAL '1 minute'
                )
                SELECT
                  entity_id,
                  entity_name,
                  city_name,
                  COUNT(*)                                           AS reviews,
                  ROUND(AVG(rating)::numeric, 2)                     AS avg_rating,
                  SUM(CASE WHEN sentiment='positive' THEN 1 ELSE 0 END) AS pos,
                  SUM(CASE WHEN sentiment='negative' THEN 1 ELSE 0 END) AS neg
                FROM src
                GROUP BY entity_id, entity_name, city_name
                ORDER BY reviews DESC
            """, minutes)

    return [dict(r) for r in rows]




@app.get("/api/revenue/kpis")
async def revenue_kpis(minutes: int = 60):
    window_end = datetime.utcnow()
    window_start = window_end - timedelta(minutes=minutes)
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
        "window_start": window_start.isoformat()+"Z",
        "window_end": window_end.isoformat()+"Z",
    }

@app.get("/api/revenue/by_city")
async def revenue_by_city(minutes: int = 60):
    window_end = datetime.utcnow()
    window_start = window_end - timedelta(minutes=minutes)
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
    return {
        "window_start": window_start.isoformat()+"Z",
        "window_end": window_end.isoformat()+"Z",
        "rows": [dict(r) for r in rows]
    }

@app.get("/health/ready")
async def ready():
    try:
        async with pool.acquire() as con:
            await con.fetchval("SELECT 1")
    except Exception as e:
        raise HTTPException(503, f"DB not ready: {e}")
    return {"status": "ready"}


# webapi/app.py
@app.get("/api/orders/live")
async def orders_live(limit: int = 30, cancel_window_min: int = 15):
    q = """
    WITH shaped AS (
      SELECT
        o.order_id,
        c.city_name,
        r.name AS restaurant_name,

        -- Treat Processing as Delivering after pickup_time passes
        CASE
          WHEN o.status = 'Processing'
           AND o.pickup_time IS NOT NULL
           AND NOW() >= o.pickup_time
          THEN 'Delivering'
          ELSE o.status
        END AS status,

        o.total_price::float                       AS price,
        o.order_timestamp,
        COALESCE(o.pickup_time, o.order_timestamp) AS started_at,
        o.time_taken_minutes,

        -- Planned end when we know both pieces
        CASE
          WHEN o.time_taken_minutes IS NOT NULL AND o.pickup_time IS NOT NULL
          THEN o.pickup_time + (o.time_taken_minutes || ' minutes')::interval
          ELSE NULL
        END AS planned_end,

        -- Elapsed minutes: for Cancelled use order_timestamp (pickup_time may be in the future)
        CASE
          WHEN o.status = 'Cancelled'
          THEN GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - o.order_timestamp)) / 60))::int
          ELSE GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - COALESCE(o.pickup_time, o.order_timestamp))) / 60))::int
        END AS elapsed_min,

        -- ETA remaining for live rows when we have a planned end
        CASE
          WHEN o.time_taken_minutes IS NOT NULL
           AND o.pickup_time IS NOT NULL
          THEN GREATEST(
                 0,
                 CEIL(EXTRACT(EPOCH FROM ((o.pickup_time + (o.time_taken_minutes||' minutes')::interval) - NOW())) / 60)
               )::int
          ELSE NULL
        END AS eta_min,

        -- live flag
        CASE WHEN o.status = 'Processing'
                  OR (o.status = 'Processing' AND o.pickup_time IS NOT NULL AND NOW() >= o.pickup_time)
             THEN TRUE ELSE FALSE END AS is_live,

        -- activity ts for sorting
        GREATEST(
          -- for cancels: order start
          CASE WHEN o.status='Cancelled' THEN o.order_timestamp ELSE COALESCE(o.pickup_time, o.order_timestamp) END,
          -- if we have a planned end, it might be the latest activity for live
          COALESCE(
            CASE
              WHEN o.time_taken_minutes IS NOT NULL AND o.pickup_time IS NOT NULL
              THEN o.pickup_time + (o.time_taken_minutes||' minutes')::interval
              ELSE NULL
            END,
            COALESCE(o.pickup_time, o.order_timestamp)
          )
        ) AS activity_ts

      FROM orders o
      LEFT JOIN restaurants r ON r.restaurant_id = o.restaurant_id
      LEFT JOIN cities      c ON c.city_id      = o.city_id
      WHERE o.order_timestamp >= NOW() - INTERVAL '12 hours'
        AND (
          o.status = 'Processing'
          OR (o.status = 'Cancelled'
              AND o.order_timestamp >= NOW() - ($2::int || ' minutes')::interval)
        )
    )
    SELECT
      order_id, city_name, restaurant_name, status, price,
      order_timestamp, started_at,
      elapsed_min, eta_min, is_live
    FROM shaped
    ORDER BY is_live DESC, activity_ts DESC
    LIMIT $1;
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, limit, cancel_window_min)
    return [dict(r) for r in rows]


from typing import Optional
from pydantic import BaseModel

class AlertAck(BaseModel):
    kind: str
    city_name: Optional[str] = None
    minutes: int = 30
    user: Optional[str] = "demo"

@app.post("/api/alerts/ack")
async def alerts_ack(a: AlertAck):
    async with pool.acquire() as con:
        await con.execute(
            """
            INSERT INTO ops.alert_acks(kind, city_name, until, acked_by)
            VALUES ($1, $2, NOW() + make_interval(mins => $3::int), $4)
            """,
            a.kind, a.city_name, a.minutes, a.user or "demo"
        )
    return {"ok": True}

@app.get("/api/alerts/active")
async def alerts_active():
    alerts = []
    async with pool.acquire() as con:
        # --- driver shortage (unchanged query) ---
        shortage = await con.fetch("""
          WITH latest AS (
            SELECT DISTINCT ON (city_name)
                   city_name, ts, pressure_score, order_count, available_couriers
            FROM ops.city_pressure_minute_mv
            ORDER BY city_name, ts DESC
          )
          SELECT * FROM latest
          WHERE pressure_score >= 75
          ORDER BY pressure_score DESC
          LIMIT 3
        """)
        for r in shortage:
            alerts.append({
                "kind": "driver_shortage",
                "severity": "warning",
                "city_name": r["city_name"],
                "title": f"Driver shortage in {r['city_name']}",
                "details": {
                    "pressure": float(r["pressure_score"] or 0),
                    "orders": int(r["order_count"] or 0),
                    "available_couriers": int(r["available_couriers"] or 0),
                }
            })

        # --- SLA spike (unchanged query) ---
        spike = await con.fetch("""
          SELECT city_name, SUM(breaches)::int AS breaches
          FROM ops.sla_breaches_per_minute_mv
          WHERE ts >= NOW() - INTERVAL '10 minutes'
          GROUP BY city_name
          HAVING SUM(breaches) >= 3
          ORDER BY breaches DESC
          LIMIT 3
        """)
        for r in spike:
            alerts.append({
                "kind": "sla_spike",
                "severity": "critical",
                "city_name": r["city_name"],
                "title": f"SLA breaches spiking in {r['city_name']}",
                "details": {"breaches_10m": int(r["breaches"])}
            })

        # --- peak start (your fixed version; using window_end) ---
        peak = await con.fetch("""
          WITH latest AS (
            SELECT DISTINCT ON (city_name)
                   city_name,
                   window_end AS ts,
                   order_count
            FROM city_orders_per_minute
            WHERE window_end >= NOW() - INTERVAL '2 hours'
            ORDER BY city_name, window_end DESC
          ),
          base AS (
            SELECT city_name, AVG(order_count) AS avg2h
            FROM city_orders_per_minute
            WHERE window_end >= NOW() - INTERVAL '2 hours'
            GROUP BY city_name
          )
          SELECT l.city_name, l.order_count, b.avg2h
          FROM latest l
          JOIN base b USING (city_name)
          WHERE l.order_count >= 1.5 * b.avg2h
          ORDER BY (l.order_count - b.avg2h) DESC
          LIMIT 3
        """)
        for r in peak:
            alerts.append({
                "kind": "peak_start",
                "severity": "info",
                "city_name": r["city_name"],
                "title": f"Peak starting in {r['city_name']}",
                "details": {"opm": int(r["order_count"] or 0)}
            })

        # ---- filter out acked alerts (snoozed) ----
        acks = await con.fetch("SELECT kind, city_name FROM ops.alert_acks WHERE until > NOW()")
        acked = {(x["kind"], x["city_name"]) for x in acks}
        alerts = [a for a in alerts if (a["kind"], a.get("city_name")) not in acked]

    return alerts


@app.get("/api/heatmap/cities")
async def heatmap_cities(minutes: int = 60):
    """
    Prefer latest per-city rows from ops.city_pressure_minute_mv (by city_name).
    If missing/stale, fall back to last-5m orders to compute:
      - opm  ≈ orders_last_5m / 5.0
      - pressure scaled 0..100 across cities based on those orders.
    """
    q = """
    -- latest MV record per city *by name*
    WITH mv AS (
      SELECT DISTINCT ON (city_name)
             city_name, ts, pressure_score, order_count
      FROM ops.city_pressure_minute_mv
      WHERE ts >= NOW() - make_interval(mins => $1::int)
      ORDER BY city_name, ts DESC
    ),
    -- fallback: count orders per city in the last 5 minutes
    recent AS (
      SELECT c.city_name,
             COUNT(*)::int AS orders_last_5m
      FROM orders o
      JOIN restaurants r ON r.restaurant_id = o.restaurant_id
      JOIN cities      c ON c.city_id       = r.city_id
      WHERE o.order_timestamp >= NOW() - INTERVAL '5 minutes'
      GROUP BY c.city_name
    ),
    base AS (
      SELECT
        c.city_name,
        c.latitude  AS lat,
        c.longitude AS lon,
        mv.pressure_score::float           AS mv_pressure,
        mv.order_count::float              AS mv_opm,
        COALESCE(recent.orders_last_5m, 0) AS orders_last_5m
      FROM cities c
      LEFT JOIN mv     ON lower(mv.city_name)     = lower(c.city_name)
      LEFT JOIN recent ON lower(recent.city_name) = lower(c.city_name)
    ),
    scaled AS (
      SELECT
        b.*,
        CASE
          WHEN b.mv_pressure IS NOT NULL THEN b.mv_pressure
          ELSE CASE
                 WHEN MAX(b.orders_last_5m) OVER () = 0 THEN 0
                 ELSE ROUND(100.0 * b.orders_last_5m / NULLIF(MAX(b.orders_last_5m) OVER (), 0), 1)
               END
        END AS pressure_calc,
        CASE
          WHEN b.mv_opm IS NOT NULL THEN b.mv_opm
          ELSE ROUND(b.orders_last_5m / 5.0, 1)
        END AS opm_calc
      FROM base b
    )
    SELECT city_name, lat, lon,
           pressure_calc AS pressure,
           opm_calc      AS opm
    FROM scaled;
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, minutes)
    return [dict(r) for r in rows]


@app.get("/api/revenue/weekly")
async def revenue_weekly():
    q = """
    SELECT to_char(date_trunc('day', order_timestamp),'Dy') AS day,
           COALESCE(SUM(total_price),0)::float AS gmv
    FROM orders
    WHERE status='Completed'
      AND order_timestamp >= date_trunc('week', NOW())
    GROUP BY 1
    ORDER BY MIN(date_trunc('day', order_timestamp))
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q)
    return [dict(r) for r in rows]

@app.get("/api/revenue/monthly_progress")
async def revenue_monthly_progress(target: Optional[float] = Query(default=None)):
    async with pool.acquire() as con:
        gmv_mtd = await con.fetchval("""
          SELECT COALESCE(SUM(total_price),0)::float
          FROM orders
          WHERE status='Completed'
            AND order_timestamp >= date_trunc('month', NOW())
        """)
    tgt = float(target) if target else max((gmv_mtd or 0.0) * 1.2, 350000.0)
    pct = (gmv_mtd / tgt) * 100.0 if tgt else 0.0
    return {"gmv_mtd": float(gmv_mtd or 0.0), "target": float(tgt), "pct": float(pct)}



from typing import Optional

@app.get("/api/top/restaurants")
async def top_restaurants(
        minutes: int = 1440,
        city: Optional[str] = None,
        metric: str = "gmv",          # gmv | orders | reviews
        min_reviews: int = 0,
        limit: int = 20
):
    """
    Top restaurants by GMV (default) or orders/reviews.
    """
    q = """
    WITH base AS (
      SELECT
        r.restaurant_id                             AS entity_id,
        COALESCE(r.name, 'Restaurant '||r.restaurant_id::text) AS entity_name,
        c.city_name,
        COUNT(*) FILTER (WHERE o.status='Completed')::int                 AS orders,
        COALESCE(SUM(CASE WHEN o.status='Completed' THEN o.total_price END),0)::float AS gmv,
        COUNT(orv.*)::int                                                 AS reviews,
        ROUND(AVG(orv.rating)::numeric, 2)                                AS avg_rating
      FROM orders o
      JOIN restaurants r ON r.restaurant_id = o.restaurant_id
      JOIN cities      c ON c.city_id       = r.city_id
      LEFT JOIN order_reviews orv ON orv.order_id = o.order_id
      WHERE (COALESCE(o.pickup_time, o.order_timestamp)
             + (COALESCE(o.time_taken_minutes,0)||' minutes')::interval)
            >= (NOW() - ($1::int * interval '1 minute'))
        AND ($2::text IS NULL OR c.city_name = $2)
      GROUP BY r.restaurant_id, entity_name, c.city_name
    )
    SELECT * FROM base
    WHERE ($4::int <= 0 OR reviews >= $4)
    ORDER BY
      CASE WHEN $3='gmv'     THEN gmv    END DESC NULLS LAST,
      CASE WHEN $3='gmv'     THEN orders END DESC NULLS LAST,
      CASE WHEN $3='orders'  THEN orders END DESC NULLS LAST,
      CASE WHEN $3='orders'  THEN gmv    END DESC NULLS LAST,
      CASE WHEN $3='reviews' THEN reviews END DESC NULLS LAST,
      CASE WHEN $3='reviews' THEN avg_rating END DESC NULLS LAST
    LIMIT $5;
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, minutes, city, metric, min_reviews, limit)
    return [dict(r) for r in rows]


@app.get("/api/top/couriers")
async def top_couriers(minutes: int = 1440, limit: int = 20):
    async with pool.acquire() as con:
        rows = await con.fetch("""
          SELECT
            dp.delivery_person_id AS entity_id,
            COALESCE(dp.name, 'Courier ' || dp.delivery_person_id::text) AS entity_name,
            c.city_name,
            COUNT(*) AS reviews,
            ROUND(AVG(orv.rating)::numeric, 2) AS avg_rating
          FROM order_reviews orv
          JOIN orders             o  ON o.order_id            = orv.order_id
          JOIN delivery_personnel dp ON dp.delivery_person_id = o.delivery_person_id
          JOIN cities             c  ON c.city_id             = dp.city_id
          WHERE orv.posted_at >= NOW() - make_interval(mins => $1::int)
          GROUP BY dp.delivery_person_id, entity_name, c.city_name
          ORDER BY reviews DESC
          LIMIT $2
        """, minutes, limit)
    return [dict(r) for r in rows]

from typing import Optional, Literal

@app.get("/api/top/dishes")
async def top_dishes(
        minutes: int = 1440,
        city: Optional[str] = None,
        limit: int = 10,
        metric: Literal["units","revenue"] = "revenue"
):
    """
    Top dishes by units or revenue in the last `minutes`.
    """
    order_by = "units" if metric == "units" else "revenue"

    q = f"""
    WITH recent_completed AS (
      SELECT o.order_id
      FROM orders o
      WHERE o.status = 'Completed'
        -- Use a simpler, robust window; switch back to completion-time if you prefer
        AND o.order_timestamp >= NOW() - ($1::int * interval '1 minute')
    )
    SELECT
      mi.item_name                             AS dish,
      COUNT(*)::int                            AS units,
      COALESCE(SUM(oi.unit_price * oi.qty),0)::float AS revenue,
      c.city_name
    FROM order_items oi
    JOIN recent_completed rc ON rc.order_id = oi.order_id
    JOIN orders o       ON o.order_id       = oi.order_id
    JOIN restaurants r  ON r.restaurant_id  = o.restaurant_id
    JOIN cities c       ON c.city_id        = r.city_id
    JOIN menu_items mi  ON mi.item_id       = oi.menu_item_id
    WHERE ($2::text IS NULL OR c.city_name = $2)
    GROUP BY mi.item_name, c.city_name
    ORDER BY {order_by} DESC
    LIMIT $3;
    """

    async with pool.acquire() as con:
        rows = await con.fetch(q, minutes, city, limit)
    return [dict(r) for r in rows]



@app.get("/api/restaurants/live")
async def restaurants_live(city: Optional[str] = None, limit: int = 50):
    q = """
    SELECT
      ui.restaurant_id,
      COALESCE(c.city_name, ui.city_name) AS city_name,
      COALESCE(r.name, ('#' || ui.restaurant_id)::text) AS restaurant_name,

      COALESCE((ui.payload->>'orders_last_15m')::int, 0) AS orders_last_15m,
      COALESCE((ui.payload->>'avg_prep_time_last_hour')::numeric, 0)::double precision AS avg_prep_time_min,
      COALESCE((ui.payload->>'is_promo_active')::boolean, false) AS is_promo_active,

      COALESCE(
        (ui.payload->>'report_timestamp')::bigint,
        CAST(EXTRACT(EPOCH FROM ui.last_update)*1000 AS bigint)
      ) AS updated_ms

    FROM ops.restaurant_status_ui ui
    LEFT JOIN restaurants r ON r.restaurant_id = ui.restaurant_id
    LEFT JOIN cities      c ON c.city_id       = r.city_id
    LEFT JOIN ops.restaurant_overrides o ON o.restaurant_id = ui.restaurant_id   -- <— add this
    WHERE ($1::text IS NULL OR COALESCE(c.city_name, ui.city_name) = $1)
    ORDER BY orders_last_15m DESC NULLS LAST, updated_ms DESC
    LIMIT $2
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, city, limit)
    return [dict(r) for r in rows]


@app.get("/api/restaurants/trend")
async def restaurant_trend(restaurant_id: int, hours: int = 6):
    q = """
    SELECT ts,
           orders_last_15m,
           avg_prep_time
    FROM ops.restaurant_status_log
    WHERE restaurant_id = $1
      AND ts >= NOW() - ($2::int || ' hours')::interval
    ORDER BY ts ASC
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, restaurant_id, hours)
    return [dict(r) for r in rows]

from typing import Optional

@app.get("/api/restaurants/load_map")
async def restaurants_load_map(city: Optional[str] = None, limit: int = 400):
    """
    Latest per-restaurant load for map pins.
    load_score ~ 0..100 blended from orders_last_15m and avg_prep_time_last_hour.
    Uses restaurant lat/lon if present; otherwise falls back to city lat/lon.
    """
    q = """
    WITH latest AS (
      SELECT ui.restaurant_id,
             COALESCE((ui.payload->>'orders_last_15m')::int, 0) AS orders15,
             COALESCE((ui.payload->>'avg_prep_time_last_hour')::numeric, 0)::double precision AS prep,
             COALESCE((ui.payload->>'report_timestamp')::bigint,
                      (EXTRACT(EPOCH FROM ui.last_update)*1000)::bigint) AS updated_ms
      FROM ops.restaurant_status_ui ui
    ),
    joined AS (
      SELECT r.restaurant_id,
             r.name,
             c.city_name,
             COALESCE(r.latitude,  c.latitude)  AS lat,
             COALESCE(r.longitude, c.longitude) AS lon,
             l.orders15, l.prep, l.updated_ms
      FROM restaurants r
      JOIN cities c ON c.city_id = r.city_id
      JOIN latest l ON l.restaurant_id = r.restaurant_id
      WHERE ($1::text IS NULL OR c.city_name = $1)
        AND COALESCE(r.latitude,  c.latitude)  IS NOT NULL
        AND COALESCE(r.longitude, c.longitude) IS NOT NULL
    ),
    norms AS (
      SELECT *,
             NULLIF(MAX(orders15) OVER (), 0) AS max_o,
             NULLIF(MAX(prep)     OVER (), 0) AS max_p
      FROM joined
    )
    SELECT
      restaurant_id,
      name        AS restaurant_name,
      city_name,
      lat, lon,
      updated_ms,
      orders15,
      prep,
      -- blend: 60% orders intensity, 40% prep-time pressure (capped)
      ROUND( LEAST(100,
           100 * ( 0.6 * (orders15 / COALESCE(max_o,1))
                 + 0.4 * (prep / GREATEST(COALESCE(max_p,1), 20)) )
      )::numeric, 0) AS load_score
    FROM norms
    ORDER BY load_score DESC NULLS LAST
    LIMIT $2;
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, city, limit)
    return [dict(r) for r in rows]


@app.get("/api/couriers/live")
async def couriers_live(city: Optional[str] = None, limit: int = 50):
    q = """
    WITH recent_city AS (
      SELECT o.delivery_person_id, c.city_name, MAX(o.order_timestamp) AS last_ts
      FROM orders o
      JOIN cities c ON c.city_id = o.city_id
      WHERE o.order_timestamp >= NOW() - INTERVAL '6 hours'
      GROUP BY o.delivery_person_id, c.city_name
    )
    SELECT
      ui.delivery_person_id AS courier_id,
      COALESCE(dp.name, '#' || ui.delivery_person_id::text) AS courier_name,   -- <— NEW
      COALESCE(rc.city_name, ui.city_name) AS city_name,
      COALESCE((ui.payload->>'active_deliveries_count')::int, 0)   AS active_deliveries,
      COALESCE((ui.payload->>'avg_delivery_speed_today')::float, NULL) AS avg_speed_kmh,
      COALESCE(
        NULLIF(ui.payload->>'report_timestamp','')::bigint,
        CASE WHEN (ui.payload->>'report_timestamp') ~ '^[0-9]{10}$'
             THEN ((ui.payload->>'report_timestamp')::bigint * 1000) END,
        CASE WHEN ui.payload ? 'report_timestamp'
             THEN (EXTRACT(EPOCH FROM (ui.payload->>'report_timestamp')::timestamptz) * 1000)::bigint END,
        NULLIF(ui.payload->>'ts','')::bigint,
        NULLIF(ui.payload->>'event_time','')::bigint,
        (EXTRACT(EPOCH FROM ui.last_update) * 1000)::bigint
      ) AS updated_ms
    FROM ops.courier_activity_ui ui
    LEFT JOIN delivery_personnel dp ON dp.delivery_person_id = ui.delivery_person_id  -- <— NEW
    LEFT JOIN recent_city rc        ON rc.delivery_person_id = ui.delivery_person_id
    WHERE ($1::text IS NULL OR COALESCE(rc.city_name, ui.city_name) = $1)
    ORDER BY updated_ms DESC
    LIMIT $2
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, city, limit)
    return [dict(r) for r in rows]





# webapi/app.py  (add)
from fastapi import Body
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

@app.post("/api/restaurants/pause")
async def pause_restaurant(payload: dict):
    rid = int(payload.get("restaurant_id") or 0)
    minutes = int(payload.get("minutes") or 15)
    if not rid:
        raise HTTPException(status_code=400, detail="restaurant_id required")

    until = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    async with pool.acquire() as con:
        await con.execute("""
            INSERT INTO ops.restaurant_overrides (restaurant_id, paused_until, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (restaurant_id)
            DO UPDATE SET paused_until = EXCLUDED.paused_until,
                          updated_at    = NOW()
        """, rid, until)

    # Frontend will show this time immediately
    return {"ok": True, "until": until.isoformat()}



@app.post("/api/couriers/nudge")
async def couriers_nudge(courier_id: int = Body(...), reason: str = Body("slow"), user: str = Body("ops")):
    async with pool.acquire() as con:
        await con.execute("""
          INSERT INTO ops.actions_log(ts, user_name, action, params, result)
          VALUES (NOW(), $1, 'NUDGE_COURIER', jsonb_build_object('courier_id',$2,'reason',$3), 'queued')
        """, user, courier_id, reason)
    try:
        await publish_decision("ops.decisions", {
            "kind":"NUDGE_COURIER","courier_id": courier_id, "reason": reason,
            "decided_by": user, "ts": time.time()
        })
    except Exception:
        pass
    return {"ok": True}

# --- WEATHER ENDPOINTS -----------------------------------------------------
from typing import Optional

@app.get("/api/weather/orders")
async def weather_orders(
        minutes: int = 60,
        city: Optional[str] = None,
        rain: Optional[str] = None,   # "true" | "false" | None
        limit: int = 200
):
    q = """
    SELECT
      owe.order_id,
      r.name AS restaurant_name,
      c.city_name,
      owe.weather,
      owe.is_rain,
      owe.is_rush_hour,
      owe.time_taken_minutes,
      owe.event_time,
      (EXTRACT(EPOCH FROM owe.event_time)*1000)::bigint AS event_ms
    FROM order_weather_enriched owe
    JOIN restaurants r ON r.restaurant_id = owe.restaurant_id
    JOIN cities      c ON c.city_id      = owe.city_id
    WHERE owe.event_time >= NOW() - ($1::int || ' minutes')::interval
      AND ($2::text IS NULL OR c.city_name = $2)
      AND (
            $3::text IS NULL
         OR ($3='true'  AND owe.is_rain IS TRUE)
         OR ($3='false' AND owe.is_rain IS FALSE)
      )
    ORDER BY owe.event_time DESC
    LIMIT $4::int;
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, minutes, city, rain, limit)
    return [dict(r) for r in rows]


@app.get("/api/weather/impact")
async def weather_impact(hours: int = 24, city: Optional[str] = None):
    """
    Aggregates: count + avg time by rain/rush flags.
    """
    q = """
    WITH src AS (
      SELECT *
      FROM order_weather_enriched owe
      WHERE owe.event_time >= NOW() - ($1::int || ' hours')::interval
    )
    SELECT
      c.city_name,
      s.is_rain,
      s.is_rush_hour,
      COUNT(*)::int                                   AS orders,
      ROUND(AVG(s.time_taken_minutes)::numeric, 2)    AS avg_minutes
    FROM src s
    JOIN restaurants r ON r.restaurant_id = s.restaurant_id
    JOIN cities      c ON c.city_id      = r.city_id
    WHERE ($2::text IS NULL OR c.city_name = $2)
    GROUP BY c.city_name, s.is_rain, s.is_rush_hour
    ORDER BY c.city_name, s.is_rain DESC, s.is_rush_hour DESC;
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, hours, city)
    return [dict(r) for r in rows]


@app.get("/api/weather/city_heat")
async def weather_city_heat(minutes: int = 60):
    """
    City bubbles for a Leaflet map: count, avg time, rain ratio.
    Assumes cities(latitude, longitude) columns exist (you said they do 👍).
    """
    q = """
    SELECT
      c.city_name,
      c.latitude  AS lat,
      c.longitude AS lon,
      COUNT(*)::int                                                  AS orders,
      ROUND(AVG(owe.time_taken_minutes)::numeric, 2)                 AS avg_minutes,
      COALESCE(AVG(CASE WHEN owe.is_rain THEN 1.0 ELSE 0.0 END), 0)  AS rain_ratio
    FROM order_weather_enriched owe
    JOIN restaurants r ON r.restaurant_id = owe.restaurant_id
    JOIN cities      c ON c.city_id      = r.city_id
    WHERE owe.event_time >= NOW() - ($1::int || ' minutes')::interval
    GROUP BY c.city_name, c.latitude, c.longitude
    ORDER BY orders DESC;
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, minutes)
    return [dict(r) for r in rows]

# ---------- Dynamic SLA (separate from classic SLA) ----------

@app.get("/api/dsla/violations")
async def dsla_violations(
        minutes: int = 180,
        city: Optional[str] = None,
        limit: int = 50,
        threshold: float = 1.25
):
    """
    Recent Dynamic-SLA violations (predicted vs actual), separate endpoint.
    """
    q = """
    SELECT
      v.order_id,
      r.name AS restaurant_name,
      c.city_name,
      v.predicted_minutes,
      v.actual_minutes,
      ROUND(v.overrun_minutes::numeric, 1)    AS overrun_minutes,
      ROUND(v.overrun_percentage::numeric, 3) AS overrun_pct,
      v.violation_timestamp
    FROM dynamic_sla_violations v
    JOIN orders o        ON o.order_id      = v.order_id
    JOIN restaurants r   ON r.restaurant_id = o.restaurant_id
    JOIN cities c        ON c.city_id       = o.city_id
    WHERE v.violation_timestamp >= NOW() - ($1::int * interval '1 minute')
      AND v.overrun_percentage >= $4
      AND ($2::text IS NULL OR c.city_name = $2)
    ORDER BY v.violation_timestamp DESC
    LIMIT $3
    """
    async with pool.acquire() as con:
        rows = await con.fetch(q, minutes, city, limit, threshold)
    return [dict(r) for r in rows]


@app.get("/api/dsla/model_health")
async def dsla_model_health(hours: int = 6):
    """
    Time-bucketed MAE/MAPE for the ETA model behind dynamic SLA.
    Returns: {"rows":[{"ts": "...", "mae": <float>, "mape": <float>}...], "mae_1h": <float>}
    """
    q = """
    WITH b AS (
      SELECT
        -- derive an event time near delivery without needing completed_at
        (o.order_timestamp + (COALESCE(ep.actual_minutes, ep.predicted_minutes) || ' minutes')::interval) AS ts,
        ep.absolute_error,
        NULLIF(ep.predicted_minutes, 0) AS predicted
      FROM eta_model_performance ep
      JOIN orders o ON o.order_id = ep.order_id
      WHERE o.order_timestamp >= NOW() - ($1::int || ' hours')::interval
    ),
    g AS (
      SELECT
        date_trunc('minute', ts)
          - ((EXTRACT(minute FROM ts)::int % 15) || ' minutes')::interval AS bucket,
        AVG(absolute_error)::float                        AS mae,
        AVG(absolute_error / NULLIF(predicted, 1))::float AS mape
      FROM b
      GROUP BY 1
    ),
    last1h AS (
      SELECT AVG(absolute_error)::float AS mae_1h
      FROM b
      WHERE ts >= NOW() - INTERVAL '1 hour'
    )
    SELECT
      COALESCE(
        json_agg(
          json_build_object('ts', g.bucket, 'mae', g.mae, 'mape', g.mape)
          ORDER BY g.bucket
        ),
        '[]'::json
      ) AS rows,
      COALESCE((SELECT mae_1h FROM last1h), 0.0) AS mae_1h
    FROM g;
    """
    async with pool.acquire() as con:
        row = await con.fetchrow(q, hours)

    if not row:
        return {"rows": [], "mae_1h": 0.0}

    rows_field = row["rows"]
    # asyncpg can return json as str; normalize to list
    if isinstance(rows_field, str):
        try:
            rows = json.loads(rows_field)
        except Exception:
            rows = []
    else:
        rows = rows_field or []

    return {"rows": rows, "mae_1h": float(row["mae_1h"] or 0.0)}



@app.get("/api/dsla/summary")
async def dsla_summary(hours: int = 24, threshold: float = 1.25):
    """
    KPI strip for Dynamic SLA only (rate & error percentiles).
    """
    q = """
    WITH o AS (
      SELECT order_id FROM orders
      WHERE status='Completed' AND order_timestamp >= NOW() - ($1::int || ' hours')::interval
    ), v AS (
      SELECT * FROM dynamic_sla_violations
      WHERE violation_timestamp >= NOW() - ($1::int || ' hours')::interval
        AND overrun_percentage >= $2
    ), e AS (
      SELECT absolute_error FROM eta_model_performance
      WHERE COALESCE(completed_at, now()) >= NOW() - ($1::int || ' hours')::interval
    )
    SELECT
      (SELECT COUNT(*) FROM v)::int                            AS violations,
      (SELECT COUNT(*) FROM o)::int                            AS completed,
      CASE WHEN (SELECT COUNT(*) FROM o)=0 THEN 0
           ELSE ROUND((SELECT COUNT(*) FROM v)::numeric
                       / NULLIF((SELECT COUNT(*) FROM o),0), 4) END  AS violation_rate,
      (SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY absolute_error) FROM e) AS p50_abs_err,
      (SELECT percentile_disc(0.9) WITHIN GROUP (ORDER BY absolute_error) FROM e) AS p90_abs_err
    """
    async with pool.acquire() as con:
        row = await con.fetchrow(q, hours, threshold)
    return dict(row) if row else {}

# Add after your existing endpoints (around line 1200+)

# IMPORTANT: Define /recent BEFORE /{order_id} to avoid path conflicts

@app.get("/api/routes/recent")
async def get_recent_routes(
        limit: int = 20,
        city: Optional[str] = None,
        courier_id: Optional[int] = None
):
    """Get recent completed delivery routes"""
    q = """
    SELECT 
        dr.route_id,
        dr.order_id,
        dr.delivery_person_id,
        dr.restaurant_id,
        dr.total_distance_km,
        dr.actual_duration_min,
        dr.route_completed_at,
        
        r.name AS restaurant_name,
        dp.name AS courier_name,
        c.city_name,
        o.status
        
    FROM delivery_routes dr
    JOIN orders o ON dr.order_id = o.order_id
    JOIN restaurants r ON dr.restaurant_id = r.restaurant_id
    JOIN delivery_personnel dp ON dr.delivery_person_id = dp.delivery_person_id
    JOIN cities c ON r.city_id = c.city_id
    WHERE dr.route_completed_at IS NOT NULL
      AND ($2::text IS NULL OR c.city_name = $2)
      AND ($3::int IS NULL OR dr.delivery_person_id = $3)
    ORDER BY dr.route_completed_at DESC
    LIMIT $1
    """

    async with pool.acquire() as con:
        rows = await con.fetch(q, limit, city, courier_id)

    return [dict(r) for r in rows]


@app.get("/api/routes/map/active")
async def get_active_routes_for_map(city: Optional[str] = None):
    """Get currently active deliveries with routes for live map visualization"""
    q = """
    SELECT 
        dr.order_id,
        dr.route_geometry,
        dr.waypoints,
        dr.route_started_at,
        
        r.name AS restaurant_name,
        r.latitude AS restaurant_lat,
        r.longitude AS restaurant_lon,
        
        o.delivery_latitude,
        o.delivery_longitude,
        o.status,
        
        dp.name AS courier_name,
        c.city_name,
        
        -- Calculate progress (elapsed time / total time)
        CASE 
            WHEN dr.estimated_duration_min > 0 THEN
                LEAST(1.0, GREATEST(0.0, 
                    EXTRACT(EPOCH FROM (NOW() - dr.route_started_at)) / 
                    (dr.estimated_duration_min * 60.0)
                ))
            ELSE 0.0
        END AS progress_ratio
        
    FROM delivery_routes dr
    JOIN orders o ON dr.order_id = o.order_id
    JOIN restaurants r ON dr.restaurant_id = r.restaurant_id
    JOIN delivery_personnel dp ON dr.delivery_person_id = dp.delivery_person_id
    JOIN cities c ON r.city_id = c.city_id
    WHERE o.status IN ('Processing')
      AND dr.route_completed_at IS NULL
      AND dr.route_started_at >= NOW() - INTERVAL '2 hours'
      AND ($1::text IS NULL OR c.city_name = $1)
    ORDER BY dr.route_started_at DESC
    LIMIT 50
    """

    async with pool.acquire() as con:
        rows = await con.fetch(q, city)

    routes = []
    for row in rows:
        route = dict(row)
        route['route_geometry'] = json.loads(route['route_geometry']) if isinstance(route['route_geometry'], str) else route['route_geometry']
        route['waypoints'] = json.loads(route['waypoints']) if isinstance(route['waypoints'], str) else route['waypoints']
        routes.append(route)

    return routes


@app.get("/api/routes/courier/{courier_id}/history")
async def get_courier_route_history(
        courier_id: int,
        hours: int = 8
):
    """Get all routes for a specific courier in the last N hours"""
    q = """
    SELECT 
        dr.route_id,
        dr.order_id,
        dr.route_geometry,
        dr.total_distance_km,
        dr.actual_duration_min,
        dr.route_started_at,
        dr.route_completed_at,
        
        r.name AS restaurant_name,
        r.latitude AS restaurant_lat,
        r.longitude AS restaurant_lon,
        
        o.delivery_latitude,
        o.delivery_longitude,
        
        c.city_name
        
    FROM delivery_routes dr
    JOIN orders o ON dr.order_id = o.order_id
    JOIN restaurants r ON dr.restaurant_id = r.restaurant_id
    JOIN cities c ON r.city_id = c.city_id
    WHERE dr.delivery_person_id = $1
      AND dr.route_started_at >= NOW() - ($2::int || ' hours')::interval
    ORDER BY dr.route_started_at DESC
    """

    async with pool.acquire() as con:
        rows = await con.fetch(q, courier_id, hours)

    routes = []
    for row in rows:
        route = dict(row)
        # Parse geometry
        route['route_geometry'] = json.loads(route['route_geometry']) if isinstance(route['route_geometry'], str) else route['route_geometry']
        routes.append(route)

    return routes


# MUST be defined LAST among /api/routes/* endpoints
@app.get("/api/routes/{order_id}")
async def get_route(order_id: int):
    """Get delivery route for a specific order with full details"""
    q = """
    SELECT 
        dr.route_id,
        dr.order_id,
        dr.delivery_person_id,
        dr.restaurant_id,
        dr.route_geometry,
        dr.waypoints,
        dr.total_distance_km,
        dr.estimated_duration_min,
        dr.actual_duration_min,
        dr.route_started_at,
        dr.route_completed_at,
        
        -- Restaurant details
        r.name AS restaurant_name,
        r.latitude AS restaurant_lat,
        r.longitude AS restaurant_lon,
        
        -- Delivery details
        o.delivery_latitude,
        o.delivery_longitude,
        o.status,
        
        -- Courier details
        dp.name AS courier_name,
        
        -- City
        c.city_name
        
    FROM delivery_routes dr
    JOIN orders o ON dr.order_id = o.order_id
    JOIN restaurants r ON dr.restaurant_id = r.restaurant_id
    JOIN delivery_personnel dp ON dr.delivery_person_id = dp.delivery_person_id
    JOIN cities c ON r.city_id = c.city_id
    WHERE dr.order_id = $1
    """

    async with pool.acquire() as con:
        row = await con.fetchrow(q, order_id)

    if not row:
        raise HTTPException(status_code=404, detail="Route not found")

    result = dict(row)

    # Parse JSON fields
    result['route_geometry'] = json.loads(result['route_geometry']) if isinstance(result['route_geometry'], str) else result['route_geometry']
    result['waypoints'] = json.loads(result['waypoints']) if isinstance(result['waypoints'], str) else result['waypoints']

    return result