"""Telemetry ingestion endpoint.

POST /ingest/telemetry — accepts a batch of shipment telemetry payloads
and produces each to the Redpanda `shipment-telemetry` topic.

Pydantic validation rejects malformed payloads at the edge (HTTP 422).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.ingestion.api.dependencies import get_producer
from services.ingestion.producers.kafka import KafkaProducerService
from shared.schemas.telemetry import ShipmentTelemetrySchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingestion"])


class TelemetryBatchResponse(BaseModel):
    """Response body for batch telemetry ingestion."""

    accepted: int
    status: str = "ok"


@router.post(
    "/telemetry",
    response_model=TelemetryBatchResponse,
    summary="Ingest shipment telemetry batch",
    description="Accepts a list of telemetry payloads and produces them to Redpanda.",
)
async def ingest_telemetry(
    payloads: list[ShipmentTelemetrySchema],
    producer: KafkaProducerService = Depends(get_producer),
) -> TelemetryBatchResponse:
    """Validate and produce a batch of telemetry records."""
    count = await producer.send_telemetry_batch(payloads)
    logger.info("Ingested %d telemetry records", count)
    return TelemetryBatchResponse(accepted=count)
