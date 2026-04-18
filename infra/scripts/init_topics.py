"""Redpanda topic initialization script.

Creates the required topics with configured partition counts.
Idempotent — safe to run multiple times.

Usage:
    python -m infra.scripts.init_topics

Or via the CLI:
    python -m services.ingestion topics
"""

from __future__ import annotations

import asyncio
import sys

from rich.console import Console

console = Console()


async def create_topics() -> None:
    """Create Redpanda topics using aiokafka admin client."""
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic

    from services.ingestion.config import get_settings

    settings = get_settings()

    console.print(f"[bold]Connecting to Redpanda at {settings.kafka_bootstrap_servers}...[/]")

    admin = AIOKafkaAdminClient(
        bootstrap_servers=settings.kafka_bootstrap_servers,
    )
    await admin.start()

    topics_to_create = [
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
    ]

    try:
        await admin.create_topics(topics_to_create)
        for topic in topics_to_create:
            console.print(
                f"[green]✓[/] Created topic: [cyan]{topic.name}[/] "
                f"({topic.num_partitions} partitions)"
            )
    except Exception as e:
        if "TopicAlreadyExists" in str(e) or "TOPIC_ALREADY_EXISTS" in str(e):
            console.print("[yellow]Topics already exist — no changes made[/]")
        else:
            console.print(f"[red]✗ Error creating topics:[/] {e}")
            await admin.close()
            sys.exit(1)

    await admin.close()
    console.print("[bold green]Topic initialization complete.[/]")


if __name__ == "__main__":
    asyncio.run(create_topics())
