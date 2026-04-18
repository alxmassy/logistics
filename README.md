# Logistics — Resilient Supply Chain Optimization Engine

High-throughput, low-latency supply chain optimization engine that preemptively detects transit disruptions and executes dynamic rerouting.

## Architecture

```
Ingestion (FastAPI) → Redpanda → Flink (Prediction) → Context Assembly (Redis)
                                                      → Vertex AI (Optimization)
                                                      → React Frontend (HITL)
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose

### 1. Start Infrastructure

```bash
docker compose -f infra/docker-compose.yml up -d
```

This starts:
- **Redpanda** — Kafka-compatible broker at `localhost:19092`
- **Redpanda Console** — Web UI at `http://localhost:8080`
- **Redis** — Cache at `localhost:6379`

### 2. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env if your ports differ from defaults
```

### 4. Create Topics

```bash
python -m services.ingestion topics
```

### 5. Verify Infrastructure

```bash
python -m services.ingestion health
```

## Usage

### CLI — Mock Data Generator

```bash
# Run generator for 60 seconds, 20 shipments, 50 msg/s
python -m services.ingestion generate --shipments 20 --rate 50 --duration 60

# Run indefinitely with failure injection disabled
python -m services.ingestion generate --no-inject-failures

# See all options
python -m services.ingestion generate --help
```

### CLI — API Server

```bash
python -m services.ingestion serve
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ingest/telemetry` | Batch ingest shipment telemetry |
| `POST` | `/ingest/threat` | Inject a single threat signal |

### Example — Manual Threat Injection

```bash
curl -X POST http://localhost:8000/ingest/threat \
  -H "Content-Type: application/json" \
  -d '{
    "threat_id": "550e8400-e29b-41d4-a716-446655440000",
    "threat_type": "WEATHER",
    "severity": 8,
    "impact_polygon": [
      {"lat": 30.0, "lon": 120.0},
      {"lat": 32.0, "lon": 120.0},
      {"lat": 32.0, "lon": 123.0}
    ],
    "event_time": "2026-04-16T12:00:00Z"
  }'
```

## Testing

```bash
pytest tests/ -v
```

## Project Structure

```
logistics/
├── services/ingestion/     # Ingestion service (FastAPI + CLI)
│   ├── api/                # FastAPI app, routes, dependencies
│   ├── generators/         # Mock data generators
│   ├── producers/          # Kafka producer service
│   ├── cli.py              # Typer CLI entrypoint
│   └── config.py           # pydantic-settings configuration
├── shared/schemas/         # Pydantic v2 schemas (shared across services)
├── infra/                  # Docker Compose, topic init scripts
├── tests/                  # pytest test suite
└── docs/                   # Architecture documentation
```

## For Other Teams

### Frontend

- Schemas are in `shared/schemas/` — use these as the source of truth for API contracts
- CORS is enabled on the API server
- WebSocket endpoints for real-time updates will be added in the Execution Gateway phase

### ML / Data Science

- Import schemas directly: `from shared.schemas import ShipmentTelemetrySchema`
- Redpanda topics use event-time semantics — always use `event_time`, never processing time
- Precomputed routes are in Redis under `shipment_context:{shipment_id}`
