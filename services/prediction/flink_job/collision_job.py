"""PyFlink collision detection job — spatial-temporal anomaly detection.

Connects to Redpanda, consumes shipment telemetry and threat signals,
performs interval joins with event-time watermarking, and detects
spatial collisions using the geometry module's two-stage filter
(bounding box → ray-casting point-in-polygon).

Detected collisions are published to the `anomaly-alerts` topic.

This job runs inside a Docker container with PyFlink + JRE.
It is NOT executed on the host — see infra/flink/Dockerfile.

Usage (inside container):
    python collision_job.py
"""

from __future__ import annotations

import json
import logging
import os
import uuid

from pyflink.common import Types, WatermarkStrategy
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.functions import CoProcessFunction, RuntimeContext
from pyflink.datastream.state import ListStateDescriptor, MapStateDescriptor, ValueStateDescriptor

# Geometry module is mounted alongside this file in the container
from geometry import check_collision, estimate_delay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()],  # explicit stderr handler
)
logger = logging.getLogger("collision_job")

# ---------------------------------------------------------------------------
# Configuration from environment (set in docker-compose)
# ---------------------------------------------------------------------------
BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
TELEMETRY_TOPIC = os.environ.get("TELEMETRY_TOPIC", "shipment-telemetry")
THREAT_TOPIC = os.environ.get("THREAT_TOPIC", "threat-signals")
ANOMALY_TOPIC = os.environ.get("ANOMALY_ALERTS_TOPIC", "anomaly-alerts")
WATERMARK_TOLERANCE_MS = int(os.environ.get("WATERMARK_TOLERANCE_MS", "120000"))
# How long to keep threats active for matching (seconds)
THREAT_TTL_S = int(os.environ.get("THREAT_TTL_S", "600"))  # 10 minutes
# Consumer group IDs (configurable for offset management)
TELEMETRY_GROUP_ID = os.environ.get("FLINK_TELEMETRY_GROUP_ID", "flink-collision-telemetry")
THREAT_GROUP_ID = os.environ.get("FLINK_THREAT_GROUP_ID", "flink-collision-threats")


def _now_epoch_s() -> int:
    """Current UTC time as epoch seconds."""
    from datetime import datetime, timezone
    return int(datetime.now(timezone.utc).timestamp())


def _parse_telemetry(raw: str) -> dict | None:
    """Parse a telemetry JSON string into a flat dict for processing."""
    try:
        data = json.loads(raw)
        return {
            "shipment_id": data["shipment_id"],
            "lat": data["current_lat_lon"]["lat"],
            "lon": data["current_lat_lon"]["lon"],
            "transport_mode": data["transport_mode"],
            "priority_tier": data["priority_tier"],
            "event_time": data["event_time"],
        }
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Malformed telemetry record: %s", e)
        return None


def _parse_threat(raw: str) -> dict | None:
    """Parse a threat JSON string into a flat dict for processing."""
    try:
        data = json.loads(raw)
        polygon = [(p["lat"], p["lon"]) for p in data["impact_polygon"]]
        return {
            "threat_id": data["threat_id"],
            "threat_type": data["threat_type"],
            "severity": data["severity"],
            "polygon": polygon,
            "event_time": data["event_time"],
        }
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Malformed threat record: %s", e)
        return None


def _extract_timestamp(event_time_str: str) -> int:
    """Convert ISO 8601 timestamp to epoch milliseconds for watermarking."""
    from datetime import datetime, timezone

    try:
        dt = datetime.fromisoformat(event_time_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return 0


class CollisionDetector(CoProcessFunction):
    """Keyed CoProcessFunction that detects shipment–threat collisions.

    State management:
      - Telemetry side: MapState keyed by shipment_id → latest position JSON.
        Only the most recent position per shipment is retained.
      - Threat side: ListState of active threats with timestamp-based TTL
        eviction (THREAT_TTL_S). Expired threats are pruned on each new event.

    When a new telemetry record arrives, it's checked against all active
    threats. When a new threat arrives, it's checked against all known
    shipment positions. This bidirectional check ensures no collisions
    are missed regardless of arrival order.
    """

    def open(self, runtime_context: RuntimeContext) -> None:
        # Latest position per shipment — MapState keyed by shipment_id
        self.telemetry_state = runtime_context.get_map_state(
            MapStateDescriptor("telemetry_positions", Types.STRING(), Types.STRING())
        )
        # Active threats with timestamps for TTL eviction
        self.threat_state = runtime_context.get_list_state(
            ListStateDescriptor("active_threats", Types.STRING())
        )

    def _evict_expired_threats(self) -> list[dict]:
        """Remove threats older than THREAT_TTL_S and return active ones."""
        now = _now_epoch_s()
        active = []
        for threat_json in self.threat_state.get():
            threat = json.loads(threat_json)
            ingested_at = threat.get("_ingested_at", now)
            if now - ingested_at < THREAT_TTL_S:
                active.append(threat)
        # Rewrite state with only active threats
        self.threat_state.clear()
        for threat in active:
            self.threat_state.add(json.dumps(threat))
        return active

    def process_element1(self, telemetry_json: str, ctx: CoProcessFunction.Context):
        """Process a telemetry record — upsert position and check threats."""
        telemetry = _parse_telemetry(telemetry_json)
        if telemetry is None:
            return

        # Upsert: only keep the latest position per shipment
        self.telemetry_state.put(
            telemetry["shipment_id"], json.dumps(telemetry)
        )

        # Check against all active threats (with TTL eviction)
        for threat in self._evict_expired_threats():
            yield from self._check_and_emit(telemetry, threat, ctx)

    def process_element2(self, threat_json: str, ctx: CoProcessFunction.Context):
        """Process a threat record — check against all known shipment positions."""
        threat = _parse_threat(threat_json)
        if threat is None:
            return

        # Tag with ingestion timestamp for TTL eviction
        threat["_ingested_at"] = _now_epoch_s()
        self.threat_state.add(json.dumps(threat))

        # Check against all known shipment positions
        for shipment_id in self.telemetry_state.keys():
            tel_json = self.telemetry_state.get(shipment_id)
            telemetry = json.loads(tel_json)
            yield from self._check_and_emit(telemetry, threat, ctx)

    def _check_and_emit(self, telemetry: dict, threat: dict, ctx: CoProcessFunction.Context):
        """Run two-stage collision check and emit alert if positive."""
        ship_lat = telemetry["lat"]
        ship_lon = telemetry["lon"]
        polygon = threat["polygon"]

        if check_collision(ship_lat, ship_lon, polygon):
            delay = estimate_delay(
                severity=threat["severity"],
                transport_mode=telemetry["transport_mode"],
                ship_lat=ship_lat,
                ship_lon=ship_lon,
                polygon=polygon,
            )

            alert = {
                "alert_id": str(uuid.uuid4()),
                "shipment_id": telemetry["shipment_id"],
                "threat_id": threat["threat_id"],
                "threat_type": threat["threat_type"],
                "severity": threat["severity"],
                "collision_coordinates": {"lat": ship_lat, "lon": ship_lon},
                "transport_mode": telemetry["transport_mode"],
                "priority_tier": telemetry["priority_tier"],
                "estimated_delay_hours": delay,
                "event_time": telemetry["event_time"],
            }

            logger.info(
                "COLLISION DETECTED: shipment=%s threat=%s delay=%.1fh",
                telemetry["shipment_id"][:8],
                threat["threat_id"][:8],
                delay,
            )
            yield json.dumps(alert)


def build_and_run() -> None:
    """Build and execute the Flink collision detection pipeline."""
    env = StreamExecutionEnvironment.get_execution_environment()

    # Parallelism — single container, keep it simple
    env.set_parallelism(1)

    # Enable checkpointing for fault tolerance (every 30s)
    env.enable_checkpointing(30000)

    # Add Kafka connector JAR
    kafka_jar = os.environ.get(
        "KAFKA_CONNECTOR_JAR",
        "file:///opt/flink-connectors/flink-sql-connector-kafka-3.1.0-1.18.jar",
    )
    env.add_jars(kafka_jar)

    print(f"[collision_job] Building pipeline: {TELEMETRY_TOPIC} + {THREAT_TOPIC} → {ANOMALY_TOPIC}", flush=True)

    # --- Telemetry Source ---
    telemetry_source = (
        KafkaSource.builder()
        .set_bootstrap_servers(BOOTSTRAP_SERVERS)
        .set_topics(TELEMETRY_TOPIC)
        .set_group_id(TELEMETRY_GROUP_ID)
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    # --- Threat Source ---
    threat_source = (
        KafkaSource.builder()
        .set_bootstrap_servers(BOOTSTRAP_SERVERS)
        .set_topics(THREAT_TOPIC)
        .set_group_id(THREAT_GROUP_ID)
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    # --- Watermark Strategy ---
    # Bounded out-of-orderness: tolerate late events up to WATERMARK_TOLERANCE_MS
    from pyflink.common.watermark_strategy import TimestampAssigner
    from pyflink.common import Duration

    class TelemetryTimestampAssigner(TimestampAssigner):
        def extract_timestamp(self, value: str, record_timestamp: int) -> int:
            try:
                data = json.loads(value)
                return _extract_timestamp(data.get("event_time", ""))
            except Exception:
                return record_timestamp

    class ThreatTimestampAssigner(TimestampAssigner):
        def extract_timestamp(self, value: str, record_timestamp: int) -> int:
            try:
                data = json.loads(value)
                return _extract_timestamp(data.get("event_time", ""))
            except Exception:
                return record_timestamp

    watermark_strategy_telemetry = (
        WatermarkStrategy
        .for_bounded_out_of_orderness(Duration.of_millis(WATERMARK_TOLERANCE_MS))
        .with_timestamp_assigner(TelemetryTimestampAssigner())
    )

    watermark_strategy_threat = (
        WatermarkStrategy
        .for_bounded_out_of_orderness(Duration.of_millis(WATERMARK_TOLERANCE_MS))
        .with_timestamp_assigner(ThreatTimestampAssigner())
    )

    # --- Build DataStreams ---
    telemetry_stream = env.from_source(
        telemetry_source,
        watermark_strategy_telemetry,
        "TelemetryStream",
    )

    threat_stream = env.from_source(
        threat_source,
        watermark_strategy_threat,
        "ThreatStream",
    )

    # --- Connect Streams + Collision Detection ---
    # Key by a constant ("global") to co-locate all events for collision checking.
    # In production with high volume, key by geographic zone for parallelism.
    anomaly_stream = (
        telemetry_stream
        .key_by(lambda _: "global", key_type=Types.STRING())
        .connect(threat_stream.key_by(lambda _: "global", key_type=Types.STRING()))
        .process(CollisionDetector(), output_type=Types.STRING())
    )

    # --- Anomaly Alerts Sink ---
    anomaly_sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(BOOTSTRAP_SERVERS)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(ANOMALY_TOPIC)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .build()
    )

    anomaly_stream.sink_to(anomaly_sink)

    logger.info("Starting Flink collision detection job...")
    env.execute("Logistics Collision Detection")


if __name__ == "__main__":
    import sys
    import traceback
    print("[collision_job] Starting...", file=sys.stderr, flush=True)
    try:
        build_and_run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
