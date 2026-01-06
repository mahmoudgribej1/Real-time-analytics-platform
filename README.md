# 🌊 Flavor Trend - Streaming Infrastructure & Web Platform

> Complete infrastructure, CDC configuration, and web application for real-time food delivery analytics


## 📋 Table of Contents
- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Components](#components)
- [Quick Start](#quick-start)
- [Infrastructure Setup](#infrastructure-setup)
- [CDC Configuration](#cdc-configuration)
- [Web Application](#web-application)
- [Data Generator](#data-generator)
- [Orchestration](#orchestration)
- [Monitoring](#monitoring)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This repository contains the complete infrastructure and application layer for **Flavor Trend**, a real-time food delivery analytics platform. It includes:

- 🐳 **Docker Compose orchestration** for 13+ services
- 📡 **Debezium CDC configuration** for PostgreSQL
- 📨 **Kafka topic management** and configuration
- 🌐 **React frontend** with real-time WebSocket updates
- ⚡ **FastAPI backend** with async PostgreSQL connections
- 🔔 **WebSocket notification service** bridging Kafka to UI
- 🎲 **Synthetic data generator** with realistic patterns
- 🔄 **Apache Airflow DAGs** for automation
- 📊 **Apache Superset** dashboards
- 🗄️ **PostgreSQL schema** and migrations

## 🏗️ System Architecture

![image alt](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/e4fb2a5d47d39043d6c06df83e3b8aa2f1cf567b/sysArchi.png)

## 🔧 Components

### Infrastructure Layer
- **PostgreSQL 16.0** - Operational + analytical databases
- **Apache Kafka 7.6.1** - Event streaming backbone
- **Zookeeper** - Kafka cluster coordination
- **Debezium 2.5.0** - Change Data Capture
- **Apache Flink 1.18.0** - Stream processing (from other repo)

### Orchestration Layer
- **Apache Airflow 2.9.2** - Workflow automation
- **MLflow 2.14.1** - ML experiment tracking

### Application Layer
- **React 18.0** - Frontend SPA
- **FastAPI** - Backend REST API + WebSocket
- **Notifier Service** - Kafka-to-WebSocket bridge
- **Apache Superset 2.1.3** - BI dashboards

### Tools & Monitoring
- **Confluent Control Center** - Kafka monitoring
- **Debezium UI** - CDC connector management
- **pgAdmin** - Database administration

## 🚀 Quick Start

### Prerequisites
- Docker Desktop 24.0+ with 16GB RAM allocated
- Docker Compose 3.8+
- 20GB free disk space

### One-Command Startup
```bash
git clone https://github.com/mahmoudgribej1/flavor-trend-streamsPFE.git
cd flavor-trend-streamsPFE
docker-compose up -d
```

### Access Services
| Service | URL | Credentials |
|---------|-----|-------------|
| Flink JobManager | http://localhost:8081 | - |
| Kafka Control Center | http://localhost:9021 | - |
| Debezium UI | http://localhost:8080 | - |
| Airflow | http://localhost:8082 | airflow / airflow |
| Superset | http://localhost:8088 | admin / admin |
| MLflow | http://localhost:5000 | - |
| Frontend | http://localhost:3000 | - |
| Backend API | http://localhost:8000/docs | - |

### Initialize Platform
```bash
# Option 1: Manual Airflow DAG trigger
# Go to http://localhost:8082 → Trigger "realtime_pipeline"

# Option 2: Via Airflow CLI
docker exec airflow-scheduler airflow dags trigger realtime_pipeline
```

## 🐳 Infrastructure Setup

### Docker Compose Structure
```
flavor-trend-streamsPFE/
├── docker-compose.yml          # Main orchestration file
├── init-db/
│   ├── 01-schema.sql          # Database schema
│   ├── 02-seed-data.sql       # Initial data
│   └── 03-analytics-tables.sql
├── debezium/
│   ├── connectors/            # Connector configs
│   └── register_connectors.sh
├── kafka/
│   ├── topics/                # Topic creation scripts
│   └── kafka-setup.sh
├── frontend/                   # React application
├── webapi/                    # FastAPI backend
├── notifier/                  # Kafka-WebSocket bridge
├── data_generation/           # Synthetic data generator
└── dags/                      # Airflow DAGs
```

### Services Configuration

#### PostgreSQL
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
    - "wal_level=logical"  # Required for CDC
  volumes:
    - ./init-db:/docker-entrypoint-initdb.d
    - postgres_data:/var/lib/postgresql/data
  ports:
    - "5432:5432"
```

#### Kafka
```yaml
kafka:
  image: confluentinc/cp-kafka:7.6.1
  environment:
    KAFKA_BROKER_ID: 1
    KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:9093
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    KAFKA_LOG_RETENTION_MS: 604800000  # 7 days
  ports:
    - "9092:9092"
    - "9093:9093"
```

#### Debezium (Kafka Connect)
```yaml
debezium:
  image: debezium/connect:2.5.0
  environment:
    BOOTSTRAP_SERVERS: kafka:9092
    GROUP_ID: debezium-cluster
    CONFIG_STORAGE_TOPIC: debezium_configs
    OFFSET_STORAGE_TOPIC: debezium_offsets
    STATUS_STORAGE_TOPIC: debezium_status
  ports:
    - "8083:8083"
```

## 📡 CDC Configuration

### Debezium Connectors

#### Orders Connector
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

#### Register All Connectors
```bash
# Via script
./debezium/register_connectors.sh

# Or manually via REST API
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @debezium/connectors/orders-connector.json
```

### Kafka Topics

#### Topic Creation Script
```bash
#!/bin/bash
# kafka/kafka-setup.sh

KAFKA_CONTAINER="kafka"

# CDC Topics (auto-created by Debezium)
# - postgres-orders-.public.orders
# - postgres-order_reviews-.public.order_reviews
# - postgres-weather_conditions-.public.weather_conditions

# Event Topics
docker exec $KAFKA_CONTAINER kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic orders_enriched_weather \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

docker exec $KAFKA_CONTAINER kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic new_orders_for_prediction \
  --partitions 4 \
  --replication-factor 1

# Compacted Feature Store Topics
docker exec $KAFKA_CONTAINER kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic courier_features_live \
  --partitions 1 \
  --replication-factor 1 \
  --config cleanup.policy=compact \
  --config min.compaction.lag.ms=60000

docker exec $KAFKA_CONTAINER kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic restaurant_features_live \
  --partitions 1 \
  --replication-factor 1 \
  --config cleanup.policy=compact
```

## 🌐 Web Application

### Frontend (React)

**Tech Stack:** React 18, React Router, Leaflet, Recharts, WebSocket

**Key Pages:**
- **Overview** - Real-time KPIs, alerts, city pressure
- **Dashboards** - Embedded Superset BI dashboards
- **Dynamic SLA** - ML-based SLA monitoring
- **Weather Insights** - Delivery time analysis by weather
- **Routes** - Interactive map with delivery routes
- **Scenarios** - Simulation controls (rain, promotions, outages)
- **Replay** - Historical city pressure visualization
- **Activity Log** - Audit trail of system actions

**Development:**
```bash
cd frontend
npm install
npm start  # http://localhost:3000
```

**Production Build:**
```bash
npm run build
# Served via nginx in Docker
```

**WebSocket Integration:**
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
      setMessages(prev => [...prev.slice(-11), data]); // Keep last 12
    };

    setWs(socket);
    return () => socket.close();
  }, [url]);

  return { messages, ws };
};
```

### Backend (FastAPI)

**Tech Stack:** FastAPI, AsyncPG, WebSocket, Pydantic

**Key Endpoints:**
```python
# webapi/main.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncpg

app = FastAPI(title="Flavor Trend API")

# REST Endpoints
@app.get("/api/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/kpi/cities")
async def get_city_kpis(time_range: str = "1h"):
    # Query PostgreSQL for city KPIs
    pass

@app.get("/api/sla/violations")
async def get_sla_violations(limit: int = 100):
    # Query SLA violations
    pass

@app.get("/api/sentiment/restaurants")
async def get_restaurant_sentiment():
    # Query restaurant sentiment
    pass

# WebSocket for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    finally:
        connections.remove(websocket)
```

**AsyncPG Connection Pool:**
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

**Run Development Server:**
```bash
cd webapi
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Notifier Service (Kafka-WebSocket Bridge)

**Purpose:** Consumes Kafka topics and broadcasts to WebSocket clients

```python
# notifier/notifier.py
from kafka import KafkaConsumer
import requests
import json

consumer = KafkaConsumer(
    'sla_violations',
    'dynamic_sla_violations',
    'eta_predictions',
    'courier_features_live',
    'restaurant_features_live',
    bootstrap_servers='kafka:9092',
    group_id='notifier-service',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

for message in consumer:
    # Broadcast to WebSocket
    requests.post(
        'http://webapi:8000/internal/broadcast',
        json=message.value
    )
```

## 🎲 Data Generator

**Location:** `data_generation/generator.py`

**Architecture:** Multi-threaded Python application

### Features
- ✅ Realistic temporal patterns (rush hours, weekends)
- ✅ Geographic distribution (rating-weighted restaurants)
- ✅ Weather impact simulation
- ✅ Two-stage order lifecycle (placement → completion)
- ✅ Route generation with GeoJSON output
- ✅ Scenario controls (rain, promotions, outages)

### Running Generator
```bash
cd data_generation
pip install -r requirements.txt
python generator.py
```

### Configuration
```python
# data_generation/config.py
ORDER_RATE_BASE = 15  # orders per minute
ORDER_RATE_RUSH_MULTIPLIER = 1.3  # +30% during rush
ORDER_RATE_WEEKEND_MULTIPLIER = 1.1  # +10% on weekends
REVIEW_PROBABILITY = 0.7  # 70% of orders get reviewed
WEATHER_UPDATE_INTERVAL = 300  # 5 minutes
```

### Scenario Injection
```python
# Via API (from React UI)
POST /api/scenarios/rain
{
  "duration_minutes": 30,
  "intensity": "heavy"
}

# Generator reads from simulation_flags table (10s TTL)
SELECT * FROM ops.simulation_flags WHERE active = true
```

## 🔄 Orchestration (Apache Airflow)

### DAGs Location
```
dags/
├── realtime_pipeline.py    # Main startup DAG
├── teardown_pipeline.py    # Graceful shutdown DAG
└── ml_retraining.py        # Weekly ML retraining
```

### Realtime Pipeline DAG
```python
# dags/realtime_pipeline.py
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.http_sensor import HttpSensor
from datetime import datetime

with DAG(
    'realtime_pipeline',
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,  # Manual trigger
    catchup=False
) as dag:

    check_flink = HttpSensor(
        task_id='check_flink_jobmanager',
        http_conn_id='flink',
        endpoint='/jobs/overview',
        timeout=300,
        poke_interval=10
    )

    start_generator = BashOperator(
        task_id='start_data_generator',
        bash_command='docker exec -d generator python generator.py'
    )

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

### Trigger DAG
```bash
# Via Airflow UI
http://localhost:8082 → DAGs → realtime_pipeline → Trigger

# Via CLI
docker exec airflow-scheduler airflow dags trigger realtime_pipeline
```

## 📊 Monitoring

### Kafka Control Center
Access at `http://localhost:9021`

**Monitor:**
- Topic throughput
- Consumer lag
- Broker health
- Message inspection

### Debezium UI
Access at `http://localhost:8080`

**Monitor:**
- Active connectors
- CDC lag
- Snapshot progress
- Error logs

### Application Logs
```bash
# View all service logs
docker-compose logs -f

# Specific service
docker-compose logs -f webapi
docker-compose logs -f notifier
docker-compose logs -f generator
```

## 🔐 Environment Variables

### Required Variables
```bash
# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=food_delivery
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Airflow
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5000

# API
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=["http://localhost:3000"]
```

### .env File
```bash
# Copy example
cp .env.example .env

# Edit with your values
nano .env
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Services Not Starting
```bash
# Check logs
docker-compose logs -f [service-name]

# Restart specific service
docker-compose restart [service-name]

# Full restart
docker-compose down
docker-compose up -d
```

#### 2. Debezium Connector Failed
```bash
# Check connector status
curl http://localhost:8083/connectors/postgres-orders-connector/status

# Delete and recreate
curl -X DELETE http://localhost:8083/connectors/postgres-orders-connector
./debezium/register_connectors.sh
```

#### 3. Kafka Consumer Lag
```bash
# Check consumer groups
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --list

# Check specific group lag
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group flink-streaming-job \
  --describe
```

#### 4. WebSocket Connection Fails
```bash
# Check notifier service
docker-compose logs -f notifier

# Check WebAPI
docker-compose logs -f webapi

# Test WebSocket connection
wscat -c ws://localhost:8000/ws
```

#### 5. Database Connection Issues
```bash
# Verify PostgreSQL is accepting connections
docker exec postgres pg_isready

# Check WAL level
docker exec postgres psql -U postgres -d food_delivery \
  -c "SHOW wal_level;"
# Should return "logical"
```

## 🧪 Testing

### End-to-End Test
```bash
# 1. Start all services
docker-compose up -d

# 2. Wait for initialization (2-3 minutes)
sleep 180

# 3. Trigger Airflow DAG
docker exec airflow-scheduler airflow dags trigger realtime_pipeline

# 4. Verify data flow
# Check Kafka topics
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic postgres-orders-.public.orders \
  --from-beginning --max-messages 10

# 5. Open frontend
open http://localhost:3000

# 6. Verify real-time updates appear on dashboard
```

## 📝 Development

### Adding New Kafka Topic
```bash
# 1. Create topic
docker exec kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic new_topic_name \
  --partitions 3 \
  --replication-factor 1

# 2. Add to kafka-setup.sh for persistence
echo "# New topic config" >> kafka/kafka-setup.sh
```

### Adding New API Endpoint
```python
# webapi/main.py
@app.get("/api/new-endpoint")
async def new_endpoint():
    async with request.app.state.pool.acquire() as conn:
        result = await conn.fetch("SELECT * FROM table")
        return result
```

## 📚 Related Repositories

- [flavor-trend-flink-processor](https://github.com/mahmoudgribej1/flavor-trend-flink-processor) - Flink stream processing jobs

## 👨‍💻 Author

**Mahmoud Gribej**  
- GitHub: [@mahmoudgribej1](https://github.com/mahmoudgribej1)
- LinkedIn: [Mahmoud Gribej](https://linkedin.com/in/mahmoud-gribej-70bb24265)
- Email: mahmoudgribej7@gmail.com


## 📄 License

This project is part of a final year engineering project at ESPRIT.

---

⭐ If you find this project useful, please consider giving it a star!
