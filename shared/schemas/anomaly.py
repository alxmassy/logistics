"""Anomaly alert schema — output of the Flink collision detection engine.

Published to the `anomaly-alerts` Redpanda topic when a spatial-temporal
collision is detected between an active shipment and a threat zone.

Carries `transport_mode` and `priority_tier` from the telemetry join
to avoid a redundant Redis lookup in the context assembly phase.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.schemas.telemetry import LatLon, PriorityTier, TransportMode
from shared.schemas.threats import ThreatType


class AnomalyAlertSchema(BaseModel):
    """Flink-emitted alert indicating a shipment–threat spatial collision.

    This is the bridge between the Flink prediction layer and the
    context assembly worker. Each alert triggers a Redis blast-radius
    lookup and Vertex AI optimization request.
    """

    model_config = ConfigDict(frozen=True)

    alert_id: UUID
    shipment_id: UUID
    threat_id: UUID
    threat_type: ThreatType
    severity: int = Field(ge=1, le=10)
    collision_coordinates: LatLon
    transport_mode: TransportMode
    priority_tier: PriorityTier
    estimated_delay_hours: float = Field(ge=0.0)
    event_time: datetime

    @field_validator("event_time", mode="after")
    @classmethod
    def _ensure_utc_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return v
