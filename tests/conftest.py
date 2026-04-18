"""Shared test fixtures for the logistics test suite."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.schemas.telemetry import (
    LatLon,
    PriorityTier,
    ShipmentTelemetrySchema,
    TransportMode,
)
from shared.schemas.threats import ThreatSignalSchema, ThreatType


@pytest.fixture
def sample_latlon() -> LatLon:
    """A valid coordinate (Shanghai)."""
    return LatLon(lat=31.23, lon=121.47)


@pytest.fixture
def sample_telemetry() -> ShipmentTelemetrySchema:
    """A valid shipment telemetry payload."""
    now = datetime.now(timezone.utc)
    from datetime import timedelta

    return ShipmentTelemetrySchema(
        shipment_id=uuid4(),
        current_lat_lon=LatLon(lat=31.23, lon=121.47),
        destination_lat_lon=LatLon(lat=51.92, lon=4.48),
        carrier="Maersk",
        transport_mode=TransportMode.SEA,
        priority_tier=PriorityTier.HIGH,
        expected_eta=now + timedelta(hours=48),
        event_time=now,
    )


@pytest.fixture
def sample_threat() -> ThreatSignalSchema:
    """A valid threat signal payload."""
    return ThreatSignalSchema(
        threat_id=uuid4(),
        threat_type=ThreatType.WEATHER,
        severity=7,
        impact_polygon=[
            LatLon(lat=30.0, lon=120.0),
            LatLon(lat=32.0, lon=120.0),
            LatLon(lat=32.0, lon=123.0),
        ],
        event_time=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_producer() -> AsyncMock:
    """Mocked KafkaProducerService — all sends are no-ops."""
    producer = AsyncMock()
    producer.send_telemetry = AsyncMock()
    producer.send_threat = AsyncMock()
    producer.send_telemetry_batch = AsyncMock(side_effect=lambda payloads: len(payloads))
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    return producer


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mocked async Redis client."""
    redis_mock = AsyncMock()
    redis_mock.hset = AsyncMock()
    redis_mock.expire = AsyncMock()
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.aclose = AsyncMock()
    return redis_mock
