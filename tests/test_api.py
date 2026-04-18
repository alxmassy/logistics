"""Integration tests for FastAPI ingestion endpoints.

Uses httpx AsyncClient with mocked Kafka producer and Redis
to test request validation, response format, and producer calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from services.ingestion.api.app import create_app
from services.ingestion.api.dependencies import get_producer, get_redis
from shared.schemas.telemetry import LatLon


@pytest.fixture
def mock_producer() -> AsyncMock:
    producer = AsyncMock()
    producer.send_telemetry = AsyncMock()
    producer.send_threat = AsyncMock()
    producer.send_telemetry_batch = AsyncMock(side_effect=lambda payloads: len(payloads))
    return producer


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis_mock = AsyncMock()
    redis_mock.ping = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
def test_app(mock_producer: AsyncMock, mock_redis: AsyncMock) -> AsyncClient:
    """Create a test client with mocked dependencies.

    Overrides the lifespan-managed producer and redis with mocks
    via FastAPI dependency overrides.
    """
    app = create_app()
    app.dependency_overrides[get_producer] = lambda: mock_producer
    app.dependency_overrides[get_redis] = lambda: mock_redis
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# POST /ingest/telemetry
# ---------------------------------------------------------------------------

class TestTelemetryEndpoint:
    @pytest.mark.asyncio
    async def test_valid_batch(self, test_app: AsyncClient, mock_producer: AsyncMock) -> None:
        now = datetime.now(timezone.utc).isoformat()
        eta = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

        payload = [
            {
                "shipment_id": str(uuid4()),
                "current_lat_lon": {"lat": 31.23, "lon": 121.47},
                "destination_lat_lon": {"lat": 51.92, "lon": 4.48},
                "carrier": "Maersk",
                "transport_mode": "SEA",
                "priority_tier": "HIGH",
                "expected_eta": eta,
                "event_time": now,
            }
        ]

        async with test_app as client:
            resp = await client.post("/ingest/telemetry", json=payload)

        assert resp.status_code == 200
        body = resp.json()
        assert body["accepted"] == 1
        assert body["status"] == "ok"
        mock_producer.send_telemetry_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_malformed_payload_422(self, test_app: AsyncClient) -> None:
        payload = [
            {
                "shipment_id": "not-a-uuid",
                "current_lat_lon": {"lat": 999, "lon": 0},  # invalid lat
                "carrier": "",
            }
        ]

        async with test_app as client:
            resp = await client.post("/ingest/telemetry", json=payload)

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_batch(self, test_app: AsyncClient, mock_producer: AsyncMock) -> None:
        async with test_app as client:
            resp = await client.post("/ingest/telemetry", json=[])

        assert resp.status_code == 200
        body = resp.json()
        assert body["accepted"] == 0


# ---------------------------------------------------------------------------
# POST /ingest/threat
# ---------------------------------------------------------------------------

class TestThreatEndpoint:
    @pytest.mark.asyncio
    async def test_valid_threat(self, test_app: AsyncClient, mock_producer: AsyncMock) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "threat_id": str(uuid4()),
            "threat_type": "WEATHER",
            "severity": 8,
            "impact_polygon": [
                {"lat": 30.0, "lon": 120.0},
                {"lat": 32.0, "lon": 120.0},
                {"lat": 32.0, "lon": 123.0},
            ],
            "event_time": now,
        }

        async with test_app as client:
            resp = await client.post("/ingest/threat", json=payload)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert "threat_id" in body
        mock_producer.send_threat.assert_called_once()

    @pytest.mark.asyncio
    async def test_severity_out_of_range(self, test_app: AsyncClient) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "threat_id": str(uuid4()),
            "threat_type": "CONGESTION",
            "severity": 15,
            "impact_polygon": [
                {"lat": 0, "lon": 0},
                {"lat": 1, "lon": 0},
                {"lat": 1, "lon": 1},
            ],
            "event_time": now,
        }

        async with test_app as client:
            resp = await client.post("/ingest/threat", json=payload)

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_threat_type(self, test_app: AsyncClient) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "threat_id": str(uuid4()),
            "threat_type": "ALIEN_INVASION",
            "severity": 5,
            "impact_polygon": [
                {"lat": 0, "lon": 0},
                {"lat": 1, "lon": 0},
                {"lat": 1, "lon": 1},
            ],
            "event_time": now,
        }

        async with test_app as client:
            resp = await client.post("/ingest/threat", json=payload)

        assert resp.status_code == 422
