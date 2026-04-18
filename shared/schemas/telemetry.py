"""Shipment telemetry schemas and domain enums.

Defines the data contract for real-time GPS/positioning data
emitted by carriers and fed into the Redpanda `shipment-telemetry` topic.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransportMode(str, Enum):
    """Carrier transport modality — drives partition affinity in Kafka."""

    SEA = "SEA"
    AIR = "AIR"
    ROAD = "ROAD"


class PriorityTier(str, Enum):
    """Shipment SLA tier — determines reroute urgency thresholds."""

    LOW = "LOW"
    STANDARD = "STANDARD"
    HIGH = "HIGH"


class LatLon(BaseModel):
    """WGS-84 coordinate pair with validation bounds."""

    model_config = ConfigDict(frozen=True)

    lat: float = Field(ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    lon: float = Field(ge=-180.0, le=180.0, description="Longitude in decimal degrees")


class ShipmentTelemetrySchema(BaseModel):
    """Single telemetry reading from a shipment in transit.

    Immutable after construction — downstream consumers must not mutate payloads.
    Every record carries its own `event_time` for Flink event-time windowing;
    processing-time semantics are explicitly forbidden.
    """

    model_config = ConfigDict(frozen=True)

    shipment_id: UUID
    current_lat_lon: LatLon
    destination_lat_lon: LatLon
    carrier: str = Field(min_length=1, max_length=128)
    transport_mode: TransportMode
    priority_tier: PriorityTier
    expected_eta: datetime
    event_time: datetime

    @field_validator("expected_eta", "event_time", mode="after")
    @classmethod
    def _ensure_utc_aware(cls, v: datetime) -> datetime:
        """Reject naive datetimes — all timestamps must be UTC-aware."""
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return v
