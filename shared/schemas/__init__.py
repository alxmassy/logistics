"""Shared Pydantic v2 schemas for the logistics pipeline.

These schemas define the data contracts used across all services:
ingestion, prediction (Flink), optimization (Vertex AI), and the frontend.

Usage:
    from shared.schemas import ShipmentTelemetrySchema, ThreatSignalSchema
"""

from shared.schemas.anomaly import AnomalyAlertSchema
from shared.schemas.optimization import FallbackRoute, LLMOptimizationRequest
from shared.schemas.routes import PrecomputedRouteSchema
from shared.schemas.telemetry import (
    LatLon,
    PriorityTier,
    ShipmentTelemetrySchema,
    TransportMode,
)
from shared.schemas.threats import ThreatSignalSchema, ThreatType

__all__ = [
    "LatLon",
    "TransportMode",
    "PriorityTier",
    "ShipmentTelemetrySchema",
    "ThreatType",
    "ThreatSignalSchema",
    "PrecomputedRouteSchema",
    "AnomalyAlertSchema",
    "FallbackRoute",
    "LLMOptimizationRequest",
]
