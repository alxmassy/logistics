"""FastAPI application factory with lifespan-managed resources.

The lifespan context manager initialises and tears down:
  - KafkaProducerService (Redpanda connection)
  - Redis async client

Both are stored on `app.state` and retrieved via dependency injection
(see `dependencies.py`).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.ingestion.api.routes import telemetry, threats
from services.ingestion.config import get_settings
from services.ingestion.producers.kafka import KafkaProducerService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the lifecycle of shared resources.

    Starts the Kafka producer and Redis client before the first request,
    and ensures clean shutdown when the process exits.
    """
    settings = get_settings()

    # --- Kafka Producer ---
    producer = KafkaProducerService(settings)
    await producer.start()
    app.state.producer = producer

    # --- Redis ---
    redis_client = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    app.state.redis = redis_client

    logger.info("Ingestion API resources initialised")

    yield

    # --- Shutdown ---
    await producer.stop()
    await redis_client.aclose()
    logger.info("Ingestion API resources shut down")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Logistics Ingestion API",
        description="High-throughput ingestion endpoints for shipment telemetry and threat signals.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — the React frontend will need this
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount route modules
    app.include_router(telemetry.router)
    app.include_router(threats.router)

    return app
