# Streaming Infrastructure & Web Platform

Complete infrastructure, CDC configuration, and web application for real-time food delivery analytics.

## Table of Contents
- [What This Does](#what-this-does)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Infrastructure Setup](#infrastructure-setup)
- [CDC Configuration](#cdc-configuration)
- [Web Application](#web-application)
- [Data Generator](#data-generator)
- [Orchestration](#orchestration)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## What This Does

**Flavor Trend** is a real-time food delivery analytics platform I built for my final year project at ESPRIT. It processes thousands of delivery events per minute and provides instant insights through a web dashboard.

The platform captures every order, review, and weather update in real-time, enriches the data with ML predictions, and displays actionable insights to operations teams.

**Key capabilities:**
- Real-time change data capture from PostgreSQL to Kafka
- Stream processing with Apache Flink (separate repo)
- Live dashboard with WebSocket updates
- ML-powered SLA predictions
- Weather impact analysis
- Interactive delivery route visualization
- Scenario simulation (promotions, rain, outages)

## System Architecture

![System Architecture](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/e4fb2a5d47d39043d6c06df83e3b8aa2f1cf567b/sysArchi.png)

The pipeline flows like this:
1. Data generator creates realistic orders/reviews/weather events
2. PostgreSQL captures operational data with logical replication enabled
3. Debezium streams database changes to Kafka topics
4. Flink processes streams, enriches data, runs ML models
5. Results land back in PostgreSQL and flow to the frontend via WebSocket
6. React dashboard shows everything in real-time

## Tech Stack

**Storage & Streaming**
- PostgreSQL 16.0 (operational + analytical databases)
- Apache Kafka 7.6.1 (event streaming)
- Debezium 2.5.0 (change data capture)

**Processing**
- Apache Flink 1.18.0 (stream processing - see [flink repo](https://github.com/mahmoudgribej1/flavor-trend-flink-processor))

**Application**
- React 18.0 (frontend)
- FastAPI (backend API + WebSocket)
- Python notifier service (Kafka-to-WebSocket bridge)

**Orchestration & Tools**
- Apache Airflow 2.9.2 (workflow automation)
- MLflow 2.14.1 (ML tracking)
- Apache Superset 2.1.3 (BI dashboards)
- Confluent Control Center (Kafka monitoring)

## Getting Started

### What You Need

- Docker Desktop 24.0+ with at least 16GB RAM
- Docker Compose 3.8+
- 20GB free disk space

### Quick Setup
```bash
git clone https://github.com/mahmoudgribej1/flavor-trend-streamsPFE.git
cd flavor-trend-streamsPFE
docker-compose up -d
```

Wait 2-3 minutes for all services to initialize.

### Access Points

| Service | URL | Login |
|---------|-----|-------|
| Frontend Dashboard | http://localhost:3000 | - |
| Backend API Docs | http://localhost:8000/docs | - |
| Flink Dashboard | http://localhost:8081 | - |
| Kafka Control Center | http://localhost:9021 | - |
| Airflow | http://localhost:8082 | airflow / airflow |
| Superset | http://localhost:8088 | admin / admin |
| Debezium UI | http://localhost:8080 | - |
| MLflow | http://localhost:5000 | - |

### Start the Pipeline

Option 1 - Airflow UI:
- Go to http://localhost:8082
- Find `realtime_pipeline` DAG
- Click the play button

Option 2 - Command line:
```bash
docker exec airflow-scheduler airflow dags trigger realtime_pipeline
```

The pipeline takes about 30 seconds to fully start. You'll see live data in the dashboard at http://localhost:3000.

## Infrastructure Setup

### Project Structure
```
flavor-trend-streamsPFE/
├── docker-compose.yml          # All service definitions
├── init-db/
│   ├── 01-schema.sql          # Database schema
│   ├── 02-seed-data.sql       # Restaurants, cities, users
│   └── 03-analytics-tables.sql # Feature stores, metrics tables
├── debezium/
│   ├── connectors/            # CDC connector configs
│   └── register_connectors.sh # Auto-register script
├── kafka/
│   ├── topics/                
│   └── kafka-setup.sh         # Topic creation
├── frontend/                   # React app
├── webapi/                    # FastAPI backend
├── notifier/                  # Kafka → WebSocket bridge
├── data_generation/           # Order generator
└── dags/                      # Airflow workflows
```

### PostgreSQL Setup

PostgreSQL runs with logical replication enabled (required for Debezium CDC):
```yaml
postgres:
  image: postgres:16.0
  environment:
    POSTGRES_DB: food_delivery
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
  command: 
    - "postgres"
    - "-c" 
    - "wal_level=logical"  # This is critical for CDC
  volumes:
    - ./init-db:/docker-entrypoint-initdb.d
    - postgres_data:/var/lib/postgresql/data
  ports:
    - "5432:5432"
```

Database initialization runs automatically on first startup through the `init-db/` scripts.

### Kafka Configuration
```yaml
kafka:
  image: confluentinc/cp-kafka:7.6.1
  environment:
    KAFKA_BROKER_ID: 1
    KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:9093
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    KAFKA_LOG_RETENTION_MS: 604800000  # Keep messages for 7 days
  ports:
    - "9092:9092"
    - "9093:9093"
```

Topics are created automatically via `kafka/kafka-setup.sh` on startup.

## CDC Configuration

### How Debezium Works Here

Debezium connects to PostgreSQL's replication slot and streams every INSERT, UPDATE, DELETE as a Kafka message. I've configured connectors for:
- Orders table
- Order reviews
- Weather conditions

### Connector Configuration

Example for orders table:
```json
{
  "name": "postgres-orders-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "postgres",
    "database.password": "postgres",
    "database.dbname": "food_delivery",
    "database.server.name": "postgres-orders",
    "table.include.list": "public.orders",
    "plugin.name": "pgoutput",
    "slot.name": "orders_slot",
    "publication.name": "orders_publication",
    "time.precision.mode": "adaptive_time_microseconds",
    "snapshot.mode": "always"
  }
}
```

### Register Connectors

Automatic (on startup):
```bash
./debezium/register_connectors.sh
```

Manual registration:
```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @debezium/connectors/orders-connector.json
```

Check status:
```bash
curl http://localhost:8083/connectors/postgres-orders-connector/status | jq
```

### Kafka Topics

Debezium auto-creates topics for each table:
- `postgres-orders-.public.orders`
- `postgres-order_reviews-.public.order_reviews`
- `postgres-weather_conditions-.public.weather_conditions`

I also manually create topics for processed events:
- `orders_enriched_weather` (orders + weather data)
- `new_orders_for_prediction` (new orders needing ETA prediction)
- `courier_features_live` (compacted feature store)
- `restaurant_features_live` (compacted feature store)

Topic configuration:
```bash
docker exec kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic orders_enriched_weather \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000
```

Feature store topics use compaction to keep only latest values:
```bash
docker exec kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic courier_features_live \
  --partitions 1 \
  --replication-factor 1 \
  --config cleanup.policy=compact \
  --config min.compaction.lag.ms=60000
```

## Web Application

### Frontend (React)

The dashboard is built with React 18 and uses WebSockets for live updates. No polling needed.

**Main pages:**
- **Overview** - Real-time KPIs, recent alerts, city-level metrics
- **Dashboards** - Embedded Superset charts
- **Dynamic SLA** - ML-powered SLA monitoring with violation alerts
- **Weather Insights** - Delivery time analysis by weather conditions
- **Routes** - Interactive Leaflet map showing active deliveries
- **Scenarios** - Controls to simulate rain, promotions, system outages
- **Replay** - Historical city pressure heatmap
- **Activity Log** - System event audit trail

**Development:**
```bash
cd frontend
npm install
npm start
```

**WebSocket integration:**
```javascript
// frontend/src/hooks/useWebSocket.js
import { useEffect, useState } from 'react';

export const useWebSocket = (url) => {
  const [messages, setMessages] = useState([]);
  const [ws, setWs] = useState(null);

  useEffect(() => {
    const socket = new WebSocket(url);
    
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMessages(prev => [...prev.slice(-11), data]);
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    setWs(socket);
    return () => socket.close();
  }, [url]);

  return { messages, ws };
};
```

Usage in components:
```javascript
const { messages } = useWebSocket('ws://localhost:8000/ws');

// messages automatically update when new events arrive
```

### Backend (FastAPI)

The API serves three purposes:
1. REST endpoints for historical data queries
2. WebSocket server for live updates
3. Internal broadcast endpoint for the notifier service

**Key endpoints:**
```python
# webapi/main.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncpg

app = FastAPI(title="Flavor Trend API")

# Health check
@app.get("/api/health")
async def health():
    return {"status": "healthy"}

# City KPIs
@app.get("/api/kpi/cities")
async def get_city_kpis(time_range: str = "1h"):
    async with request.app.state.pool.acquire() as conn:
        result = await conn.fetch("""
            SELECT city_id, COUNT(*) as orders, AVG(delivery_time) 
            FROM orders 
            WHERE created_at > NOW() - INTERVAL '1 hour'
            GROUP BY city_id
        """)
        return result

# SLA violations
@app.get("/api/sla/violations")
async def get_sla_violations(limit: int = 100):
    # Query recent SLA violations
    pass

# WebSocket for real-time updates
connections = set()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        pass
    finally:
        connections.remove(websocket)

# Internal endpoint for notifier service
@app.post("/internal/broadcast")
async def broadcast(message: dict):
    for ws in connections.copy():
        try:
            await ws.send_json(message)
        except:
            connections.remove(ws)
```

**Database connection pool:**
```python
# webapi/database.py
import asyncpg

async def create_pool():
    return await asyncpg.create_pool(
        host="postgres",
        port=5432,
        database="food_delivery",
        user="postgres",
        password="postgres",
        min_size=5,
        max_size=20
    )
```

**Run locally:**
```bash
cd webapi
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Notifier Service

This bridges Kafka and WebSocket. It consumes events from Kafka and pushes them to connected browsers through the FastAPI WebSocket server.
```python
# notifier/notifier.py
from kafka import KafkaConsumer
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

consumer = KafkaConsumer(
    'sla_violations',
    'dynamic_sla_violations',
    'eta_predictions',
    'courier_features_live',
    'restaurant_features_live',
    bootstrap_servers='kafka:9092',
    group_id='notifier-service',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='latest'
)

logger.info("Notifier service started, listening to Kafka topics...")

for message in consumer:
    try:
        # Forward to WebAPI for broadcast
        requests.post(
            'http://webapi:8000/internal/broadcast',
            json={
                'topic': message.topic,
                'data': message.value
            },
            timeout=2
        )
    except Exception as e:
        logger.error(f"Failed to broadcast message: {e}")
```

## Data Generator

The generator creates realistic order patterns with temporal variations.

**What it simulates:**
- Rush hours (12-2 PM, 7-9 PM)
- Weekend surge (+10%)
- Weather-dependent order rates
- Geographic distribution based on restaurant ratings
- Two-stage order lifecycle (placement → completion after 15-45 min)
- Courier routes with actual street paths
- Customer reviews (70% of completed orders)

**Running the generator:**
```bash
cd data_generation
pip install -r requirements.txt
python generator.py
```

**Configuration:**
```python
# data_generation/config.py
ORDER_RATE_BASE = 15  # orders per minute baseline
ORDER_RATE_RUSH_MULTIPLIER = 1.3  # +30% during rush hours
ORDER_RATE_WEEKEND_MULTIPLIER = 1.1
REVIEW_PROBABILITY = 0.7
WEATHER_UPDATE_INTERVAL = 300  # 5 minutes
```

**Scenario injection:**

From the React UI, you can trigger scenarios:
```python
POST /api/scenarios/rain
{
  "duration_minutes": 30,
  "intensity": "heavy"
}
```

The generator reads from `simulation_flags` table (10-second TTL) and adjusts behavior accordingly.

## Orchestration

### Airflow DAGs

Three main workflows:

**1. `realtime_pipeline.py` - Startup orchestration**
```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.http_sensor import HttpSensor
from datetime import datetime

with DAG(
    'realtime_pipeline',
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
    catchup=False
) as dag:

    # Wait for Flink to be ready
    check_flink = HttpSensor(
        task_id='check_flink_jobmanager',
        http_conn_id='flink',
        endpoint='/jobs/overview',
        timeout=300,
        poke_interval=10
    )

    # Start data generator
    start_generator = BashOperator(
        task_id='start_data_generator',
        bash_command='docker exec -d generator python generator.py'
    )

    # Submit Flink jobs
    submit_flink_jobs = BashOperator(
        task_id='submit_flink_jobs',
        bash_command='''
        docker exec jobmanager flink run -d \
          -c com.flavortrend.jobs.FlinkStreamingJob \
          /opt/flink/usrlib/job.jar
        '''
    )

    check_flink >> start_generator >> submit_flink_jobs
```

**2. `teardown_pipeline.py` - Graceful shutdown**

Stops generator, cancels Flink jobs, flushes Kafka offsets.

**3. `ml_retraining.py` - Weekly model updates**

Pulls last week's data, retrains ETA prediction model, registers in MLflow.

**Trigger manually:**
```bash
docker exec airflow-scheduler airflow dags trigger realtime_pipeline
```

## Monitoring

### Kafka Control Center

http://localhost:9021

Monitor topic throughput, consumer lag, broker health. Inspect individual messages.

### Debezium UI

http://localhost:8080

Check connector status, CDC lag, snapshot progress. Restart failed connectors.

### Service Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f webapi
docker-compose logs -f notifier
docker-compose logs -f generator
docker-compose logs -f debezium

# Filter by level
docker-compose logs -f | grep ERROR
```

## Troubleshooting

### Services won't start
```bash
# Check what's failing
docker-compose logs -f

# Restart specific service
docker-compose restart kafka

# Full reset
docker-compose down
docker-compose up -d
```

### Debezium connector failed
```bash
# Check status
curl http://localhost:8083/connectors/postgres-orders-connector/status | jq

# Common fix: delete and recreate
curl -X DELETE http://localhost:8083/connectors/postgres-orders-connector
./debezium/register_connectors.sh
```

### No data in dashboard
```bash
# Check generator is running
docker-compose logs generator | tail -20

# Check Flink jobs are running
curl http://localhost:8081/jobs

# Check WebSocket connection
# Open browser console on http://localhost:3000
# Should see WebSocket connected message

# Manually test WebSocket
npm install -g wscat
wscat -c ws://localhost:8000/ws
```

### Kafka consumer lag
```bash
# List consumer groups
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --list

# Check lag for specific group
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group flink-streaming-job \
  --describe
```

### Database connection issues
```bash
# Check Postgres is up
docker exec postgres pg_isready

# Verify WAL level
docker exec postgres psql -U postgres -d food_delivery \
  -c "SHOW wal_level;"
# Must return "logical"

# If wrong, edit docker-compose.yml and restart:
docker-compose down
docker-compose up -d postgres
```

### Out of memory

Increase Docker Desktop RAM allocation:
- Docker Desktop → Settings → Resources → Memory
- Set to at least 16GB
- Restart Docker

## Testing the Pipeline

End-to-end verification:
```bash
# 1. Start everything
docker-compose up -d

# 2. Wait for initialization
sleep 180

# 3. Trigger pipeline
docker exec airflow-scheduler airflow dags trigger realtime_pipeline

# 4. Check Kafka has data
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic postgres-orders-.public.orders \
  --from-beginning --max-messages 5

# 5. Check database has orders
docker exec postgres psql -U postgres -d food_delivery \
  -c "SELECT COUNT(*) FROM orders WHERE created_at > NOW() - INTERVAL '5 minutes';"

# 6. Open dashboard
open http://localhost:3000

# Should see real-time updates
```

## Related Work

The stream processing layer lives in a separate repository:
- [flavor-trend-flink-processor](https://github.com/mahmoudgribej1/flavor-trend-flink-processor)

It contains all Flink jobs for data enrichment, feature engineering, and ML inference.

## About This Project

Built as my final year engineering project at ESPRIT (2024-2025).

The goal was to build a real-time analytics platform from scratch using modern data engineering tools. I learned a ton about stream processing, CDC, event-driven architecture, and building scalable systems.

**Author:** Mahmoud Gribej  
**Contact:** mahmoudgribej7@gmail.com  
**LinkedIn:** [mahmoud-gribej-70bb24265](https://linkedin.com/in/mahmoud-gribej-70bb24265)  
**GitHub:** [@mahmoudgribej1](https://github.com/mahmoudgribej1)

## License

This project is part of an academic engineering thesis at ESPRIT.

---

If you find this useful or interesting, feel free to star the repo or reach out with questions.
