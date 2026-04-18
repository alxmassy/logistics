"""Tests for anomaly alert and optimization request schemas.

Validates construction, field bounds, frozen enforcement,
and JSON round-trip serialization for the prediction-phase schemas.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from shared.schemas.anomaly import AnomalyAlertSchema
from shared.schemas.optimization import FallbackRoute, LLMOptimizationRequest
from shared.schemas.telemetry import LatLon, PriorityTier, TransportMode
from shared.schemas.threats import ThreatType


# ---------------------------------------------------------------------------
# AnomalyAlertSchema
# ---------------------------------------------------------------------------

class TestAnomalyAlert:
    def _make_alert(self, **overrides) -> AnomalyAlertSchema:
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

    def test_valid_construction(self) -> None:
        alert = self._make_alert()
        assert alert.severity == 7
        assert alert.transport_mode == TransportMode.SEA

    def test_severity_bounds(self) -> None:
        with pytest.raises(ValueError):
            self._make_alert(severity=0)
        with pytest.raises(ValueError):
            self._make_alert(severity=11)

    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            self._make_alert(event_time=datetime(2026, 1, 1))

    def test_negative_delay_rejected(self) -> None:
        with pytest.raises(ValueError):
            self._make_alert(estimated_delay_hours=-1.0)

    def test_frozen(self) -> None:
        alert = self._make_alert()
        with pytest.raises(Exception):
            alert.severity = 5  # type: ignore[misc]

    def test_json_round_trip(self) -> None:
        alert = self._make_alert()
        json_str = alert.model_dump_json()
        restored = AnomalyAlertSchema.model_validate_json(json_str)
        assert restored.alert_id == alert.alert_id
        assert restored.severity == alert.severity


# ---------------------------------------------------------------------------
# FallbackRoute
# ---------------------------------------------------------------------------

class TestFallbackRoute:
    def test_valid_construction(self) -> None:
        route = FallbackRoute(
            route_id=uuid4(),
            base_cost=1500.0,
            estimated_transit_time_hours=48.0,
        )
        assert route.base_cost == 1500.0

    def test_rejects_zero_cost(self) -> None:
        with pytest.raises(ValueError):
            FallbackRoute(
                route_id=uuid4(),
                base_cost=0.0,
                estimated_transit_time_hours=10.0,
            )

    def test_rejects_negative_transit_time(self) -> None:
        with pytest.raises(ValueError):
            FallbackRoute(
                route_id=uuid4(),
                base_cost=100.0,
                estimated_transit_time_hours=-5.0,
            )


# ---------------------------------------------------------------------------
# LLMOptimizationRequest
# ---------------------------------------------------------------------------

class TestLLMOptimizationRequest:
    def _make_request(self, **overrides) -> LLMOptimizationRequest:
        defaults = {
            "request_id": uuid4(),
            "alert_id": uuid4(),
            "threat_id": uuid4(),
            "threat_type": ThreatType.CONGESTION,
            "severity": 5,
            "estimated_delay_hours": 8.0,
            "collision_coordinates": LatLon(lat=40.0, lon=-74.0),
            "shipment_id": uuid4(),
            "priority_tier": PriorityTier.STANDARD,
            "transport_mode": TransportMode.ROAD,
            "fallback_routes": [
                FallbackRoute(route_id=uuid4(), base_cost=1200.0, estimated_transit_time_hours=36.0),
                FallbackRoute(route_id=uuid4(), base_cost=1800.0, estimated_transit_time_hours=24.0),
            ],
            "assembled_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return LLMOptimizationRequest(**defaults)

    def test_valid_construction(self) -> None:
        req = self._make_request()
        assert len(req.fallback_routes) == 2
        assert req.threat_type == ThreatType.CONGESTION

    def test_empty_fallback_routes(self) -> None:
        """Empty routes is valid — Redis context may have expired."""
        req = self._make_request(fallback_routes=[])
        assert req.fallback_routes == []

    def test_rejects_naive_assembled_at(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            self._make_request(assembled_at=datetime(2026, 1, 1))

    def test_json_round_trip(self) -> None:
        req = self._make_request()
        json_str = req.model_dump_json()
        restored = LLMOptimizationRequest.model_validate_json(json_str)
        assert restored.request_id == req.request_id
        assert len(restored.fallback_routes) == len(req.fallback_routes)

    def test_frozen(self) -> None:
        req = self._make_request()
        with pytest.raises(Exception):
            req.severity = 10  # type: ignore[misc]
