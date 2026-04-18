"""Tests for the spatial geometry module.

Validates haversine distance against known values, point-in-polygon
with various polygon shapes, bounding-box containment, and the
deterministic delay estimation function.
"""

from __future__ import annotations

import math

import pytest

from services.prediction.flink_job.geometry import (
    bounding_box_contains,
    check_collision,
    estimate_delay,
    haversine_distance,
    point_in_polygon,
    polygon_centroid,
)


# ---------------------------------------------------------------------------
# Haversine Distance
# ---------------------------------------------------------------------------

class TestHaversineDistance:
    def test_london_to_paris(self) -> None:
        """London (51.5074, -0.1278) → Paris (48.8566, 2.3522) ≈ 343 km."""
        london = (51.5074, -0.1278)
        paris = (48.8566, 2.3522)
        distance = haversine_distance(london, paris)
        assert 340 < distance < 350, f"Expected ~343km, got {distance}"

    def test_same_point_is_zero(self) -> None:
        point = (40.0, -74.0)
        assert haversine_distance(point, point) == pytest.approx(0.0)

    def test_antipodal_points(self) -> None:
        """North pole to south pole ≈ 20,015 km (half circumference)."""
        north = (90.0, 0.0)
        south = (-90.0, 0.0)
        distance = haversine_distance(north, south)
        assert 20000 < distance < 20050

    def test_new_york_to_tokyo(self) -> None:
        """NYC (40.7128, -74.0060) → Tokyo (35.6762, 139.6503) ≈ 10,838 km."""
        nyc = (40.7128, -74.0060)
        tokyo = (35.6762, 139.6503)
        distance = haversine_distance(nyc, tokyo)
        assert 10800 < distance < 10900


# ---------------------------------------------------------------------------
# Bounding Box
# ---------------------------------------------------------------------------

class TestBoundingBox:
    SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]

    def test_point_inside(self) -> None:
        assert bounding_box_contains(self.SQUARE, (5.0, 5.0)) is True

    def test_point_outside(self) -> None:
        assert bounding_box_contains(self.SQUARE, (15.0, 5.0)) is False

    def test_point_on_boundary(self) -> None:
        assert bounding_box_contains(self.SQUARE, (0.0, 0.0)) is True
        assert bounding_box_contains(self.SQUARE, (10.0, 10.0)) is True

    def test_empty_polygon(self) -> None:
        assert bounding_box_contains([], (5.0, 5.0)) is False


# ---------------------------------------------------------------------------
# Point-in-Polygon (Ray Casting)
# ---------------------------------------------------------------------------

class TestPointInPolygon:
    # Simple unit square
    SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]

    # Triangle
    TRIANGLE = [(0.0, 0.0), (5.0, 10.0), (10.0, 0.0)]

    # L-shape (concave)
    L_SHAPE = [
        (0.0, 0.0), (0.0, 10.0), (5.0, 10.0),
        (5.0, 5.0), (10.0, 5.0), (10.0, 0.0),
    ]

    def test_inside_square(self) -> None:
        assert point_in_polygon(self.SQUARE, (5.0, 5.0)) is True

    def test_outside_square(self) -> None:
        assert point_in_polygon(self.SQUARE, (15.0, 5.0)) is False

    def test_inside_triangle(self) -> None:
        assert point_in_polygon(self.TRIANGLE, (5.0, 3.0)) is True

    def test_outside_triangle(self) -> None:
        assert point_in_polygon(self.TRIANGLE, (1.0, 9.0)) is False

    def test_inside_l_shape(self) -> None:
        # Bottom-left quadrant of the L
        assert point_in_polygon(self.L_SHAPE, (2.0, 2.0)) is True

    def test_outside_l_shape_concavity(self) -> None:
        # Inside the bounding box but outside the L (in the concave notch)
        assert point_in_polygon(self.L_SHAPE, (7.0, 7.0)) is False

    def test_insufficient_vertices(self) -> None:
        assert point_in_polygon([(0.0, 0.0), (1.0, 1.0)], (0.5, 0.5)) is False


# ---------------------------------------------------------------------------
# Check Collision (two-stage: bbox → pip)
# ---------------------------------------------------------------------------

class TestCheckCollision:
    POLYGON = [(30.0, 120.0), (32.0, 120.0), (32.0, 123.0), (30.0, 123.0)]

    def test_inside_polygon(self) -> None:
        assert check_collision(31.0, 121.5, self.POLYGON) is True

    def test_outside_polygon(self) -> None:
        assert check_collision(40.0, 121.5, self.POLYGON) is False

    def test_outside_bbox(self) -> None:
        """Point far from polygon — should be filtered by bounding box."""
        assert check_collision(0.0, 0.0, self.POLYGON) is False


# ---------------------------------------------------------------------------
# Polygon Centroid
# ---------------------------------------------------------------------------

class TestPolygonCentroid:
    def test_square_centroid(self) -> None:
        square = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
        centroid = polygon_centroid(square)
        assert centroid == pytest.approx((5.0, 5.0))

    def test_empty_polygon(self) -> None:
        assert polygon_centroid([]) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# Delay Estimation
# ---------------------------------------------------------------------------

class TestEstimateDelay:
    def test_sea_higher_than_air(self) -> None:
        """SEA multiplier (1.5) should produce more delay than AIR (0.5)."""
        sea_delay = estimate_delay(5, "SEA")
        air_delay = estimate_delay(5, "AIR")
        assert sea_delay > air_delay

    def test_higher_severity_more_delay(self) -> None:
        low = estimate_delay(1, "ROAD")
        high = estimate_delay(10, "ROAD")
        assert high > low

    def test_deterministic(self) -> None:
        """Same inputs should always produce the same output."""
        d1 = estimate_delay(7, "SEA")
        d2 = estimate_delay(7, "SEA")
        assert d1 == d2

    def test_minimum_delay_is_non_negative(self) -> None:
        assert estimate_delay(1, "AIR") >= 0.0

    def test_proximity_increases_delay(self) -> None:
        """Point close to threat center gets more delay than distant point."""
        polygon = [(30.0, 120.0), (32.0, 120.0), (32.0, 123.0), (30.0, 123.0)]
        close = estimate_delay(5, "ROAD", 31.0, 121.5, polygon)
        far = estimate_delay(5, "ROAD", 31.0, 150.0, polygon)
        assert close > far

    def test_unknown_mode_defaults_to_one(self) -> None:
        """Unknown transport mode should use multiplier of 1.0."""
        default = estimate_delay(5, "UNKNOWN")
        road = estimate_delay(5, "ROAD")
        assert default == road
