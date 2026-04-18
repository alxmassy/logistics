# System Context: Optimization & Execution Layer

## 1. Macro Architecture Checkpoint
Ingestion, Prediction, and Context Assembly are complete. You now have a strict `LLMOptimizationRequest` payload containing the threat data, cargo priority, and pre-computed fallback routes.
This phase introduces heuristic reasoning via an LLM to select the optimal route, followed immediately by a deterministic safety gateway to route the execution autonomously or require human intervention.

## 2. Optimization & Execution Build Instructions

**Objective:** Build the Vertex AI integration for structured decision-making and the FastAPI dynamic risk scoring engine to enforce execution tiers.

### Technical Constraints & Tooling
* **LLM Provider:** Google Cloud Vertex AI (Gemini 1.5 Pro).
* **Output Format:** Strict JSON enforcement. The LLM must not return markdown blocks or conversational text. Use Vertex AI's `response_mime_type="application/json"`.
* **Execution Framework:** FastAPI `BackgroundTasks` for Tier 1, WebSockets + Redis for Tier 2.
* **Validation:** Pydantic v2 for the Rule Engine scoring matrix.

### Task 1: Vertex AI Decision Engine
* Create an asynchronous service function to call Vertex AI.
* **Prompt Engineering:** Construct a system prompt that injects the `LLMOptimizationRequest` payload. Instruct the model to act as an autonomous routing agent prioritizing SLA constraints and cost efficiency.
* **Schema Definition:** Enforce the following output schema from the LLM:
  * `selected_route_id` (String)
  * `action` (String)
  * `reasoning` (String)
  * `requires_human` (Boolean) - LLM override for life-safety or geopolitical anomalies.
  * `new_eta_offset_hours` (Float)

### Task 2: Deterministic Rule Engine (Risk Scoring)
* Define a Pydantic model (`ExecutionPayload`) that accepts the merged original context and the LLM's JSON output.
* Implement a `calculate_risk_score()` method within the model.
* **Scoring Matrix:**
  * Base cost delta: `$0-$100` (+0), `$101-$500` (+5), `>$500` (+50).
  * Cargo SLA: `LOW` (+0), `STANDARD` (+10), `HIGH` (+50).
  * Mode/Carrier Friction: Same (+0), Change Carrier (+20), Change Mode (+50).
* Define the threshold variable: `TIER_1_MAX_SCORE = 40`.

### Task 3: Execution Branching & Delivery
* **Tier 1 (Score <= 40 AND requires_human == False):**
  * Pass the execution payload to a FastAPI `BackgroundTask`.
  * The task should simulate an external Carrier API call to book the route, ensuring it passes a generated `idempotency_key` (UUID).
* **Tier 2 (Score > 40 OR requires_human == True):**
  * Store the pending execution payload in Redis with a 10-minute TTL (Key: `pending_approval:{shipment_id}`).
  * Push the payload immediately over an active WebSocket connection to the frontend (`/ws/dashboard`).
* **The Failsafe:** Implement a background listener for Redis Keyspace Notifications (expired TTLs). If a Tier 2 decision expires without human approval, automatically execute the lowest-cost "Wait It Out" fallback route.

### Task 4: Frontend Action Endpoints
* Expose `POST /execute/approve/{shipment_id}` and `POST /execute/reject/{shipment_id}` endpoints.
* These endpoints must pull the payload from Redis, execute the final simulated carrier API call (if approved), and delete the Redis key to clear the queue.
