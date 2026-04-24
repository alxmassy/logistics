"""Configuration for the prediction service.

Separate from ingestion config to maintain service isolation.
Both services share broker/Redis infrastructure but have
independent operational settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class PredictionSettings(BaseSettings):
    """Prediction service configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Kafka / Redpanda ---
    kafka_bootstrap_servers: str = "localhost:19092"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Topics ---
    telemetry_topic: str = "shipment-telemetry"
    threat_topic: str = "threat-signals"
    anomaly_alerts_topic: str = "anomaly-alerts"
    optimization_requests_topic: str = "optimization-requests"
    anomaly_alerts_partitions: int = 3
    optimization_requests_partitions: int = 3

    # --- Consumer ---
    consumer_group_id: str = "context-assembly"

    # --- Flink (used inside the Docker container) ---
    flink_kafka_bootstrap_servers: str = "redpanda:9092"
    flink_watermark_tolerance_seconds: int = 120
    flink_interval_join_minutes: int = 10


@lru_cache(maxsize=1)
def get_prediction_settings() -> PredictionSettings:
    """Return a cached singleton PredictionSettings instance."""
    return PredictionSettings()
