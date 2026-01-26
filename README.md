# Flavor Trend: Real-Time Analytics Platform

[![Apache Flink](https://img.shields.io/badge/Apache%20Flink-1.18.0-E6526F?logo=apache-flink)](https://flink.apache.org/)
[![Apache Kafka](https://img.shields.io/badge/Apache%20Kafka-7.6.1-231F20?logo=apache-kafka)](https://kafka.apache.org/)
[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-2.9-017CEE?logo=apache-airflow)](https://airflow.apache.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.0-4169E1?logo=postgresql)](https://www.postgresql.org/)
[![React](https://img.shields.io/badge/React-18.0-61DAFB?logo=react)](https://react.dev/)

Production-grade streaming analytics platform for food delivery operations. Processes **10,000+ orders/hour** with **sub-second latency** using Kappa architecture, exactly-once semantics, and real-time ML inference.

**Engineering Thesis Project** | ESPRIT 2024-2025 | [Mahmoud Gribej](https://github.com/mahmoudgribej1)

---

## System Architecture

![System Architecture](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/2843f0a39ba3be417e49c12b75a6acd2298cef28/images/sysArchi.png)
*Complete six-layer Kappa architecture from CDC ingestion through ML inference to real-time presentation*

### Architecture Layers

**1. Data Ingestion** - Debezium CDC captures PostgreSQL changes with <50ms latency  
**2. Event Streaming** - Kafka handles 13 topics with exactly-once delivery  
**3. Stream Processing** - 8 concurrent Flink jobs with exactly-once semantics  
**4. Machine Learning** - Real-time feature engineering + LightGBM inference  
**5. Storage** - PostgreSQL (analytics), Kafka (event log), RocksDB (state)  
**6. Presentation** - React dashboard + Superset BI

### Key Design Decisions

*Kappa Architecture*
![Kappa](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/a3fd21f25a4d1a315e8d5758d55c9cf386bda599/images/kappa.png)

**Kappa Over Lambda** - Single stream processing path eliminates batch layer complexity and code duplication

**Log-Based CDC** - Asynchronous WAL monitoring with <1% database overhead vs. polling or triggers

**Temporal Joins** - `FOR SYSTEM_TIME AS OF` ensures point-in-time correctness for feature consistency

**Compacted Kafka Topics** - Real-time feature store with upsert semantics maintains latest values per key

---

## Core Components

### Change Data Capture

![Debezium Connectors](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/a3fd21f25a4d1a315e8d5758d55c9cf386bda599/images/Screenshot%202026-01-23%20011551.png)
*Active CDC connectors streaming orders, reviews, and weather updates to Kafka*

**Architecture:**
- PostgreSQL configured with `wal_level=logical` for replication slot access
- Debezium connectors monitor 3 high-velocity tables (orders, reviews, weather)
- Events published to Kafka with full before/after state and transaction metadata
- Exactly-once delivery through Kafka transactions

**Performance:** <50ms CDC capture latency, <1% PostgreSQL CPU overhead

### Stream Processing

![Flink Jobs](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/a3fd21f25a4d1a315e8d5758d55c9cf386bda599/images/flink_jobs.png)
*Flink JobManager showing 8 concurrent jobs with 100% checkpoint success rate*

**Job Architecture:**

| Job | Purpose | Processing Pattern |
|-----|---------|-------------------|
| FlinkStreamingJob | City-level KPIs | 1-min tumbling windows |
| FlinkSlaMonitor | Static SLA violations | Event-driven filtering |
| SentimentAnalyzer | Review aggregation | 5-min tumbling windows |
| WeatherAwareOrderAnalysis | Order enrichment | Temporal + JDBC joins |
| CourierActivityJob | Courier features | Stateful computation |
| RestaurantStatusJob | Restaurant features | 1-hour sliding windows |
| eta_prediction_job | ML inference | Temporal joins + UDF |
| DynamicSlaMonitor | ML-based SLA | Stream-stream joins |

**Key Patterns:**
- **Temporal Joins** - Point-in-time feature lookups for ML consistency
- **Stateful Processing** - RocksDB backend for large state management
- **Event-Time Processing** - Watermarks handle out-of-order events
- **Exactly-Once** - Checkpointing ensures no data loss or duplication

### Machine Learning Pipeline

![MLflow Tracking](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/a3fd21f25a4d1a315e8d5758d55c9cf386bda599/images/mlflowtracking.png)
*Experiment tracking showing model performance and artifacts*

**Training:**
- Historical data extraction from enriched orders table
- Feature engineering: temporal, weather, contextual, entity features
- Optuna hyperparameter optimization (50 trials)
- LightGBM model (MAE: 12.28 minutes)
- MLflow tracking and model registry

**Inference:**
- Triple temporal join: order + restaurant features + courier features
- Embedded model pattern: <100ms latency per prediction
- PyFlink UDF with cached model loading
- Output to Kafka for downstream consumption

**Feature Store:**
- Kafka compacted topics (`courier_features_live`, `restaurant_features_live`)
- Upsert semantics maintain latest values
- Training-serving consistency through identical Flink logic

### Superset live dashboards

![Orders Dashboard](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/dashboard%201%20.jpg)
![SLA violations Dashboard](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/real-time-delivery-sla-monitor-2025-05-29T02-28-06.184Z.jpg)

### Web Application
*Overview Page*
![Overview](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/overview.png)
![Live Restaurant and Courier tracking](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/Screenshot%202026-01-23%20013755.png)
![Live Sentiment Analysis](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/sentimentpanel.png)
![SLA Alerts](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/sla.png)
![Top Restaurants and Dishes of the day](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/toptoday.png)

*Dashboards Page*
![Superset Embedded Dashboards](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/dashboards.png)

*Dynamic SLA violations Tracking Page*
![Dynamic SLA tracking](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/dynamicslam.png)

*Live Weather Impact Page*
![Weather Page](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/weather.png)

*Routes Page*
[!Routes](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/routess.png)

*Scenario Page*
![Scenarios](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/scenarios.png)

*Replay Page*
![Replay](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/2ee63d202e72f2b947c2561cc075b1cde3341cae/replayy.png)

**Backend (FastAPI):**
- Async REST API with AsyncPG connection pooling
- WebSocket server for real-time notifications
- Endpoints: KPIs, violations, sentiment, routes, predictions

*API Architecture*
![API](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/apiarchitecturee.png)
**Notifier Service:**
- Kafka consumer bridging to WebSocket
- Broadcasts events: SLA violations, predictions, feature updates
- Handles connection lifecycle and reconnection

**Frontend (React):**
- Overview: Real-time KPIs, alerts, city pressure, sentiment
- Dashboards: Embedded Superset BI charts
- Dynamic SLA: ML predictions vs actuals with violations
- Routes: GPS visualization with Leaflet
- Scenarios: Simulation controls (rain, promotions, outages)
- Replay: Historical city pressure analysis

---

## Performance Metrics

![Checkpoint Dashboard](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/checkpoints.png)
*Checkpoint metrics showing 100% success rate and 121ms average duration*

### System Performance

| Metric | Value |
|--------|-------|
| **End-to-End Latency** | ~3 seconds (order → prediction → UI) |
| **CDC Capture** | <50ms median |
| **Flink Processing** | Sub-second |
| **ML Inference** | <100ms per prediction |
| **Throughput** | 10,000+ orders/hour |
| **Checkpoint Success** | 100% |
| **Checkpoint Duration** | 121ms average |
| **State Size** | 2.24 MB (8 jobs combined) |

### Scalability

- **Horizontal:** Parallelism tuning per job (currently 1-4 slots)
- **Vertical:** RocksDB state backend handles large state beyond heap
- **Database:** <1% CPU overhead from CDC, AsyncPG pooling (5-20 connections)

---

## Deployment

### Infrastructure

**13 Containerized Services:**

- **Core:** PostgreSQL, Kafka, ZooKeeper, Kafka Connect, Debezium
- **Processing:** Flink (JobManager + TaskManager), Data Generator
- **Orchestration:** Airflow (Scheduler + Webserver), MLflow
- **Presentation:** Superset, FastAPI, Notifier, React Frontend
- **Monitoring:** Control Center, Debezium UI

**Single-Command Deployment:**
```bash
docker-compose up -d
docker exec airflow-scheduler airflow dags trigger realtime_pipeline
```

### Orchestration

**Startup Pipeline (Airflow DAG):**
![pipelineDAG](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/pipelineDAG.png)
2. Start data generator
3. Submit Flink jobs in dependency order:
   - Group 1 (parallel): KPI, SLA, Sentiment
   - Group 2 (parallel): Enrichment, Features
   - Sequential: ML Inference → Dynamic SLA

**Teardown Pipeline:**
![teardownDAG](https://github.com/mahmoudgribej1/Real-time-analytics-platform/blob/7f899524ad8f329c76e553f5521039a3cf564523/images/pipelineteardownDAG.png)
1. Cancel all Flink jobs via REST API
2. Stop data generator
3. Flush Kafka consumer offsets

---

## Project Structure

```
flavor-trend-streamsPFE/
├── dags/                      # Airflow orchestration
├── data_generation/           # Synthetic order generator
├── debezium/connectors/       # CDC configurations
├── init-db/                   # Database schemas
├── kafka/                     # Topic setup scripts
├── frontend/                  # React application
├── webapi/                    # FastAPI backend
├── notifier/                  # Kafka-WebSocket bridge
└── docker-compose.yml         # Service orchestration
```

**Related Repository:**  
[Flink Stream Processor](https://github.com/mahmoudgribej1/flavor-trend-flink-processor) - All 8 Flink jobs, PyFlink ML inference, and training pipeline

---

## Monitoring

**Flink Web UI** (localhost:8081) - Job status, checkpoints, backpressure  
**Kafka Control Center** (localhost:9021) - Topic metrics, consumer lag  
**MLflow** (localhost:5000) - Experiment tracking, model registry  
**Superset** (localhost:8088) - BI dashboards, SQL queries  
**Airflow** (localhost:8082) - DAG execution, task logs  
**Debezium UI** (localhost:8080) - Connector status, CDC lag

---

## Technology Stack

**Stream Processing:** Apache Flink 1.18.0, Apache Kafka 7.6.1, Debezium 2.5.0  
**Storage:** PostgreSQL 16.0, RocksDB  
**ML:** PyFlink, LightGBM, MLflow 2.14.1, Optuna  
**Orchestration:** Apache Airflow 2.9.2, Docker Compose 3.8  
**Web:** React 18.0, FastAPI, WebSocket, Apache Superset 2.1.3

---

## Technical Achievements

 **Kappa Architecture** - Pure streaming approach with single processing logic  
 **Exactly-Once Semantics** - Distributed checkpointing across all components  
 **Event-Time Processing** - Watermarks handle out-of-order events correctly  
 **Temporal Joins** - Point-in-time correctness for ML feature consistency  
 **Real-Time ML** - <100ms inference with embedded model pattern  
 **100% Checkpoint Success** - Fault tolerance with automatic recovery  
 **Sub-Second Latency** - End-to-end processing in ~3 seconds  
 **Production Patterns** - State management, monitoring, automated deployment

---

## About

**Project:** Real-Time Decision Making Platform for Food Delivery Operations  
**Institution:** ESPRIT School of Engineering (2024-2025)  

**Author:** Mahmoud Gribej  
 mahmoudgribej7@gmail.com  
 [LinkedIn](https://linkedin.com/in/mahmoud-gribej-70bb24265)  
 [GitHub](https://github.com/mahmoudgribej1)

---

**License:** Academic thesis project - ESPRIT. All rights reserved.
