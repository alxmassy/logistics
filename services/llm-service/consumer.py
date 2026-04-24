"""
Kafka Consumer — reads from `optimization-requests`, orchestrates the
Vertex AI → Rule Engine pipeline, and publishes to `reroute-decisions`.
"""
import os
import json
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from pydantic import ValidationError

from rule_engine import LLMOptimizationRequest, LLMDecision, ExecutionPayload
from prompt_builder import build_prompt
from vertex_client import VertexClient

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.environ.get(
    "KAFKA_BOOTSTRAP_SERVERS", "localhost:19092"
)
OPTIMIZATION_REQUESTS_TOPIC = os.environ.get(
    "OPTIMIZATION_REQUESTS_TOPIC", "optimization-requests"
)
REROUTE_DECISIONS_TOPIC = os.environ.get(
    "REROUTE_DECISIONS_TOPIC", "reroute-decisions"
)
CONSUMER_GROUP_ID = os.environ.get(
    "LLM_CONSUMER_GROUP_ID", "llm-optimization-group"
)


class AIServiceConsumer:
    """
    Async Kafka consumer that drives the full decision pipeline:
    consume → prompt → Vertex AI → rule engine → tier branch → produce.
    """

    def __init__(self, redis_client, ws_broadcast_fn=None) -> None:
        """
        Args:
            redis_client:     An initialised async Redis client (shared with main.py).
            ws_broadcast_fn:  Optional async callable(str) to push Tier 2
                              payloads to WebSocket clients.
        """
        self.redis = redis_client
        self.ws_broadcast = ws_broadcast_fn
        self.vertex = VertexClient()
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.running = False

    # ── Lifecycle ────────────────────────────────────────────────────
    async def start(self) -> None:
        self.consumer = AIOKafkaConsumer(
            OPTIMIZATION_REQUESTS_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=CONSUMER_GROUP_ID,
            auto_offset_reset="latest",
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        )

        await self.consumer.start()
        await self.producer.start()
        self.running = True
        logger.info("Kafka consumer/producer started.")

        try:
            async for msg in self.consumer:
                if not self.running:
                    break
                await self.process_message(msg.value)
        finally:
            await self._close_kafka()

    async def stop(self) -> None:
        """Signal the consumer loop to stop and close Kafka handles."""
        self.running = False
        await self._close_kafka()

    async def _close_kafka(self) -> None:
        if self.consumer:
            await self.consumer.stop()
            self.consumer = None
        if self.producer:
            await self.producer.stop()
            self.producer = None
        logger.info("Kafka connections closed.")

    # ── Pipeline ─────────────────────────────────────────────────────
    async def process_message(self, message_bytes: bytes) -> None:
        # ① Parse
        try:
            data = json.loads(message_bytes.decode("utf-8"))
            request_payload = LLMOptimizationRequest(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error("Bad message on optimization-requests: %s", e)
            return

        try:
            # ② Prompt → Vertex AI
            prompt = build_prompt(request_payload)
            decision_dict = await self.vertex.get_optimization_decision(prompt)
            decision = LLMDecision(**decision_dict)

            # ③ Risk scoring
            execution = ExecutionPayload(
                request_data=request_payload,
                decision=decision,
            )
            execution.calculate_risk_score()

            # ④ Tier branching
            if execution.tier == 1:
                logger.info(
                    "Tier 1 — auto-executing shipment %s  (score=%d, key=%s)",
                    request_payload.shipment_id,
                    execution.score,
                    execution.idempotency_key,
                )
                await self._execute_booking(execution)
            else:
                logger.info(
                    "Tier 2 — escalating shipment %s  (score=%d)",
                    request_payload.shipment_id,
                    execution.score,
                )
                await self._store_tier2(execution)

            # ⑤ Publish to reroute-decisions
            decision_json = json.dumps(
                execution.model_dump(mode="json")
            ).encode("utf-8")
            await self.producer.send_and_wait(
                REROUTE_DECISIONS_TOPIC, decision_json
            )

        except Exception:
            logger.exception(
                "Pipeline error for request %s", request_payload.request_id
            )

    # ── Tier 1: autonomous booking ───────────────────────────────────
    async def _execute_booking(self, execution: ExecutionPayload) -> None:
        """Simulate an external Carrier API call to book the route."""
        logger.info(
            "Carrier API booking — route=%s  idempotency_key=%s",
            execution.decision.selected_route_id,
            execution.idempotency_key,
        )

    # ── Tier 2: human-in-the-loop ────────────────────────────────────
    async def _store_tier2(self, execution: ExecutionPayload) -> None:
        """Store in Redis with 10-min TTL and push to WebSocket clients."""
        payload_json = json.dumps(execution.model_dump(mode="json"))
        redis_key = f"pending_approval:{execution.request_data.shipment_id}"

        # Store with 10-minute TTL
        await self.redis.setex(redis_key, 600, payload_json)

        # Push over WebSocket via the broadcast callback
        if self.ws_broadcast:
            await self.ws_broadcast(payload_json)

        # Also publish to Redis pub/sub so the WS listener picks it up
        # even if the broadcast callback is not wired (belt & suspenders).
        await self.redis.publish("tier2_alerts", payload_json)
