import os, json, asyncio
import asyncpg, httpx
from aiokafka import AIOKafkaConsumer
from aiokafka.admin import AIOKafkaAdminClient
import time
from prometheus_client import Counter, Histogram, Gauge, start_http_server

MSG_CONSUMED = Counter("notifier_msg_consumed_total", "Messages consumed", ["topic"])
HANDLER_ERRS = Counter("notifier_handler_errors_total", "Handler errors", ["topic"])
WS_BROADCASTS = Counter("notifier_ws_broadcast_total", "WS messages broadcast", ["type"])
DB_LATENCY = Histogram("notifier_db_latency_seconds", "DB op latency", ["op"])

def typed_event(title, typ, severity="info", city=None, payload=None):
    return {
        "type": typ, "title": title, "severity": severity,
        "city": city, "payload": payload or {}
    }


KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPICS = [t.strip() for t in os.getenv("TOPICS", "sla_violations").split(",") if t.strip()]
PG_DSN = os.getenv("PG_DSN", "postgresql://airflow:airflow@postgres:5432/airflow")
WEBAPI_NOTIFY = os.getenv("WEBAPI_NOTIFY_URL", "http://webapi:8000/api/notify")
GROUP_ID = os.getenv("GROUP_ID", "notifier")
START_FROM_BEGINNING = os.getenv("START_FROM_BEGINNING", "false").lower() in ("1","true","yes")

async def broadcast(title: str, typ: str, severity: str, details: dict):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(WEBAPI_NOTIFY, json={
                "id": 0, "title": title, "type": typ, "severity": severity, "details": details
            })
        except Exception:
            pass

async def handle_topic(pool, topic: str, payload: dict):
    MSG_CONSUMED.labels(topic).inc()
    try:
        async with pool.acquire() as con:
            t0 = time.time()

            if topic == "sla_violations":
                if await is_city_muted(pool, payload.get("city_name")):
                    return
                title = f"SLA breach order {payload.get('order_id')}"
                await con.execute("""
                  INSERT INTO ops.notifications(type, severity, title, details)
                  VALUES ('SLA','warning',$1,$2::jsonb)
                """, title, json.dumps(payload))
                WS_BROADCASTS.labels("sla_violation").inc()
                await broadcast(typed_event(title, "sla_violation", "warning",
                                            city=payload.get("city_name"), payload=payload))

            elif topic == "eta_predictions":
                await con.execute("""
                  INSERT INTO ops.eta_predictions_ui(order_id, city_name, payload)
                  VALUES ($1,$2,$3::jsonb)
                  ON CONFLICT (order_id) DO UPDATE
                    SET city_name=EXCLUDED.city_name, payload=EXCLUDED.payload, event_time=NOW()
                """, payload.get("order_id"), payload.get("city_name"), json.dumps(payload))
                WS_BROADCASTS.labels("eta_prediction").inc()
                await broadcast(typed_event(f"ETA update {payload.get('order_id')}",
                                            "eta_prediction", "info",
                                            city=payload.get("city_name"), payload=payload))

            elif topic == "courier_features_live":
                cid = payload.get("delivery_person_id")
                ts_ms = payload.get("report_timestamp") or 0
                # optional city enrichment: if courier has a home/base city; else derive from last order city if you track it.
                city = await con.fetchval(
                    "SELECT city_name FROM courier_profiles WHERE delivery_person_id=$1",
                    cid
                )
                await con.execute("""
                  INSERT INTO ops.courier_activity_ui (delivery_person_id, city_name, payload, last_update)
                  VALUES ($1,$2,$3::jsonb, to_timestamp($4/1000.0))
                  ON CONFLICT (delivery_person_id) DO UPDATE
                    SET city_name=EXCLUDED.city_name,
                        payload=EXCLUDED.payload,
                        last_update=EXCLUDED.last_update
                """, cid, city, json.dumps(payload), ts_ms)
                await con.execute("""
                  INSERT INTO ops.courier_activity_log
                    (ts, delivery_person_id, city_name, active_deliveries, avg_speed_kmh, payload)
                  VALUES (to_timestamp($1/1000.0), $2, $3, $4, $5, $6::jsonb)
                """, ts_ms, cid, city,
                                  payload.get("active_deliveries_count"),
                                  payload.get("avg_delivery_speed_today"),
                                  json.dumps(payload))
                await broadcast(typed_event(
                    title=f"Courier update c#{cid}",
                    typ="courier_update",
                    severity="info",
                    city=city,
                    payload=payload
                ))

            elif topic == "restaurant_features_live":
                rid = payload.get("restaurant_id")
                ts_ms = payload.get("report_timestamp") or 0
                # lookup city once (cache this in-process if you like)
                city = await con.fetchval(
                    "SELECT c.city_name FROM restaurants r JOIN cities c ON c.city_id=r.city_id WHERE r.restaurant_id=$1",
                    rid
                )
                await con.execute("""
                  INSERT INTO ops.restaurant_status_ui (restaurant_id, city_name, payload, last_update)
                  VALUES ($1,$2,$3::jsonb, to_timestamp($4/1000.0))
                  ON CONFLICT (restaurant_id) DO UPDATE
                    SET city_name=EXCLUDED.city_name,
                        payload=EXCLUDED.payload,
                        last_update=EXCLUDED.last_update
                """, rid, city, json.dumps(payload), ts_ms)
                await con.execute("""
                  INSERT INTO ops.restaurant_status_log
                    (ts, restaurant_id, city_name, orders_last_15m, avg_prep_time, is_promo_active, payload)
                  VALUES (to_timestamp($1/1000.0), $2, $3, $4, $5, $6, $7::jsonb)
                """, ts_ms, rid, city,
                                  payload.get("orders_last_15m"),
                                  payload.get("avg_prep_time_last_hour"),
                                  payload.get("is_promo_active"),
                                  json.dumps(payload))
                await broadcast(typed_event(
                    title=f"Restaurant update r#{rid}",
                    typ="restaurant_update",
                    severity="info",
                    city=city,
                    payload=payload
                ))

            elif topic == "dynamic_sla_violations":
                await con.execute("""
                  INSERT INTO ops.dynamic_sla_ui(order_id, city_name, payload)
                  VALUES ($1, $2, $3::jsonb)
                """, payload.get("order_id"), payload.get("city_name"), json.dumps(payload))
                WS_BROADCASTS.labels("dynamic_sla").inc()
                await broadcast(typed_event("Dynamic SLA", "dynamic_sla", "warning",
                                            city=payload.get("city_name"), payload=payload))

            DB_LATENCY.labels("handle_topic").observe(time.time()-t0)

    except Exception as e:
        HANDLER_ERRS.labels(topic).inc()
        print(f"[notifier] handler error topic={topic}: {e}")



async def wait_for_topics():
    admin = AIOKafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP)
    await admin.start()
    try:
        deadline = asyncio.get_event_loop().time() + 60
        while True:
            existing = set(await admin.list_topics())
            missing = [t for t in TOPICS if t not in existing]
            if not missing:
                print(f"[notifier] topics ready: {TOPICS}")
                return
            if asyncio.get_event_loop().time() > deadline:
                raise RuntimeError(f"Topics missing after 60s: {missing}")
            print(f"[notifier] waiting for topics: {missing}")
            await asyncio.sleep(2)
    finally:
        await admin.close()

async def seek_to_end(consumer: AIOKafkaConsumer):
    """Optionally start from end to avoid replaying backlog."""
    if START_FROM_BEGINNING:
        print("[notifier] starting from beginning (replaying backlog)")
        return
    await asyncio.sleep(0)  # yield once
    parts = consumer.assignment()
    if not parts:
        # wait for assignment
        for _ in range(30):
            await asyncio.sleep(0.2)
            parts = consumer.assignment()
            if parts:
                break
    if parts:
        end_offsets = await consumer.end_offsets(list(parts))
        for tp in parts:
            try:
                await consumer.seek(tp, end_offsets[tp])
            except Exception:
                pass
        print("[notifier] advanced to end of current offsets")

_mute_cache = {"exp": 0, "data": set()}

async def is_city_muted(pool, city):
    if not city:
        return False
    now = time.time()
    if now >= _mute_cache["exp"]:
        async with pool.acquire() as con:
            rows = await con.fetch("SELECT city_name FROM ops.alert_mutes WHERE until > NOW()")
        _mute_cache["data"] = {r["city_name"] for r in rows}
        _mute_cache["exp"] = now + 20  # refresh every 20s
    return city in _mute_cache["data"]

async def main():
    # Only list topics you actually have. Add more later when jobs produce them.
    print(f"[notifier] bootstrap={KAFKA_BOOTSTRAP} topics={TOPICS} group={GROUP_ID}")
    await wait_for_topics()

    pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=3)
    consumer = AIOKafkaConsumer(
        *TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=GROUP_ID,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        metadata_max_age_ms=30000,
    )

    await consumer.start()
    print(f"[notifier] consuming from {TOPICS} on {KAFKA_BOOTSTRAP} as group '{GROUP_ID}'")
    try:
        await seek_to_end(consumer)
        async for msg in consumer:
            payload = msg.value if isinstance(msg.value, dict) else {}
            print(f"[notifier] topic={msg.topic} keys={list(payload.keys())[:5]}")
            try:
                await handle_topic(pool, msg.topic, payload)
            except Exception as e:
                print(f"[notifier] handler error: {e}")
    finally:
        await consumer.stop()
        await pool.close()

if __name__ == "__main__":
    try:
        import uvloop; uvloop.install()
    except Exception:
        pass
    # optional: expose metrics
    try:
        start_http_server(int(os.getenv("PROM_PORT","8008")))
        print("[notifier] prometheus on port", os.getenv("PROM_PORT","8008"))
    except Exception:
        pass
    asyncio.run(main())
