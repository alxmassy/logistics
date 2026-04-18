# System Context: Prediction & Context Assembly Layer

## 1. Macro Architecture Checkpoint
Ingestion is active. Redpanda is buffering `shipment-telemetry` and `threat-signals`.
This phase builds the deterministic stream processing brain (Apache Flink) and the stateful context assembler (Redis + FastAPI). Flink executes the raw math; Redis provides the business context.

## 2. Prediction & Context Build Instructions

**Objective:** Build a PyFlink application for real-time spatial-temporal anomaly detection, and a FastAPI worker to assemble the "Blast Radius" context from Redis when an anomaly triggers.

### Technical Constraints & Tooling
* **Stream Processor:** PyFlink (`apache-flink`). PyFlink is mandated to maintain operational consistency with the existing Python/FastAPI environment. Do not use Java/Maven for this hackathon build.
* **State Store / KVS:** Redis (use standard async drivers).
* **Time Semantics:** Strict Event-Time processing with Bounded Out-of-Orderness Watermarks. Processing Time is forbidden.

### Task 1: PyFlink Stream Setup & Watermarking
* Initialize the PyFlink execution environment. Connect it to the Redpanda broker.
* Instantiate two DataStreams: `TelemetryStream` and `ThreatStream`.
* **Critical:** Assign timestamps and watermarks to both streams based on the `event_time` field. Configure a bounded out-of-orderness tolerance (e.g., 2 minutes) to handle network latency without indefinitely stalling the window.

### Task 2: Spatial-Temporal Collision Engine (The Math)
* Implement a `CoProcessFunction` or a temporal Interval Join to evaluate the intersection of the two streams.
* **The Logic:** When a threat is registered, calculate if any active shipment's coordinates intersect with the threat's `impact_polygon` during the active time window.
* **Optimization:** Do not run complex GIS operations on every event. Use a lightweight bounding-box overlap or a fast Haversine distance calculation to filter out obvious non-collisions before running exact geometry checks.
* **Output:** Upon detecting a collision, construct an `AnomalyAlert` payload and sink it to a new Redpanda topic: `anomaly-alerts`.
* *Schema:* `shipment_id`, `threat_id`, `collision_coordinates`, `estimated_delay_hours`.

### Task 3: Context Assembly Worker (FastAPI Consumer)
* Build a dedicated asynchronous consumer within the FastAPI service listening exclusively to the `anomaly-alerts` Redpanda topic.
* **The Redis Lookup (Blast Radius):** The moment an alert is pulled, query Redis using the key `shipment_context:{shipment_id}`.
* **Payload Construction:** Merge the dynamic Flink alert data with the static Redis state.
* *Target Output Payload:*
  * Threat parameters (`threat_id`, `delay_hours`, `collision_coordinates`)
  * Cargo properties (`priority_tier`, `transport_mode`)
  * Pre-computed Fallback Routes (Array of alternate routes containing `route_id`, `base_cost`, and `transit_time`).
* **Handoff:** Structure this assembled payload into a strict Pydantic model (`LLMOptimizationRequest`). This is the exact payload that will be injected into Vertex AI in the next phase.