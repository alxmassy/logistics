"""Tests for the context assembly pipeline.

Validates the ContextAssembler's Redis lookup, payload construction,
and graceful handling of missing/malformed Redis context.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from services.prediction.context_assembly.assembler import ContextAssembler
from shared.schemas.anomaly import AnomalyAlertSchema
from shared.schemas.optimization import LLMOptimizationRequest
from shared.schemas.telemetry import LatLon, PriorityTier, TransportMode
from shared.schemas.threats import ThreatType


def _make_alert(**overrides) -> AnomalyAlertSchema:
    """Build a test anomaly alert."""
    defaults = {
        "alert_id": uuid4(),
        "shipment_id": uuid4(),
        "threat_id": uuid4(),
        "threat_type": ThreatType.WEATHER,
        "severity": 7,
        "collision_coordinates": LatLon(lat=31.0, lon=121.0),
        "transport_mode": TransportMode.SEA,
        "priority_tier": PriorityTier.HIGH,
        "estimated_delay_hours": 12.5,
        "event_time": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return AnomalyAlertSchema(**defaults)


def _make_redis_routes(shipment_id, count: int = 3) -> str:
    """Build a JSON string matching the Redis routes format."""
    routes = [
        {
            "route_id": str(uuid4()),
            "shipment_id": str(shipment_id),
            "path_nodes": [{"lat": 0.0, "lon": 0.0}, {"lat": 10.0, "lon": 10.0}],
            "base_cost": 1000.0 + i * 500.0,
            "estimated_transit_time_hours": 24.0 + i * 12.0,
        }
        for i in range(count)
    ]
    return json.dumps(routes)


# ---------------------------------------------------------------------------
# ContextAssembler
# ---------------------------------------------------------------------------

class TestContextAssembler:
    @pytest.mark.asyncio
    async def test_assembles_with_routes(self) -> None:
        """Full assembly: alert + Redis routes → LLMOptimizationRequest."""
        alert = _make_alert()
        mock_redis = AsyncMock()
        mock_redis.hget = AsyncMock(
            return_value=_make_redis_routes(alert.shipment_id, count=3)
        )

        assembler = ContextAssembler(mock_redis)
        request = await assembler.assemble(alert)

        assert isinstance(request, LLMOptimizationRequest)
        assert request.shipment_id == alert.shipment_id
        assert request.threat_id == alert.threat_id
        assert request.severity == alert.severity
        assert request.transport_mode == TransportMode.SEA
        assert request.priority_tier == PriorityTier.HIGH
        assert len(request.fallback_routes) == 3
        assert request.assembled_at is not None

        # Verify Redis was called with correct key
        mock_redis.hget.assert_called_once_with(
            f"shipment_context:{alert.shipment_id}", "routes"
        )

        assert assembler.assembled_count == 1
        assert assembler.missing_context_count == 0

    @pytest.mark.asyncio
    async def test_assembles_with_missing_context(self) -> None:
        """Missing Redis context → empty fallback_routes, still succeeds."""
        alert = _make_alert()
        mock_redis = AsyncMock()
        mock_redis.hget = AsyncMock(return_value=None)

        assembler = ContextAssembler(mock_redis)
        request = await assembler.assemble(alert)

        assert isinstance(request, LLMOptimizationRequest)
        assert request.fallback_routes == []
        assert request.shipment_id == alert.shipment_id

        assert assembler.assembled_count == 1
        assert assembler.missing_context_count == 1

    @pytest.mark.asyncio
    async def test_handles_malformed_redis_data(self) -> None:
        """Corrupted Redis data → empty routes, no crash."""
        alert = _make_alert()
        mock_redis = AsyncMock()
        mock_redis.hget = AsyncMock(return_value="not-valid-json{{{")

        assembler = ContextAssembler(mock_redis)
        request = await assembler.assemble(alert)

        assert request.fallback_routes == []

    @pytest.mark.asyncio
    async def test_handles_redis_connection_error(self) -> None:
        """Redis failure → empty routes, no crash."""
        alert = _make_alert()
        mock_redis = AsyncMock()
        mock_redis.hget = AsyncMock(side_effect=ConnectionError("Redis down"))

        assembler = ContextAssembler(mock_redis)
        request = await assembler.assemble(alert)

        assert request.fallback_routes == []
        assert request.shipment_id == alert.shipment_id

    @pytest.mark.asyncio
    async def test_routes_have_correct_fields(self) -> None:
        """Verify FallbackRoute strips path_nodes (saves LLM tokens)."""
        alert = _make_alert()
        mock_redis = AsyncMock()
        mock_redis.hget = AsyncMock(
            return_value=_make_redis_routes(alert.shipment_id, count=2)
        )

        assembler = ContextAssembler(mock_redis)
        request = await assembler.assemble(alert)

        for route in request.fallback_routes:
            assert route.base_cost > 0
            assert route.estimated_transit_time_hours > 0
            assert route.route_id is not None
            # FallbackRoute should NOT have path_nodes
            assert not hasattr(route, "path_nodes") or "path_nodes" not in route.model_fields

    @pytest.mark.asyncio
    async def test_multiple_assemblies_increment_count(self) -> None:
        """Counter tracks total assemblies correctly."""
        mock_redis = AsyncMock()
        mock_redis.hget = AsyncMock(return_value=None)

        assembler = ContextAssembler(mock_redis)

        for _ in range(5):
            await assembler.assemble(_make_alert())

        assert assembler.assembled_count == 5
        assert assembler.missing_context_count == 5
