"""Optimization request schemas for the Vertex AI integration.

The `LLMOptimizationRequest` is the strict contract between the context
assembly worker and the optimization layer (Vertex AI / Gemini 1.5 Pro).
It bundles threat context, cargo properties, and precomputed fallback
routes into a single payload ready for zero-shot prompt injection.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.schemas.telemetry import LatLon, PriorityTier, TransportMode
from shared.schemas.threats import ThreatType


class FallbackRoute(BaseModel):
    """Simplified route view for the LLM optimization context.

    Stripped-down version of PrecomputedRouteSchema — the LLM only needs
    the route ID, cost, and transit time to evaluate trade-offs.
    Path nodes are omitted to reduce token consumption.
    """

    model_config = ConfigDict(frozen=True)

    route_id: UUID
    base_cost: float = Field(gt=0)
    estimated_transit_time_hours: float = Field(gt=0)


class LLMOptimizationRequest(BaseModel):
    """Assembled context payload for Vertex AI reroute optimization.

    This is the exact payload injected into the Gemini 1.5 Pro zero-shot
    prompt. The LLM evaluates cost/time trade-offs across the fallback
    routes and outputs a strict JSON reroute decision.
    """

    model_config = ConfigDict(frozen=True)

    request_id: UUID

    # --- Threat context ---
    alert_id: UUID
    threat_id: UUID
    threat_type: ThreatType
    severity: int = Field(ge=1, le=10)
    estimated_delay_hours: float = Field(ge=0.0)
    collision_coordinates: LatLon

    # --- Cargo context ---
    shipment_id: UUID
    priority_tier: PriorityTier
    transport_mode: TransportMode

    # --- Fallback routes from Redis blast radius ---
    fallback_routes: list[FallbackRoute] = Field(
        default_factory=list,
        description="Precomputed alternative routes; empty if Redis context expired",
    )

    # --- Metadata ---
    assembled_at: datetime

    @field_validator("assembled_at", mode="after")
    @classmethod
    def _ensure_utc_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return v
