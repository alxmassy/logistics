"""FastAPI dependency injection for shared resources.

Pulls the Kafka producer and Redis client from `app.state`,
which are initialised in the lifespan context manager (see `app.py`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    import redis.asyncio as aioredis

    from services.ingestion.producers.kafka import KafkaProducerService


def get_producer(request: Request) -> KafkaProducerService:
    """Retrieve the Kafka producer from application state."""
    return request.app.state.producer  # type: ignore[no-any-return]


def get_redis(request: Request) -> aioredis.Redis:
    """Retrieve the async Redis client from application state."""
    return request.app.state.redis  # type: ignore[no-any-return]
