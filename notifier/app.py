import os, json, asyncio
import asyncpg, httpx
from aiokafka import AIOKafkaConsumer
from aiokafka.admin import AIOKafkaAdminClient
import time

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
    async with pool.acquire() as con:
        if topic == "sla_violations":
            if await is_city_muted(pool, payload.get("city_name")):
                return  # muted city, skip alert
            title = f"SLA breach order {payload.get('order_id')}"
            await con.execute("""
              INSERT INTO ops.notifications(type, severity, title, details)
              VALUES ('SLA','warning',$1,$2::jsonb)
            """, title, json.dumps(payload))
            await broadcast(title, "SLA", "warning", payload)

        elif topic == "dynamic_sla_violations":
            await con.execute("""
              INSERT INTO ops.dynamic_sla_ui(order_id, city_name, payload)
              VALUES ($1, $2, $3::jsonb)
            """, payload.get("order_id"), payload.get("city_name"), json.dumps(payload))

        elif topic == "eta_predictions":
            await con.execute("""
              INSERT INTO ops.eta_predictions_ui(order_id, city_name, payload)
              VALUES ($1, $2, $3::jsonb)
              ON CONFLICT (order_id) DO UPDATE SET
                city_name = EXCLUDED.city_name,
                payload = EXCLUDED.payload,
                event_time = NOW()
            """, payload.get("order_id"), payload.get("city_name"), json.dumps(payload))

        elif topic == "courier_features_live":
            await con.execute("""
              INSERT INTO ops.courier_activity_ui(delivery_person_id, city_name, payload)
              VALUES ($1, $2, $3::jsonb)
              ON CONFLICT (delivery_person_id) DO UPDATE SET
                city_name = EXCLUDED.city_name,
                payload = EXCLUDED.payload,
                last_update = NOW()
            """, payload.get("delivery_person_id"), payload.get("city_name"), json.dumps(payload))

        elif topic == "restaurant_features_live":
            await con.execute("""
              INSERT INTO ops.restaurant_status_ui(restaurant_id, city_name, payload)
              VALUES ($1, $2, $3::jsonb)
              ON CONFLICT (restaurant_id) DO UPDATE SET
                city_name = EXCLUDED.city_name,
                payload = EXCLUDED.payload,
                last_update = NOW()
            """, payload.get("restaurant_id"), payload.get("city_name"), json.dumps(payload))

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
    asyncio.run(main())
