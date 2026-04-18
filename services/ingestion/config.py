"""Centralized configuration for the ingestion service.

All settings are loaded from environment variables (or a `.env` file).
This is the single source of truth — no hardcoded values elsewhere.

Usage:
    from services.ingestion.config import get_settings
    settings = get_settings()
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ingestion service configuration.

    All fields have sensible defaults matching the local Docker Compose
    setup in `infra/docker-compose.yml`. Override via environment variables
    or a `.env` file in the project root.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Kafka / Redpanda ---
    kafka_bootstrap_servers: str = "localhost:19092"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Topic Configuration ---
    telemetry_topic: str = "shipment-telemetry"
    threat_topic: str = "threat-signals"
    telemetry_partitions: int = 6
    threat_partitions: int = 3
    anomaly_alerts_topic: str = "anomaly-alerts"
    anomaly_alerts_partitions: int = 3
    optimization_requests_topic: str = "optimization-requests"
    optimization_requests_partitions: int = 3
    reroute_decisions_topic: str = "reroute-decisions"
    reroute_decisions_partitions: int = 3

    # --- Generator Defaults ---
    generator_rate_per_sec: int = 100
    generator_num_shipments: int = 50
    failure_injection_ratio: float = 0.1

    # --- API Server ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance.

    Using lru_cache ensures we only parse env vars once per process.
    """
    return Settings()
