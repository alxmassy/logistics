"""Anomaly alert consumer — async Kafka consumer for the context assembly pipeline.

Subscribes to the `anomaly-alerts` topic, deserializes each message into
an AnomalyAlertSchema, delegates to the ContextAssembler for enrichment,
and publishes the assembled LLMOptimizationRequest to `optimization-requests`.

Can run standalone (via CLI) or integrated into the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from services.prediction.config import PredictionSettings
from shared.schemas.anomaly import AnomalyAlertSchema

if TYPE_CHECKING:
    from services.prediction.context_assembly.assembler import ContextAssembler

logger = logging.getLogger(__name__)


class AnomalyAlertConsumer:
    """Async consumer that processes anomaly alerts and produces optimization requests.

    Lifecycle:
        consumer = AnomalyAlertConsumer(settings, assembler)
        await consumer.start()
        task = asyncio.create_task(consumer.run())
        ...
        await consumer.stop()

    Args:
        settings: Prediction service configuration.
        assembler: ContextAssembler instance (with Redis client).
    """

    def __init__(
        self,
        settings: PredictionSettings,
        assembler: ContextAssembler,
    ) -> None:
        self._settings = settings
        self._assembler = assembler
        self._consumer: AIOKafkaConsumer | None = None
        self._producer: AIOKafkaProducer | None = None
        self._running = False

    async def start(self) -> None:
        """Initialize and connect the Kafka consumer and producer."""
        self._consumer = AIOKafkaConsumer(
            self._settings.anomaly_alerts_topic,
            bootstrap_servers=self._settings.kafka_bootstrap_servers,
            group_id=self._settings.consumer_group_id,
            value_deserializer=lambda v: v.decode("utf-8"),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await self._consumer.start()

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._settings.kafka_bootstrap_servers,
            value_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
            acks="all",
        )
        await self._producer.start()

        self._running = True
        logger.info(
            "Anomaly alert consumer started: topic=%s, group=%s",
            self._settings.anomaly_alerts_topic,
            self._settings.consumer_group_id,
        )

    async def stop(self) -> None:
        """Gracefully shut down the consumer and producer."""
        self._running = False
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
        logger.info("Anomaly alert consumer stopped")

    async def run(self) -> None:
        """Main consume loop — runs until stop() is called.

        For each anomaly alert:
        1. Deserialize → AnomalyAlertSchema
        2. Assemble → LLMOptimizationRequest (via ContextAssembler)
        3. Publish → optimization-requests topic
        """
        if self._consumer is None or self._producer is None:
            raise RuntimeError("Consumer not started. Call await start() first.")

        logger.info("Consuming anomaly alerts...")

        try:
            async for message in self._consumer:
                if not self._running:
                    break

                try:
                    alert = AnomalyAlertSchema.model_validate_json(message.value)
                except Exception as e:
                    logger.error("Failed to deserialize anomaly alert: %s", e)
                    continue

                try:
                    optimization_request = await self._assembler.assemble(alert)
                except Exception as e:
                    logger.error(
                        "Failed to assemble context for alert %s: %s",
                        alert.alert_id, e,
                    )
                    continue

                # Publish to optimization-requests topic
                try:
                    await self._producer.send_and_wait(
                        topic=self._settings.optimization_requests_topic,
                        value=optimization_request.model_dump_json(),
                    )
                    logger.info(
                        "Published optimization request %s for shipment %s",
                        optimization_request.request_id,
                        optimization_request.shipment_id,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to publish optimization request: %s", e,
                    )

        except asyncio.CancelledError:
            logger.info("Consumer task cancelled")
        except Exception as e:
            logger.error("Consumer loop error: %s", e, exc_info=True)
