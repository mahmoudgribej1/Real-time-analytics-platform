import os, json, asyncio
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
