"""Tests for mock data generators.

Validates that generators produce valid schema-conformant payloads,
trajectories advance correctly, and failure injection works.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from services.ingestion.generators.routes import (
    RouteSeeder,
    generate_routes_for_shipment,
)
from services.ingestion.generators.telemetry import ShipmentSimulator
from services.ingestion.generators.threats import ThreatGenerator
from shared.schemas.telemetry import LatLon, ShipmentTelemetrySchema
from shared.schemas.threats import ThreatSignalSchema


# ---------------------------------------------------------------------------
# ShipmentSimulator
# ---------------------------------------------------------------------------

class TestShipmentSimulator:
    def test_generates_correct_count(self) -> None:
        sim = ShipmentSimulator(num_shipments=10)
        payloads = sim.generate_tick()
        assert len(payloads) == 10
        assert all(isinstance(p, ShipmentTelemetrySchema) for p in payloads)

    def test_coordinates_change_between_ticks(self) -> None:
        sim = ShipmentSimulator(num_shipments=3)
        tick1 = sim.generate_tick()
        tick2 = sim.generate_tick()

        # At least one shipment should have moved (probabilistic but near-certain)
        moved = any(
            t1.current_lat_lon != t2.current_lat_lon
            for t1, t2 in zip(tick1, tick2, strict=True)
        )
        assert moved, "Expected at least one shipment to change position between ticks"

    def test_fleet_recycling(self) -> None:
        """Shipments that arrive are replaced with new ones."""
        sim = ShipmentSimulator(num_shipments=5)
        initial_ids = {ship.shipment_id for ship in sim.fleet}

        # Force all shipments to arrive
        for ship in sim.fleet:
            ship.progress = 1.5

        sim.generate_tick()
        new_ids = {ship.shipment_id for ship in sim.fleet}

        # All should be replaced
        assert initial_ids.isdisjoint(new_ids), "Arrived shipments should be recycled"

    def test_active_positions_returns_all(self) -> None:
        sim = ShipmentSimulator(num_shipments=7)
        positions = sim.get_active_positions()
        assert len(positions) == 7
        assert all(isinstance(pos, LatLon) for pos, _ in positions)


# ---------------------------------------------------------------------------
# ThreatGenerator
# ---------------------------------------------------------------------------

class TestThreatGenerator:
    def test_generates_valid_threats(self) -> None:
        gen = ThreatGenerator(failure_injection_ratio=0.0)
        threats = gen.generate(count=5)
        assert len(threats) == 5
        assert all(isinstance(t, ThreatSignalSchema) for t in threats)

    def test_polygon_has_enough_vertices(self) -> None:
        gen = ThreatGenerator(failure_injection_ratio=0.0)
        threats = gen.generate(count=20)
        for t in threats:
            assert len(t.impact_polygon) >= 3

    def test_failure_injection_targets_shipment(self) -> None:
        """With 100% injection ratio, threats should center near active positions."""
        gen = ThreatGenerator(failure_injection_ratio=1.0)
        target_pos = LatLon(lat=31.23, lon=121.47)
        active_positions = [(target_pos, None)]

        threats = gen.generate(count=5, active_positions=active_positions)

        for t in threats:
            # At least one vertex should be within ~1 degree of the target
            close = any(
                abs(v.lat - target_pos.lat) < 1.5 and abs(v.lon - target_pos.lon) < 1.5
                for v in t.impact_polygon
            )
            assert close, f"Injected threat polygon should be near {target_pos}"

    def test_invalid_ratio_raises(self) -> None:
        with pytest.raises(ValueError):
            ThreatGenerator(failure_injection_ratio=1.5)
        with pytest.raises(ValueError):
            ThreatGenerator(failure_injection_ratio=-0.1)


# ---------------------------------------------------------------------------
# RouteSeeder
# ---------------------------------------------------------------------------

class TestRouteGeneration:
    def test_generates_routes_for_shipment(self) -> None:
        from uuid import uuid4
        routes = generate_routes_for_shipment(
            shipment_id=uuid4(),
            origin=LatLon(lat=31.23, lon=121.47),
            destination=LatLon(lat=51.92, lon=4.48),
        )
        assert 2 <= len(routes) <= 4
        for r in routes:
            assert len(r.path_nodes) >= 2
            assert r.base_cost > 0
            assert r.estimated_transit_time_hours > 0

    def test_explicit_alternative_count(self) -> None:
        from uuid import uuid4
        routes = generate_routes_for_shipment(
            shipment_id=uuid4(),
            origin=LatLon(lat=0.0, lon=0.0),
            destination=LatLon(lat=10.0, lon=10.0),
            num_alternatives=3,
        )
        assert len(routes) == 3

    @pytest.mark.asyncio
    async def test_route_seeder_seeds_redis(self) -> None:
        from uuid import uuid4
        mock_redis = AsyncMock()
        mock_redis.hset = AsyncMock()
        mock_redis.expire = AsyncMock()

        seeder = RouteSeeder(mock_redis)
        sid = uuid4()
        routes = await seeder.seed_for_shipment(
            shipment_id=sid,
            origin=LatLon(lat=31.23, lon=121.47),
            destination=LatLon(lat=51.92, lon=4.48),
        )

        assert seeder.seeded_count == 1
        assert len(routes) >= 2
        mock_redis.hset.assert_called_once()
        mock_redis.expire.assert_called_once()

        # Verify the Redis key format
        call_args = mock_redis.hset.call_args
        key = call_args[0][0]
        assert key == f"shipment_context:{sid}"
