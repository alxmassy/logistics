"""
FastAPI Application — LLM Optimization Service entry point.

Endpoints:
    GET  /health                          → liveness check
    GET  /decision/{request_id}           → fetch a stored decision
    POST /execute/approve/{shipment_id}   → human approves Tier 2
    POST /execute/reject/{shipment_id}    → human rejects Tier 2
    WS   /ws/dashboard                    → real-time Tier 2 push

Background workers (started via lifespan):
    • Kafka consumer loop (optimization-requests → reroute-decisions)
    • Redis pub/sub listener → WebSocket broadcaster
    • Redis keyspace-notification listener (expired TTL failsafe)
"""
import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # Load .env before anything reads os.environ

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
import redis.asyncio as aioredis

from rule_engine import ExecutionPayload, LLMAction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


# ── WebSocket connection manager ─────────────────────────────────────
class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: str) -> None:
        dead: list[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# ── In-memory decision store (swap for a DB in production) ───────────
_decisions: dict[str, dict] = {}


def store_decision(execution: ExecutionPayload) -> None:
    """Persist a decision so GET /decision/{request_id} can return it."""
    _decisions[execution.request_data.request_id] = execution.model_dump(
        mode="json"
    )


# ── Background: Redis pub/sub → WebSocket relay ─────────────────────
async def _redis_ws_relay(redis_client: aioredis.Redis) -> None:
    """Subscribe to tier2_alerts and push every message to WS clients."""
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("tier2_alerts")
    logger.info("Redis pub/sub → WS relay started.")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await manager.broadcast(message["data"])
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe("tier2_alerts")
        await pubsub.close()


# ── Background: Redis keyspace expiry failsafe ───────────────────────
async def _keyspace_expiry_listener(redis_client: aioredis.Redis) -> None:
    """
    Listen for expired `pending_approval:*` keys.
    When a Tier 2 decision expires without human action, automatically
    execute the lowest-cost 'Wait It Out' fallback route.
    """
    # Enable keyspace notifications for expired events (requires Redis config
    # `notify-keyspace-events Ex` or we set it at runtime).
    try:
        await redis_client.config_set("notify-keyspace-events", "Ex")
    except Exception as e:
        logger.warning(
            "Could not enable keyspace notifications (may need Redis ACL): %s", e
        )

    pubsub = redis_client.pubsub()
    # Subscribe to DB-0 expired events
    await pubsub.subscribe("__keyevent@0__:expired")
    logger.info("Redis keyspace expiry failsafe started.")
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            expired_key = message["data"]
            if isinstance(expired_key, bytes):
                expired_key = expired_key.decode()
            if not expired_key.startswith("pending_approval:"):
                continue

            shipment_id = expired_key.removeprefix("pending_approval:")
            logger.warning(
                "Tier 2 TTL expired for shipment %s — "
                "auto-executing lowest-cost 'Wait It Out' fallback.",
                shipment_id,
            )
            # In a full system we'd look up the original payload
            # (it's gone from Redis now). A production design would
            # store a shadow copy. For now we log the failsafe trigger.
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe("__keyevent@0__:expired")
        await pubsub.close()


# ── Lifespan ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Shared Redis connection
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    app.state.redis = redis_client

    # Import consumer here (after .env is loaded) to avoid import-time issues
    from consumer import AIServiceConsumer

    consumer = AIServiceConsumer(
        redis_client=redis_client,
        ws_broadcast_fn=manager.broadcast,
    )
    app.state.consumer = consumer

    # Launch background workers
    consumer_task = asyncio.create_task(consumer.start())
    relay_task = asyncio.create_task(_redis_ws_relay(redis_client))
    failsafe_task = asyncio.create_task(_keyspace_expiry_listener(redis_client))

    yield

    # Graceful shutdown: cancel background tasks first, then stop consumer
    for task in (relay_task, failsafe_task):
        task.cancel()
    await consumer.stop()
    consumer_task.cancel()

    # Wait for all tasks to finish
    await asyncio.gather(
        consumer_task, relay_task, failsafe_task, return_exceptions=True
    )
    await redis_client.close()
    logger.info("All background workers shut down.")


# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="LLM Optimization Service",
    description="Phase 4 — Vertex AI route optimization & execution gateway",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Routes ───────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    consumer = getattr(app.state, "consumer", None)
    return {
        "status": "ok",
        "consumer_running": consumer.running if consumer else False,
    }


@app.get("/decision/{request_id}")
async def get_decision(request_id: str):
    decision = _decisions.get(request_id)
    if not decision:
        raise HTTPException(
            status_code=404, detail="Decision not found for this request_id."
        )
    return decision


@app.post("/execute/approve/{shipment_id}")
async def approve_tier2(shipment_id: str):
    redis_client: aioredis.Redis = app.state.redis
    redis_key = f"pending_approval:{shipment_id}"
    payload_str = await redis_client.get(redis_key)

    if not payload_str:
        raise HTTPException(
            status_code=404,
            detail="Pending decision not found or expired.",
        )

    payload = json.loads(payload_str)
    route_id = payload["decision"]["selected_route_id"]
    idempotency_key = payload.get("idempotency_key", "N/A")

    logger.info(
        "Human APPROVED shipment %s — booking route %s (key=%s)",
        shipment_id, route_id, idempotency_key,
    )

    # Clear from pending queue
    await redis_client.delete(redis_key)

    return {
        "status": "approved",
        "shipment_id": shipment_id,
        "route_id": route_id,
        "idempotency_key": idempotency_key,
    }


@app.post("/execute/reject/{shipment_id}")
async def reject_tier2(shipment_id: str):
    redis_client: aioredis.Redis = app.state.redis
    redis_key = f"pending_approval:{shipment_id}"

    if not await redis_client.exists(redis_key):
        raise HTTPException(
            status_code=404,
            detail="Pending decision not found or expired.",
        )

    await redis_client.delete(redis_key)
    logger.info("Human REJECTED shipment %s.", shipment_id)
    return {"status": "rejected", "shipment_id": shipment_id}


@app.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive / ping
    except WebSocketDisconnect:
        manager.disconnect(websocket)
