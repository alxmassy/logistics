"""Typer CLI for the ingestion service.

Standalone entrypoint for managing the mock data generators,
Redpanda topics, and infrastructure health checks.

Usage:
    python -m services.ingestion generate --rate 10 --shipments 5 --duration 30
    python -m services.ingestion topics
    python -m services.ingestion health
"""

from __future__ import annotations

import asyncio
import logging
import sys

import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table

from services.ingestion.config import get_settings

app = typer.Typer(
    name="logistics-ingest",
    help="Logistics ingestion service CLI — mock generators, topic management, and health checks.",
    no_args_is_help=True,
)
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _build_stats_table(
    telemetry_sent: int,
    threats_sent: int,
    routes_seeded: int,
    elapsed: float,
    rate: float,
) -> Table:
    """Build a Rich table for live stats display."""
    table = Table(title="Ingestion Generator — Live Stats", expand=True)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green", justify="right")
    table.add_row("Telemetry records sent", f"{telemetry_sent:,}")
    table.add_row("Threat signals sent", f"{threats_sent:,}")
    table.add_row("Routes seeded (Redis)", f"{routes_seeded:,}")
    table.add_row("Elapsed time", f"{elapsed:.1f}s")
    table.add_row("Effective rate", f"{rate:.1f} msg/s")
    return table


async def _run_generator(
    num_shipments: int,
    rate_per_sec: int,
    duration: int,
    inject_failures: bool,
) -> None:
    """Core async generator loop."""
    import time

    import redis.asyncio as aioredis

    from services.ingestion.generators.routes import RouteSeeder
    from services.ingestion.generators.telemetry import ShipmentSimulator
    from services.ingestion.generators.threats import ThreatGenerator
    from services.ingestion.producers.kafka import KafkaProducerService

    settings = get_settings()

    # --- Initialise resources ---
    producer = KafkaProducerService(settings)
    await producer.start()

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    route_seeder = RouteSeeder(redis_client)

    simulator = ShipmentSimulator(num_shipments=num_shipments)
    threat_gen = ThreatGenerator(
        failure_injection_ratio=settings.failure_injection_ratio if inject_failures else 0.0,
    )

    # Seed initial routes for the starting fleet
    console.print("[bold blue]Seeding initial routes into Redis...[/]")
    for ship in simulator.fleet:
        await route_seeder.seed_for_shipment(
            ship.shipment_id, ship.origin, ship.destination,
        )
    console.print(f"[green]✓ Seeded routes for {num_shipments} shipments[/]")

    # --- Generator loop ---
    telemetry_sent = 0
    threats_sent = 0
    start_time = time.monotonic()
    tick_interval = 1.0 / max(rate_per_sec / max(num_shipments, 1), 0.1)

    try:
        with Live(
            _build_stats_table(0, 0, route_seeder.seeded_count, 0.0, 0.0),
            console=console,
            refresh_per_second=2,
        ) as live:
            while True:
                elapsed = time.monotonic() - start_time
                if duration > 0 and elapsed >= duration:
                    break

                # Generate telemetry tick
                telemetry_payloads = simulator.generate_tick()
                for payload in telemetry_payloads:
                    await producer.send_telemetry(payload)
                telemetry_sent += len(telemetry_payloads)

                # Generate threats (roughly 1 per 5 ticks)
                if telemetry_sent % 5 == 0:
                    active_positions = simulator.get_active_positions()
                    threat_payloads = threat_gen.generate(
                        count=1,
                        active_positions=active_positions if inject_failures else None,
                    )
                    for threat in threat_payloads:
                        await producer.send_threat(threat)
                    threats_sent += len(threat_payloads)

                # Seed routes for any recycled shipments
                for ship in simulator.fleet:
                    if ship.progress < ship.speed * 1.5:
                        # Newly created shipment — seed its routes
                        await route_seeder.seed_for_shipment(
                            ship.shipment_id, ship.origin, ship.destination,
                        )

                # Update live stats
                effective_rate = telemetry_sent / max(elapsed, 0.01)
                live.update(
                    _build_stats_table(
                        telemetry_sent,
                        threats_sent,
                        route_seeder.seeded_count,
                        elapsed,
                        effective_rate,
                    )
                )

                await asyncio.sleep(tick_interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Generator interrupted by user[/]")
    finally:
        await producer.stop()
        await redis_client.aclose()
        console.print(
            f"[bold green]Done.[/] Sent {telemetry_sent:,} telemetry, "
            f"{threats_sent:,} threats, seeded {route_seeder.seeded_count:,} routes."
        )


@app.command()
def generate(
    rate: int = typer.Option(
        None, "--rate", "-r",
        help="Target messages per second (default: from config)",
    ),
    shipments: int = typer.Option(
        None, "--shipments", "-s",
        help="Number of concurrent simulated shipments (default: from config)",
    ),
    duration: int = typer.Option(
        0, "--duration", "-d",
        help="Run duration in seconds (0 = run until Ctrl+C)",
    ),
    inject_failures: bool = typer.Option(
        True, "--inject-failures/--no-inject-failures",
        help="Generate threats that intentionally overlap shipments",
    ),
) -> None:
    """Start the mock data generator.

    Simulates shipment movements and threat signals, producing them
    to Redpanda and seeding precomputed routes into Redis.
    """
    settings = get_settings()
    effective_rate = rate or settings.generator_rate_per_sec
    effective_shipments = shipments or settings.generator_num_shipments

    console.print(f"[bold]Starting generator:[/] {effective_shipments} shipments, "
                  f"{effective_rate} msg/s target, "
                  f"{'∞' if duration == 0 else f'{duration}s'} duration, "
                  f"failure injection {'ON' if inject_failures else 'OFF'}")

    asyncio.run(
        _run_generator(effective_shipments, effective_rate, duration, inject_failures)
    )


async def _run_create_topics() -> None:
    """Create Redpanda topics using aiokafka admin."""
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic

    settings = get_settings()

    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap_servers)
    await admin.start()

    topics = [
        NewTopic(
            name=settings.telemetry_topic,
            num_partitions=settings.telemetry_partitions,
            replication_factor=1,
        ),
        NewTopic(
            name=settings.threat_topic,
            num_partitions=settings.threat_partitions,
            replication_factor=1,
        ),
        NewTopic(
            name=settings.anomaly_alerts_topic,
            num_partitions=settings.anomaly_alerts_partitions,
            replication_factor=1,
        ),
        NewTopic(
            name=settings.optimization_requests_topic,
            num_partitions=settings.optimization_requests_partitions,
            replication_factor=1,
        ),
    ]

    try:
        await admin.create_topics(topics)
        for topic in topics:
            console.print(
                f"[green]✓ Created topic:[/] {topic.name} "
                f"({topic.num_partitions} partitions)"
            )
    except Exception as e:
        # TopicAlreadyExistsError is expected on re-runs
        if "TopicAlreadyExists" in str(e) or "TOPIC_ALREADY_EXISTS" in str(e):
            console.print("[yellow]Topics already exist — skipping creation[/]")
        else:
            console.print(f"[red]Failed to create topics:[/] {e}")
            raise
    finally:
        await admin.close()


@app.command()
def topics() -> None:
    """Create Redpanda topics (idempotent — safe to re-run)."""
    console.print("[bold]Creating Redpanda topics...[/]")
    asyncio.run(_run_create_topics())


async def _run_health_check() -> None:
    """Check connectivity to Redpanda and Redis."""
    import redis.asyncio as aioredis
    from aiokafka import AIOKafkaProducer

    settings = get_settings()
    table = Table(title="Infrastructure Health Check")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="bold")

    # Check Redpanda
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
        )
        await producer.start()
        await producer.stop()
        table.add_row("Redpanda (Kafka)", "[green]✓ Connected[/]")
    except Exception as e:
        table.add_row("Redpanda (Kafka)", f"[red]✗ {e}[/]")

    # Check Redis
    try:
        redis_client = aioredis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.aclose()
        table.add_row("Redis", "[green]✓ Connected[/]")
    except Exception as e:
        table.add_row("Redis", f"[red]✗ {e}[/]")

    console.print(table)


@app.command()
def health() -> None:
    """Check Redpanda and Redis connectivity."""
    asyncio.run(_run_health_check())


@app.command()
def serve(
    host: str = typer.Option(None, "--host", "-h", help="Bind host (default: from config)"),
    port: int = typer.Option(None, "--port", "-p", help="Bind port (default: from config)"),
) -> None:
    """Start the FastAPI ingestion API server."""
    import uvicorn

    settings = get_settings()
    effective_host = host or settings.api_host
    effective_port = port or settings.api_port

    console.print(f"[bold]Starting API server at[/] http://{effective_host}:{effective_port}")
    uvicorn.run(
        "services.ingestion.api.app:create_app",
        factory=True,
        host=effective_host,
        port=effective_port,
        log_level="info",
    )


if __name__ == "__main__":
    app()
