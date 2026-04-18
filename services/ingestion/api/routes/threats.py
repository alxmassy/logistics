"""Threat signal ingestion endpoint.

POST /ingest/threat — accepts a single threat signal payload
and produces it to the Redpanda `threat-signals` topic.

Useful for manual threat injection during demos and testing.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.ingestion.api.dependencies import get_producer
from services.ingestion.producers.kafka import KafkaProducerService
from shared.schemas.threats import ThreatSignalSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingestion"])


class ThreatResponse(BaseModel):
    """Response body for threat signal ingestion."""

    threat_id: str
    status: str = "accepted"


@router.post(
    "/threat",
    response_model=ThreatResponse,
    summary="Ingest a threat signal",
    description="Accepts a single threat signal and produces it to Redpanda.",
)
async def ingest_threat(
    payload: ThreatSignalSchema,
    producer: KafkaProducerService = Depends(get_producer),
) -> ThreatResponse:
    """Validate and produce a single threat signal."""
    await producer.send_threat(payload)
    logger.info("Ingested threat %s (type=%s)", payload.threat_id, payload.threat_type.value)
    return ThreatResponse(threat_id=str(payload.threat_id))
