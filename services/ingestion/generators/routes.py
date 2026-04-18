"""Precomputed route generator and Redis seeder.

For each generated shipment, creates 2–4 alternative routes and stores
them in a Redis hash under the key `shipment_context:{shipment_id}`.

This bridges the gap caused by the lack of a dedicated graph database —
the context assembly layer queries Redis directly when Flink triggers
a reroute alert.
"""

from __future__ import annotations

import json
import logging
import random
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from shared.schemas.routes import PrecomputedRouteSchema
from shared.schemas.telemetry import LatLon

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Redis key prefix for shipment context
SHIPMENT_CONTEXT_PREFIX = "shipment_context"


def _generate_alternative_route(
    shipment_id: UUID,
    origin: LatLon,
    destination: LatLon,
) -> PrecomputedRouteSchema:
    """Generate a single alternative route between origin and destination.

    Creates intermediate waypoints with random deviations to simulate
    different routing options (e.g., different ports, highways, airways).
    """
    num_waypoints = random.randint(2, 5)
    path_nodes: list[LatLon] = [origin]

    for i in range(1, num_waypoints - 1):
        # Interpolate with deviation
        t = i / (num_waypoints - 1)
        lat = origin.lat + (destination.lat - origin.lat) * t + random.gauss(0, 2.0)
        lon = origin.lon + (destination.lon - origin.lon) * t + random.gauss(0, 2.0)
        lat = max(-90.0, min(90.0, round(lat, 6)))
        lon = max(-180.0, min(180.0, round(lon, 6)))
        path_nodes.append(LatLon(lat=lat, lon=lon))

    path_nodes.append(destination)

    return PrecomputedRouteSchema(
        route_id=uuid4(),
        shipment_id=shipment_id,
        path_nodes=path_nodes,
        base_cost=round(random.uniform(500.0, 25000.0), 2),
        estimated_transit_time_hours=round(random.uniform(12.0, 720.0), 1),
    )


def generate_routes_for_shipment(
    shipment_id: UUID,
    origin: LatLon,
    destination: LatLon,
    num_alternatives: int | None = None,
) -> list[PrecomputedRouteSchema]:
    """Generate 2–4 alternative routes for a single shipment.

    Args:
        shipment_id: UUID of the shipment these routes belong to.
        origin: Starting coordinate.
        destination: Ending coordinate.
        num_alternatives: Override the number of alternatives (default: random 2–4).

    Returns:
        List of PrecomputedRouteSchema objects.
    """
    count = num_alternatives or random.randint(2, 4)
    return [
        _generate_alternative_route(shipment_id, origin, destination)
        for _ in range(count)
    ]


async def seed_shipment_context(
    redis_client: aioredis.Redis,
    shipment_id: UUID,
    routes: list[PrecomputedRouteSchema],
) -> None:
    """Store precomputed routes in Redis for a shipment.

    Stores as a Redis hash:
        Key:   shipment_context:{shipment_id}
        Field: routes
        Value: JSON array of serialized route objects

    The context assembly layer reads this when Flink triggers an alert.
    """
    key = f"{SHIPMENT_CONTEXT_PREFIX}:{shipment_id}"
    routes_json = json.dumps([
        json.loads(route.model_dump_json()) for route in routes
    ])
    await redis_client.hset(key, "routes", routes_json)  # type: ignore[arg-type]
    # Set a TTL so stale shipment context doesn't accumulate (48 hours)
    await redis_client.expire(key, 48 * 3600)


class RouteSeeder:
    """Batch seeds Redis with precomputed routes for generated shipments.

    Used by the CLI generator to populate the blast-radius context
    at shipment creation time.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client
        self._seeded_count = 0

    async def seed_for_shipment(
        self,
        shipment_id: UUID,
        origin: LatLon,
        destination: LatLon,
    ) -> list[PrecomputedRouteSchema]:
        """Generate and seed routes for a single shipment.

        Returns the generated routes for logging/inspection.
        """
        routes = generate_routes_for_shipment(shipment_id, origin, destination)
        await seed_shipment_context(self._redis, shipment_id, routes)
        self._seeded_count += 1
        return routes

    @property
    def seeded_count(self) -> int:
        """Total number of shipments seeded so far."""
        return self._seeded_count
