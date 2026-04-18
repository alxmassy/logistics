# =============================================================================
# PyFlink Collision Detection — Docker Image
#
# Uses full Python image (not slim) because apache-flink requires:
#   - JDK headers (for pemja C extension)
#   - Build tools (gcc, make)
#
# Build:
#   docker compose -f infra/docker-compose.yml --profile flink build flink-job
# =============================================================================

FROM python:3.10-bookworm

# Install JRE 17 (pre-compiled wheels exist for Python 3.10)
RUN apt-get update && \
    apt-get install -y --no-install-recommends default-jre-headless wget && \
    rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Install PyFlink (will use pre-compiled wheels for 3.10)
RUN pip install --no-cache-dir apache-flink==1.18.1

# Download Flink Kafka SQL connector JAR
RUN mkdir -p /opt/flink-connectors && \
    wget -q -P /opt/flink-connectors/ \
    https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.18/flink-sql-connector-kafka-3.1.0-1.18.jar

WORKDIR /app

# Copy the Flink job code and geometry module
COPY services/prediction/flink_job/collision_job.py .
COPY services/prediction/flink_job/geometry.py .

ENV PYTHONUNBUFFERED=1
ENV KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
ENV TELEMETRY_TOPIC=shipment-telemetry
ENV THREAT_TOPIC=threat-signals
ENV ANOMALY_ALERTS_TOPIC=anomaly-alerts
ENV WATERMARK_TOLERANCE_MS=120000
ENV THREAT_TTL_S=600
ENV FLINK_TELEMETRY_GROUP_ID=flink-collision-telemetry
ENV FLINK_THREAT_GROUP_ID=flink-collision-threats
ENV KAFKA_CONNECTOR_JAR=file:///opt/flink-connectors/flink-sql-connector-kafka-3.1.0-1.18.jar

CMD ["python", "collision_job.py"]
