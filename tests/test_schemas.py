"""Tests for shared Pydantic v2 schemas.

Validates edge cases, bounds enforcement, enum strictness,
and the UTC-aware timestamp requirement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from shared.schemas.routes import PrecomputedRouteSchema
from shared.schemas.telemetry import (
    LatLon,
    PriorityTier,
    ShipmentTelemetrySchema,
    TransportMode,
)
from shared.schemas.threats import ThreatSignalSchema, ThreatType


# ---------------------------------------------------------------------------
# LatLon validation
# ---------------------------------------------------------------------------

class TestLatLon:
    def test_valid_coordinates(self) -> None:
        coord = LatLon(lat=45.0, lon=90.0)
        assert coord.lat == 45.0
        assert coord.lon == 90.0

    def test_boundary_values(self) -> None:
        LatLon(lat=-90.0, lon=-180.0)
        LatLon(lat=90.0, lon=180.0)

    def test_latitude_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            LatLon(lat=91.0, lon=0.0)
        with pytest.raises(ValueError):
            LatLon(lat=-91.0, lon=0.0)

    def test_longitude_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            LatLon(lat=0.0, lon=181.0)
        with pytest.raises(ValueError):
            LatLon(lat=0.0, lon=-181.0)

    def test_frozen(self) -> None:
        coord = LatLon(lat=10.0, lon=20.0)
        with pytest.raises(Exception):
            coord.lat = 30.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ShipmentTelemetrySchema validation
# ---------------------------------------------------------------------------

class TestShipmentTelemetry:
    def test_valid_payload(self, sample_telemetry: ShipmentTelemetrySchema) -> None:
        assert sample_telemetry.transport_mode == TransportMode.SEA
        assert sample_telemetry.priority_tier == PriorityTier.HIGH
        assert sample_telemetry.carrier == "Maersk"

    def test_rejects_naive_datetime(self) -> None:
        """event_time and expected_eta must be UTC-aware."""
        with pytest.raises(ValueError, match="timezone-aware"):
            ShipmentTelemetrySchema(
                shipment_id=uuid4(),
                current_lat_lon=LatLon(lat=0.0, lon=0.0),
                destination_lat_lon=LatLon(lat=1.0, lon=1.0),
                carrier="Test",
                transport_mode=TransportMode.ROAD,
                priority_tier=PriorityTier.LOW,
                expected_eta=datetime(2026, 1, 1),  # naive
                event_time=datetime.now(timezone.utc),
            )

    def test_rejects_invalid_transport_mode(self) -> None:
        with pytest.raises(ValueError):
            ShipmentTelemetrySchema(
                shipment_id=uuid4(),
                current_lat_lon=LatLon(lat=0.0, lon=0.0),
                destination_lat_lon=LatLon(lat=1.0, lon=1.0),
                carrier="Test",
                transport_mode="TRAIN",  # type: ignore[arg-type]
                priority_tier=PriorityTier.LOW,
                expected_eta=datetime.now(timezone.utc),
                event_time=datetime.now(timezone.utc),
            )

    def test_rejects_empty_carrier(self) -> None:
        with pytest.raises(ValueError):
            ShipmentTelemetrySchema(
                shipment_id=uuid4(),
                current_lat_lon=LatLon(lat=0.0, lon=0.0),
                destination_lat_lon=LatLon(lat=1.0, lon=1.0),
                carrier="",
                transport_mode=TransportMode.AIR,
                priority_tier=PriorityTier.STANDARD,
                expected_eta=datetime.now(timezone.utc),
                event_time=datetime.now(timezone.utc),
            )

    def test_frozen(self, sample_telemetry: ShipmentTelemetrySchema) -> None:
        with pytest.raises(Exception):
            sample_telemetry.carrier = "DHL"  # type: ignore[misc]

    def test_json_round_trip(self, sample_telemetry: ShipmentTelemetrySchema) -> None:
        json_str = sample_telemetry.model_dump_json()
        restored = ShipmentTelemetrySchema.model_validate_json(json_str)
        assert restored.shipment_id == sample_telemetry.shipment_id
        assert restored.transport_mode == sample_telemetry.transport_mode


# ---------------------------------------------------------------------------
# ThreatSignalSchema validation
# ---------------------------------------------------------------------------

class TestThreatSignal:
    def test_valid_payload(self, sample_threat: ThreatSignalSchema) -> None:
        assert sample_threat.severity == 7
        assert sample_threat.threat_type == ThreatType.WEATHER
        assert len(sample_threat.impact_polygon) >= 3

    def test_severity_too_low(self) -> None:
        with pytest.raises(ValueError):
            ThreatSignalSchema(
                threat_id=uuid4(),
                threat_type=ThreatType.CONGESTION,
                severity=0,
                impact_polygon=[
                    LatLon(lat=0, lon=0), LatLon(lat=1, lon=0), LatLon(lat=1, lon=1),
                ],
                event_time=datetime.now(timezone.utc),
            )

    def test_severity_too_high(self) -> None:
        with pytest.raises(ValueError):
            ThreatSignalSchema(
                threat_id=uuid4(),
                threat_type=ThreatType.INFRASTRUCTURE,
                severity=11,
                impact_polygon=[
                    LatLon(lat=0, lon=0), LatLon(lat=1, lon=0), LatLon(lat=1, lon=1),
                ],
                event_time=datetime.now(timezone.utc),
            )

    def test_polygon_needs_three_vertices(self) -> None:
        with pytest.raises(ValueError):
            ThreatSignalSchema(
                threat_id=uuid4(),
                threat_type=ThreatType.WEATHER,
                severity=5,
                impact_polygon=[LatLon(lat=0, lon=0), LatLon(lat=1, lon=1)],
                event_time=datetime.now(timezone.utc),
            )


# ---------------------------------------------------------------------------
# PrecomputedRouteSchema validation
# ---------------------------------------------------------------------------

class TestPrecomputedRoute:
    def test_valid_route(self) -> None:
        route = PrecomputedRouteSchema(
            route_id=uuid4(),
            shipment_id=uuid4(),
            path_nodes=[LatLon(lat=0.0, lon=0.0), LatLon(lat=10.0, lon=10.0)],
            base_cost=1500.0,
            estimated_transit_time_hours=72.0,
        )
        assert route.base_cost == 1500.0

    def test_rejects_zero_cost(self) -> None:
        with pytest.raises(ValueError):
            PrecomputedRouteSchema(
                route_id=uuid4(),
                shipment_id=uuid4(),
                path_nodes=[LatLon(lat=0.0, lon=0.0), LatLon(lat=10.0, lon=10.0)],
                base_cost=0.0,
                estimated_transit_time_hours=72.0,
            )

    def test_rejects_single_node_path(self) -> None:
        with pytest.raises(ValueError):
            PrecomputedRouteSchema(
                route_id=uuid4(),
                shipment_id=uuid4(),
                path_nodes=[LatLon(lat=0.0, lon=0.0)],
                base_cost=100.0,
                estimated_transit_time_hours=10.0,
            )
