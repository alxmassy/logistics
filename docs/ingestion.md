# System Context: Resilient Logistics & Dynamic Supply Chain Optimization

## 1. Macro Architecture Overview
This system is a high-throughput, low-latency supply chain optimization engine designed to preemptively detect transit disruptions and execute dynamic rerouting. It operates on a strict reactive stream architecture, isolating deterministic threat prediction from heuristic LLM-based optimization.

**The Pipeline Pipeline:**
1.  **Ingestion:** FastAPI asynchronous producers push concurrent, high-volume mocked telemetry and external API threat data into Redpanda.
2.  **Prediction:** Apache Flink consumes Redpanda topics, strictly using Event-Time windowing to detect spatial-temporal collisions between shipments and threats.
3.  **Context Assembly:** Flink triggers an alert. The backend queries Redis for the shipment's "Blast Radius" (pre-computed alternative routes, cargo priority, SLA).
4.  **Optimization:** Context is injected into a Vertex AI (Gemini 1.5 Pro) zero-shot prompt. The LLM evaluates cost/time trade-offs and outputs a strict JSON reroute decision.
5.  **Execution Gateway:** A FastAPI rule engine scores the LLM output. Sub-threshold scores execute autonomously via background tasks; high-risk scores are pushed to a React frontend via WebSockets for human-in-the-loop approval.

---

## 2. Ingestion Phase: AI Agent Build Instructions

**Objective:** Build the FastAPI-based high-concurrency ingestion producers and the Redpanda topic initialization scripts. The code must be production-ready, modular, and optimized for I/O bounds.

### Technical Constraints & Tooling
* **Framework:** FastAPI. Use standard async/await for all I/O operations.
* **Validation:** Use Pydantic v2 strictly. No raw dict manipulation. Malformed JSON must be rejected at the edge.
* **Broker:** Redpanda (Kafka compatible). Use `confluent-kafka-python` or `aiokafka`.
* **CLI Tooling:** Implement a CLI interface (using `Typer` and `Rich`) to start/stop the mock generators and control the ingestion rate (messages/second). 
* **Time Handling:** Every payload must include an `event_time` timestamp (ISO 8601 UTC). Do not rely on processing time.

### Task 1: Redpanda Setup & Topic Partitioning
Write the initialization script to create the required Redpanda topics with specific partitions.
* **Topic 1:** `shipment-telemetry` (Partitioned by geographic zone or transport mode to ensure parallel downstream processing).
* **Topic 2:** `threat-signals` (For weather, traffic, and port congestion alerts).

### Task 2: Pydantic v2 Schemas
Define the strict schemas for the payloads.
* **ShipmentTelemetrySchema:** `shipment_id` (UUID), `current_lat_lon`, `destination_lat_lon`, `carrier`, `transport_mode` (Enum: SEA, AIR, ROAD), `priority_tier` (Enum: LOW, STANDARD, HIGH), `expected_eta`, `event_time`.
* **ThreatSignalSchema:** `threat_id`, `threat_type` (Enum: WEATHER, CONGESTION, INFRASTRUCTURE), `severity` (1-10), `impact_polygon` (Array of lat/lon coordinates), `event_time`.
* **PrecomputedRouteSchema (For Redis seeding):** `route_id`, `path_nodes`, `base_cost`, `estimated_transit_time`.

### Task 3: High-Throughput Mock Generator
Develop the asynchronous generator that simulates the "millions of shipments" and external threats.
* The generator must randomly alter coordinates along a trajectory to simulate movement.
* **Crucial Logic:** The generator must inject pre-computed alternative routes for each generated shipment into a Redis hash (`shipment_context:{shipment_id}`) *at the time of creation*. This bridges the gap caused by the lack of a dedicated Graph Database.
* Implement configurable failure injection (e.g., intentionally generating a weather threat polygon that intersects with a generated shipment's coordinates to test the Flink pipeline later).

### Task 4: FastAPI Producer Endpoints
Expose REST endpoints to manually inject data or trigger the generator, useful for the hackathon demo.
* `POST /ingest/telemetry`: Accepts a batch of telemetry payloads.
* `POST /ingest/threat`: Accepts manual threat injection.
* Ensure the producer client is instantiated at application startup (lifespan events) to avoid reconnect overhead per request.