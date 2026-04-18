"""Threat signal generator.

Produces random weather, congestion, and infrastructure disruption events.
Supports configurable failure injection: intentionally generates threat
polygons that overlap active shipment coordinates to trigger downstream
Flink spatial-temporal collision detection.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from uuid import uuid4

from shared.schemas.telemetry import LatLon
from shared.schemas.threats import ThreatSignalSchema, ThreatType


def _random_polygon(center_lat: float, center_lon: float, radius_deg: float = 0.5) -> list[LatLon]:
    """Generate a rough polygon around a center point.

    Creates a 4-6 vertex convex polygon within `radius_deg` of the center.
    This is intentionally simple — we're simulating threat zones, not
    doing computational geometry.
    """
    num_vertices = random.randint(4, 6)
    vertices: list[LatLon] = []
    import math

    for i in range(num_vertices):
        angle = (2 * math.pi * i) / num_vertices + random.uniform(-0.3, 0.3)
        r = radius_deg * random.uniform(0.5, 1.0)
        lat = center_lat + r * math.cos(angle)
        lon = center_lon + r * math.sin(angle)
        # Clamp to valid ranges
        lat = max(-90.0, min(90.0, lat))
        lon = max(-180.0, min(180.0, lon))
        vertices.append(LatLon(lat=round(lat, 6), lon=round(lon, 6)))

    return vertices


class ThreatGenerator:
    """Generates threat signals, optionally targeting active shipments.

    Args:
        failure_injection_ratio: Fraction of threats (0.0–1.0) that should
            intentionally overlap with active shipment positions. Set to 0.0
            to generate purely random threats.
    """

    def __init__(self, failure_injection_ratio: float = 0.1) -> None:
        if not 0.0 <= failure_injection_ratio <= 1.0:
            raise ValueError("failure_injection_ratio must be between 0.0 and 1.0")
        self._injection_ratio = failure_injection_ratio

    def generate(
        self,
        count: int = 1,
        active_positions: list[tuple[LatLon, object]] | None = None,
    ) -> list[ThreatSignalSchema]:
        """Generate `count` threat signals.

        Args:
            count: Number of threats to generate.
            active_positions: List of (position, shipment) tuples from the
                ShipmentSimulator. Required for failure injection mode.

        Returns:
            List of ThreatSignalSchema payloads.
        """
        now = datetime.now(timezone.utc)
        threats: list[ThreatSignalSchema] = []

        for _ in range(count):
            inject = (
                random.random() < self._injection_ratio
                and active_positions
                and len(active_positions) > 0
            )

            if inject:
                # Pick a random active shipment and center the threat on it
                target_pos, _ = random.choice(active_positions)
                center_lat = target_pos.lat
                center_lon = target_pos.lon
                # Smaller radius to guarantee overlap
                polygon = _random_polygon(center_lat, center_lon, radius_deg=0.3)
                # Injected threats tend to be more severe
                severity = random.randint(6, 10)
            else:
                # Random threat somewhere in the world
                center_lat = random.uniform(-60.0, 70.0)
                center_lon = random.uniform(-170.0, 170.0)
                polygon = _random_polygon(center_lat, center_lon, radius_deg=random.uniform(0.2, 2.0))
                severity = random.randint(1, 10)

            threats.append(
                ThreatSignalSchema(
                    threat_id=uuid4(),
                    threat_type=random.choice(list(ThreatType)),
                    severity=severity,
                    impact_polygon=polygon,
                    event_time=now,
                )
            )

        return threats
