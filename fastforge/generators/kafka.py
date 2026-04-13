"""Add Kafka streaming support to an existing FastForge project.

Creates:
  - app/streaming/__init__.py, producer.py, consumer.py, handler.py
  - infra/docker-compose.kafka.yml
  - infra/kafka/  (config placeholder)
Modifies:
  - app/config.py, app/main.py, .env.staging, pyproject.toml, .fastforge.json
"""

import os
import re
import subprocess

from fastforge.project_config import load_config, save_config

# ═══════════════════════════════════════════════════════════════════════════════
# App code templates
# ═══════════════════════════════════════════════════════════════════════════════

STREAMING_INIT = '"""Streaming package — Kafka producer and consumer."""\n'

PRODUCER_PY = '''\
"""Kafka event producer."""

from aiokafka import AIOKafkaProducer

from app.config import settings

_producer: AIOKafkaProducer | None = None


async def get_producer() -> AIOKafkaProducer:
    """Return the singleton Kafka producer, creating it if needed."""
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
        )
        await _producer.start()
    return _producer


async def send_event(topic: str, key: str, value: bytes) -> None:
    """Send an event to a Kafka topic."""
    producer = await get_producer()
    await producer.send_and_wait(topic, value=value, key=key.encode())


async def close_producer() -> None:
    """Gracefully close the Kafka producer."""
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
'''

CONSUMER_PY = '''\
"""Kafka event consumer — runs as a background task during app lifespan."""

import asyncio
import logging

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.streaming.handler import handle_message

logger = logging.getLogger(__name__)

_consumer_task: asyncio.Task | None = None


async def start_consumer() -> None:
    """Start the Kafka consumer as a background task."""
    global _consumer_task
    _consumer_task = asyncio.create_task(_consume())


async def stop_consumer() -> None:
    """Stop the Kafka consumer background task."""
    global _consumer_task
    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        _consumer_task = None


async def _consume() -> None:
    """Main consumer loop — subscribe and dispatch messages."""
    consumer = AIOKafkaConsumer(
        settings.kafka_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_id,
        auto_offset_reset="earliest",
    )

    try:
        await consumer.start()
        logger.info("Kafka consumer started", extra={"topic": settings.kafka_topic})

        async for msg in consumer:
            try:
                await handle_message(msg.topic, msg.key, msg.value)
            except Exception:
                logger.exception("Error handling Kafka message", extra={
                    "topic": msg.topic,
                    "partition": msg.partition,
                    "offset": msg.offset,
                })
    except asyncio.CancelledError:
        logger.info("Kafka consumer stopping")
    finally:
        await consumer.stop()
'''

HANDLER_PY = '''\
"""Message handler — process incoming Kafka messages.

Extend this module with your business logic.
"""

import logging

logger = logging.getLogger(__name__)


async def handle_message(topic: str, key: bytes | None, value: bytes) -> None:
    """Handle an incoming Kafka message.

    Args:
        topic: The Kafka topic the message was received from.
        key: Optional message key.
        value: Message payload (bytes).
    """
    logger.info(
        "Received message",
        extra={"topic": topic, "key": key.decode() if key else None, "size": len(value)},
    )
    # TODO: Add your message processing logic here
'''

KAFKA_DEPS = [
    '"aiokafka>=0.11.0"',
]

# ═══════════════════════════════════════════════════════════════════════════════
# Infrastructure templates
# ═══════════════════════════════════════════════════════════════════════════════

COMPOSE_KAFKA = """\
# Kafka (KRaft mode — no ZooKeeper)
# Usage: docker compose -f infra/docker-compose.yml -f infra/docker-compose.kafka.yml up -d

services:
  kafka:
    image: confluentinc/cp-kafka:7.7.0
    container_name: {slug}-kafka
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      CLUSTER_ID: {slug}-kafka-cluster
    ports:
      - "9092:9092"
    healthcheck:
      test: ["CMD-SHELL", "kafka-broker-api-versions --bootstrap-server localhost:9092"]
      interval: 30s
      timeout: 10s
      retries: 5
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Generator
# ═══════════════════════════════════════════════════════════════════════════════


def add_kafka(project_dir: str) -> dict:
    """Add Kafka streaming support. Returns summary of changes."""
    config = load_config(project_dir)

    if config.get("streaming") == "kafka":
        return {"status": "already_configured", "created": [], "modified": []}

    slug = config.get("project_slug", "app")
    package = config.get("package_name", slug.replace("-", "_"))

    created: list[str] = []
    modified: list[str] = []

    # 1. Create app/streaming/ package
    streaming_dir = os.path.join(project_dir, "app", "streaming")
    os.makedirs(streaming_dir, exist_ok=True)

    for filename, content in [
        ("__init__.py", STREAMING_INIT),
        ("producer.py", PRODUCER_PY),
        ("consumer.py", CONSUMER_PY),
        ("handler.py", HANDLER_PY),
    ]:
        path = os.path.join(streaming_dir, filename)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(content)
            created.append(f"app/streaming/{filename}")

    # 2. Add Kafka settings to config.py
    config_path = os.path.join(project_dir, "app", "config.py")
    if os.path.isfile(config_path):
        with open(config_path) as f:
            content = f.read()

        if "kafka_bootstrap_servers" not in content:
            kafka_block = (
                "\n    # Kafka\n"
                '    kafka_bootstrap_servers: str = "localhost:9092"\n'
                f'    kafka_topic: str = "{package}-events"\n'
                f'    kafka_group_id: str = "{package}-group"\n\n'
            )
            for anchor in ["    model_config", "    @property"]:
                if anchor in content:
                    content = content.replace(anchor, kafka_block + anchor, 1)
                    break

            with open(config_path, "w") as f:
                f.write(content)
            modified.append("app/config.py")

    # 3. Add lifespan hooks to main.py
    main_path = os.path.join(project_dir, "app", "main.py")
    if os.path.isfile(main_path):
        with open(main_path) as f:
            main_content = f.read()

        changed = False

        # Add imports
        imports_to_add = []
        if "from app.streaming.consumer import start_consumer" not in main_content:
            imports_to_add.append("from app.streaming.consumer import start_consumer, stop_consumer")
        if "from app.streaming.producer import close_producer" not in main_content:
            imports_to_add.append("from app.streaming.producer import close_producer")

        if imports_to_add:
            lines = main_content.split("\n")
            last_app_import = -1
            for i, line in enumerate(lines):
                if line.startswith("from app."):
                    last_app_import = i
            if last_app_import >= 0:
                for offset, imp in enumerate(imports_to_add):
                    lines.insert(last_app_import + 1 + offset, imp)
                main_content = "\n".join(lines)
                changed = True

        # Add startup/shutdown in lifespan or after app creation
        if "start_consumer" not in main_content or "await start_consumer()" not in main_content:
            if "async def lifespan" in main_content:
                # Add to existing lifespan
                if "yield" in main_content:
                    main_content = main_content.replace(
                        "    yield",
                        "    await start_consumer()\n    yield\n    await stop_consumer()\n    await close_producer()",
                        1,
                    )
                    changed = True
            else:
                # Add startup event handler
                lines = main_content.split("\n")
                last_include = -1
                for i, line in enumerate(lines):
                    if "include_router" in line:
                        last_include = i
                if last_include >= 0:
                    indent = "    " if lines[last_include].startswith("    ") else ""
                    insertions = [
                        "",
                        f"{indent}# Kafka consumer lifecycle",
                        f"{indent}@app.on_event('startup')",
                        f"{indent}async def startup_kafka():",
                        f"{indent}    await start_consumer()",
                        "",
                        f"{indent}@app.on_event('shutdown')",
                        f"{indent}async def shutdown_kafka():",
                        f"{indent}    await stop_consumer()",
                        f"{indent}    await close_producer()",
                    ]
                    for idx, line in enumerate(insertions):
                        lines.insert(last_include + 1 + idx, line)
                    main_content = "\n".join(lines)
                    changed = True

        if changed:
            with open(main_path, "w") as f:
                f.write(main_content)
            modified.append("app/main.py")

    # 4. Add to .env.staging
    env_path = os.path.join(project_dir, ".env.staging")
    if os.path.isfile(env_path):
        with open(env_path) as f:
            env_content = f.read()

        if "KAFKA_BOOTSTRAP_SERVERS" not in env_content:
            with open(env_path, "a") as f:
                f.write(
                    "\n# Kafka\n"
                    "KAFKA_BOOTSTRAP_SERVERS=localhost:9092\n"
                    f"KAFKA_TOPIC={package}-events\n"
                    f"KAFKA_GROUP_ID={package}-group\n"
                )
            modified.append(".env.staging")

    # 5. Add dependencies to pyproject.toml
    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        with open(pyproject_path) as f:
            pyproject_content = f.read()

        new_deps = [d for d in KAFKA_DEPS if d.split('"')[1].split('>')[0] not in pyproject_content.lower()]

        if new_deps:
            match = re.search(r"(dependencies\s*=\s*\[)(.*?)(^\])", pyproject_content, re.DOTALL | re.MULTILINE)
            if match:
                existing = match.group(2).rstrip()
                if existing and not existing.rstrip().endswith(","):
                    existing = existing.rstrip() + ","
                new_section = existing + "\n" + "\n".join(f"    {d}," for d in new_deps) + "\n"
                pyproject_content = (
                    pyproject_content[: match.start(2)]
                    + new_section
                    + pyproject_content[match.start(3) :]
                )
                with open(pyproject_path, "w") as f:
                    f.write(pyproject_content)
                modified.append("pyproject.toml")

    # 6. Generate infra/docker-compose.kafka.yml
    infra_dir = os.path.join(project_dir, "infra")
    os.makedirs(infra_dir, exist_ok=True)

    compose_path = os.path.join(infra_dir, "docker-compose.kafka.yml")
    if not os.path.exists(compose_path):
        with open(compose_path, "w") as f:
            f.write(COMPOSE_KAFKA.format(slug=slug))
        created.append("infra/docker-compose.kafka.yml")

    # 7. Run ruff
    subprocess.run(["ruff", "check", "--fix", "--silent", "."], cwd=project_dir, capture_output=True)
    subprocess.run(["ruff", "format", "--silent", "."], cwd=project_dir, capture_output=True)

    # 8. Update .fastforge.json
    config["streaming"] = "kafka"
    save_config(config, project_dir)
    modified.append(".fastforge.json")

    return {"status": "added", "created": created, "modified": modified}
