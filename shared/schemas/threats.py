"""Threat signal schemas and domain enums.

Defines the data contract for external disruption signals
(weather, congestion, infrastructure) fed into the `threat-signals` topic.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.schemas.telemetry import LatLon


class ThreatType(str, Enum):
    """Category of disruption event."""

    WEATHER = "WEATHER"
    CONGESTION = "CONGESTION"
    INFRASTRUCTURE = "INFRASTRUCTURE"


class ThreatSignalSchema(BaseModel):
    """External threat signal with geographic impact zone.

    The `impact_polygon` defines a closed geographic region where the threat
    is active. Downstream Flink jobs perform point-in-polygon intersection
    against active shipment coordinates to detect spatial-temporal collisions.
    """

    model_config = ConfigDict(frozen=True)

    threat_id: UUID
    threat_type: ThreatType
    severity: int = Field(ge=1, le=10, description="Severity scale: 1 (minor) to 10 (catastrophic)")
    impact_polygon: list[LatLon] = Field(
        min_length=3,
        description="Closed polygon vertices defining the threat impact zone",
    )
    event_time: datetime

    @field_validator("event_time", mode="after")
    @classmethod
    def _ensure_utc_aware(cls, v: datetime) -> datetime:
        """Reject naive datetimes — all timestamps must be UTC-aware."""
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return v
