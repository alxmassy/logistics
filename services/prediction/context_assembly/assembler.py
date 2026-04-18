"""Context assembler — Redis blast-radius lookup and payload construction.

When Flink detects a shipment–threat collision, the assembler:
1. Queries Redis for precomputed alternative routes
2. Merges the dynamic alert data with static route context
3. Constructs a strict LLMOptimizationRequest for Vertex AI

Handles missing Redis context gracefully — shipment context may have
expired (48h TTL) or never been seeded in edge cases.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from shared.schemas.anomaly import AnomalyAlertSchema
from shared.schemas.optimization import FallbackRoute, LLMOptimizationRequest

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Must match the prefix used by the ingestion route seeder
_SHIPMENT_CONTEXT_PREFIX = "shipment_context"


class ContextAssembler:
    """Assembles LLM optimization requests from anomaly alerts + Redis context.

    This is the bridge between the prediction layer (Flink) and the
    optimization layer (Vertex AI). Each assembled request contains
    everything the LLM needs to evaluate rerouting options.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client
        self._assembled_count = 0
        self._missing_context_count = 0

    async def assemble(self, alert: AnomalyAlertSchema) -> LLMOptimizationRequest:
        """Build an LLMOptimizationRequest from an anomaly alert.

        Queries Redis for the shipment's precomputed routes. If the context
        is missing (expired TTL or un-seeded shipment), the request is still
        constructed with an empty fallback_routes list — the LLM can still
        make a recommendation based on threat severity and cargo priority.

        Args:
            alert: The anomaly alert from Flink.

        Returns:
            A fully assembled LLMOptimizationRequest.
        """
        fallback_routes = await self._fetch_routes(alert.shipment_id)

        request = LLMOptimizationRequest(
            request_id=uuid4(),
            alert_id=alert.alert_id,
            threat_id=alert.threat_id,
            threat_type=alert.threat_type,
            severity=alert.severity,
            estimated_delay_hours=alert.estimated_delay_hours,
            collision_coordinates=alert.collision_coordinates,
            shipment_id=alert.shipment_id,
            priority_tier=alert.priority_tier,
            transport_mode=alert.transport_mode,
            fallback_routes=fallback_routes,
            assembled_at=datetime.now(timezone.utc),
        )

        self._assembled_count += 1
        logger.info(
            "Assembled optimization request %s: shipment=%s, %d fallback routes",
            request.request_id,
            alert.shipment_id,
            len(fallback_routes),
        )

        return request

    async def _fetch_routes(self, shipment_id) -> list[FallbackRoute]:
        """Fetch precomputed routes from Redis blast-radius cache.

        Returns an empty list if the context is missing or malformed.
        """
        key = f"{_SHIPMENT_CONTEXT_PREFIX}:{shipment_id}"

        try:
            routes_json = await self._redis.hget(key, "routes")  # type: ignore[arg-type]
        except Exception as e:
            logger.error("Redis lookup failed for %s: %s", key, e)
            return []

        if routes_json is None:
            self._missing_context_count += 1
            logger.warning(
                "No Redis context for shipment %s (expired or un-seeded)",
                shipment_id,
            )
            return []

        try:
            raw_routes = json.loads(routes_json)
            return [
                FallbackRoute(
                    route_id=r["route_id"],
                    base_cost=r["base_cost"],
                    estimated_transit_time_hours=r["estimated_transit_time_hours"],
                )
                for r in raw_routes
            ]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error("Malformed routes data for %s: %s", key, e)
            return []

    @property
    def assembled_count(self) -> int:
        """Total number of requests assembled."""
        return self._assembled_count

    @property
    def missing_context_count(self) -> int:
        """Number of alerts where Redis context was missing."""
        return self._missing_context_count
