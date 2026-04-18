"""Precomputed route schemas for Redis blast-radius context.

These routes are seeded into Redis at shipment creation time and queried
by the context assembly layer when Flink triggers a reroute alert.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shared.schemas.telemetry import LatLon


class PrecomputedRouteSchema(BaseModel):
    """Alternative route option stored in the shipment context cache.

    Each shipment gets 2–4 precomputed alternatives. The optimization layer
    (Vertex AI) uses these as candidate reroutes when evaluating disruptions.
    """

    model_config = ConfigDict(frozen=True)

    route_id: UUID
    shipment_id: UUID
    path_nodes: list[LatLon] = Field(
        min_length=2,
        description="Ordered waypoints defining the route path",
    )
    base_cost: float = Field(gt=0, description="Estimated cost in USD")
    estimated_transit_time_hours: float = Field(gt=0, description="Transit time in hours")
