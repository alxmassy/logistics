"""Shipment telemetry simulator.

Generates realistic shipment movement along predefined trade corridors.
Each tick advances shipments along their trajectory with random jitter
to simulate real-world GPS drift and vessel/truck deviations.

Corridors are based on actual high-volume global shipping lanes.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from uuid import uuid4

from shared.schemas.telemetry import (
    LatLon,
    PriorityTier,
    ShipmentTelemetrySchema,
    TransportMode,
)

# ---------------------------------------------------------------------------
# Realistic trade corridors: (origin, destination, typical transport mode)
# ---------------------------------------------------------------------------
TRADE_CORRIDORS: list[tuple[LatLon, LatLon, TransportMode]] = [
    # Shanghai → Rotterdam (SEA)
    (LatLon(lat=31.23, lon=121.47), LatLon(lat=51.92, lon=4.48), TransportMode.SEA),
    # Los Angeles → New York (ROAD)
    (LatLon(lat=33.94, lon=-118.41), LatLon(lat=40.71, lon=-74.01), TransportMode.ROAD),
    # Dubai → London (AIR)
    (LatLon(lat=25.25, lon=55.36), LatLon(lat=51.47, lon=-0.46), TransportMode.AIR),
    # Singapore → Sydney (SEA)
    (LatLon(lat=1.35, lon=103.82), LatLon(lat=-33.87, lon=151.21), TransportMode.SEA),
    # Frankfurt → Chicago (AIR)
    (LatLon(lat=50.11, lon=8.68), LatLon(lat=41.88, lon=-87.63), TransportMode.AIR),
    # Mumbai → Hamburg (SEA)
    (LatLon(lat=19.08, lon=72.88), LatLon(lat=53.55, lon=9.99), TransportMode.SEA),
    # São Paulo → Miami (ROAD/AIR)
    (LatLon(lat=-23.55, lon=-46.63), LatLon(lat=25.76, lon=-80.19), TransportMode.AIR),
    # Tokyo → Long Beach (SEA)
    (LatLon(lat=35.69, lon=139.69), LatLon(lat=33.77, lon=-118.19), TransportMode.SEA),
]

CARRIERS = [
    "Maersk", "MSC", "CMA CGM", "COSCO", "Hapag-Lloyd",
    "FedEx Freight", "DHL Express", "UPS Supply Chain",
    "Kuehne+Nagel", "DB Schenker",
]


class _ActiveShipment:
    """Internal state for a shipment being simulated."""

    __slots__ = (
        "shipment_id", "origin", "destination", "transport_mode",
        "carrier", "priority_tier", "progress", "speed",
    )

    def __init__(self) -> None:
        corridor = random.choice(TRADE_CORRIDORS)
        self.shipment_id = uuid4()
        self.origin = corridor[0]
        self.destination = corridor[1]
        self.transport_mode = corridor[2]
        self.carrier = random.choice(CARRIERS)
        self.priority_tier = random.choice(list(PriorityTier))
        # progress: 0.0 = at origin, 1.0 = at destination
        self.progress: float = random.uniform(0.0, 0.3)
        # speed: fraction of route covered per tick
        self.speed: float = random.uniform(0.005, 0.02)

    def current_position(self) -> LatLon:
        """Interpolate current position along the corridor with GPS jitter."""
        t = min(self.progress, 1.0)
        lat = self.origin.lat + (self.destination.lat - self.origin.lat) * t
        lon = self.origin.lon + (self.destination.lon - self.origin.lon) * t
        # Add realistic GPS jitter (±0.05 degrees ≈ ±5.5 km)
        lat += random.gauss(0, 0.02)
        lon += random.gauss(0, 0.02)
        # Clamp to valid ranges
        lat = max(-90.0, min(90.0, lat))
        lon = max(-180.0, min(180.0, lon))
        return LatLon(lat=round(lat, 6), lon=round(lon, 6))

    def advance(self) -> None:
        """Move the shipment forward along its trajectory."""
        self.progress += self.speed + random.gauss(0, 0.002)
        self.progress = max(0.0, self.progress)

    @property
    def arrived(self) -> bool:
        return self.progress >= 1.0


class ShipmentSimulator:
    """Generates telemetry ticks for a fleet of simulated shipments.

    Shipments that reach their destination are replaced with new ones
    to maintain a constant fleet size — simulating continuous operations.

    Args:
        num_shipments: Number of concurrent shipments to simulate.
    """

    def __init__(self, num_shipments: int = 50) -> None:
        self._num_shipments = num_shipments
        self._fleet: list[_ActiveShipment] = [
            _ActiveShipment() for _ in range(num_shipments)
        ]

    @property
    def fleet(self) -> list[_ActiveShipment]:
        """Expose the current fleet for failure injection (threat overlap)."""
        return self._fleet

    def generate_tick(self) -> list[ShipmentTelemetrySchema]:
        """Advance all shipments and return their current telemetry.

        Arrived shipments are recycled — replaced with fresh ones
        departing from a random corridor.
        """
        now = datetime.now(timezone.utc)
        payloads: list[ShipmentTelemetrySchema] = []

        for i, ship in enumerate(self._fleet):
            ship.advance()

            if ship.arrived:
                # Recycle: replace with a new shipment
                self._fleet[i] = _ActiveShipment()
                ship = self._fleet[i]

            # ETA: rough estimate based on remaining progress and speed
            remaining_hours = ((1.0 - ship.progress) / max(ship.speed, 0.001)) * 0.5
            from datetime import timedelta
            eta = now + timedelta(hours=remaining_hours)

            payloads.append(
                ShipmentTelemetrySchema(
                    shipment_id=ship.shipment_id,
                    current_lat_lon=ship.current_position(),
                    destination_lat_lon=ship.destination,
                    carrier=ship.carrier,
                    transport_mode=ship.transport_mode,
                    priority_tier=ship.priority_tier,
                    expected_eta=eta,
                    event_time=now,
                )
            )

        return payloads

    def get_active_positions(self) -> list[tuple[LatLon, _ActiveShipment]]:
        """Return current positions of all active shipments.

        Used by the threat generator for failure injection — creating
        threat polygons that intentionally overlap shipment coordinates.
        """
        return [(ship.current_position(), ship) for ship in self._fleet]
