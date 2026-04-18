"""Async Kafka producer service wrapping aiokafka.

Provides a managed lifecycle (start/stop) and typed send methods
for each Redpanda topic. Designed to be instantiated once at app
startup (via FastAPI lifespan) or in the CLI generator process.

Usage:
    producer = KafkaProducerService(settings)
    await producer.start()
    await producer.send_telemetry(payload)
    await producer.stop()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiokafka import AIOKafkaProducer

from shared.schemas.telemetry import ShipmentTelemetrySchema
from shared.schemas.threats import ThreatSignalSchema

if TYPE_CHECKING:
    from services.ingestion.config import Settings

logger = logging.getLogger(__name__)


class KafkaProducerService:
    """Async Kafka producer with typed send methods per topic.

    Partition key strategy:
      - Telemetry: keyed by `transport_mode` → ensures all SEA/AIR/ROAD
        shipments land in the same partition set for Flink co-partitioning.
      - Threats: keyed by `threat_type` → groups similar threats for
        downstream windowed aggregation.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        """Connect to Redpanda and start the producer."""
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._settings.kafka_bootstrap_servers,
            # Use Pydantic's model_dump_json() at the call site, so
            # the serializer here just encodes the pre-serialized string.
            value_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
            key_serializer=lambda k: k.encode("utf-8") if isinstance(k, str) else k,
            # Durability: wait for leader + one replica ack
            acks="all",
            # Batch for throughput — 16KB batches, 10ms linger
            max_batch_size=16384,
            linger_ms=10,
        )
        await self._producer.start()
        logger.info(
            "Kafka producer connected to %s",
            self._settings.kafka_bootstrap_servers,
        )

    async def stop(self) -> None:
        """Flush pending messages and disconnect."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            logger.info("Kafka producer stopped")

    def _ensure_started(self) -> AIOKafkaProducer:
        """Guard against using the producer before start()."""
        if self._producer is None:
            raise RuntimeError(
                "KafkaProducerService is not started. Call await start() first."
            )
        return self._producer

    async def send_telemetry(self, payload: ShipmentTelemetrySchema) -> None:
        """Produce a telemetry record to the shipment-telemetry topic.

        Partition key: transport_mode (SEA, AIR, ROAD).
        """
        producer = self._ensure_started()
        await producer.send_and_wait(
            topic=self._settings.telemetry_topic,
            key=payload.transport_mode.value,
            value=payload.model_dump_json(),
        )

    async def send_threat(self, payload: ThreatSignalSchema) -> None:
        """Produce a threat signal to the threat-signals topic.

        Partition key: threat_type (WEATHER, CONGESTION, INFRASTRUCTURE).
        """
        producer = self._ensure_started()
        await producer.send_and_wait(
            topic=self._settings.threat_topic,
            key=payload.threat_type.value,
            value=payload.model_dump_json(),
        )

    async def send_telemetry_batch(
        self, payloads: list[ShipmentTelemetrySchema]
    ) -> int:
        """Produce a batch of telemetry records. Returns count of messages sent."""
        producer = self._ensure_started()
        for payload in payloads:
            await producer.send(
                topic=self._settings.telemetry_topic,
                key=payload.transport_mode.value,
                value=payload.model_dump_json(),
            )
        # Flush the batch
        await producer.flush()
        return len(payloads)
