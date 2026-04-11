"""Event consumer — {{ cookiecutter.streaming }} listener with background task."""

import asyncio
import json
{%- if cookiecutter.logging == "structlog" %}

from app.logging_config import get_logger

logger = get_logger(__name__)
{%- else %}

from logging import getLogger

logger = getLogger(__name__)
{%- endif %}

from app.streaming.handler import handle_event
{%- if cookiecutter.streaming == "kafka" %}

from aiokafka import AIOKafkaConsumer

from app.config import settings

_consumer: AIOKafkaConsumer | None = None
_task: asyncio.Task | None = None


async def _consume_loop() -> None:
    """Internal loop — reads messages and dispatches to handler."""
    try:
        async for msg in _consumer:
            value = json.loads(msg.value) if msg.value else {}
            key = msg.key.decode() if msg.key else None
            await handle_event(msg.topic, key, value)
    except asyncio.CancelledError:
        pass


async def start_consumer(topics: list[str]) -> None:
    """Start consuming from Kafka topics in a background task."""
    global _consumer, _task  # noqa: PLW0603
    _consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_id,
        auto_offset_reset="latest",
    )
    await _consumer.start()
    _task = asyncio.create_task(_consume_loop())
    logger.info("kafka_consumer_started", topics=topics)


async def stop_consumer() -> None:
    """Stop the Kafka consumer."""
    global _consumer, _task  # noqa: PLW0603
    if _task is not None:
        _task.cancel()
        await asyncio.gather(_task, return_exceptions=True)
        _task = None
    if _consumer is not None:
        await _consumer.stop()
        _consumer = None
{%- elif cookiecutter.streaming == "rabbitmq" %}

import aio_pika

from app.config import settings

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None


async def start_consumer(topics: list[str]) -> None:
    """Start consuming from RabbitMQ exchanges."""
    global _connection, _channel  # noqa: PLW0603
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    _channel = await _connection.channel()
    await _channel.set_qos(prefetch_count=10)

    for topic in topics:
        exchange = await _channel.declare_exchange(topic, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await _channel.declare_queue(f"{{ cookiecutter.project_slug }}-{topic}", durable=True)
        await queue.bind(exchange, routing_key="#")

        async def _on_message(message: aio_pika.abc.AbstractIncomingMessage, _topic: str = topic) -> None:
            async with message.process():
                value = json.loads(message.body) if message.body else {}
                await handle_event(_topic, message.routing_key, value)

        await queue.consume(_on_message)

    logger.info("rabbitmq_consumer_started", topics=topics)


async def stop_consumer() -> None:
    """Stop the RabbitMQ consumer."""
    global _connection, _channel  # noqa: PLW0603
    if _channel is not None:
        await _channel.close()
        _channel = None
    if _connection is not None:
        await _connection.close()
        _connection = None
{%- elif cookiecutter.streaming == "redis_pubsub" %}

import redis.asyncio as redis

from app.config import settings

_client: redis.Redis | None = None
_pubsub: redis.client.PubSub | None = None
_task: asyncio.Task | None = None


async def _consume_loop() -> None:
    """Internal loop — reads Redis Pub/Sub messages."""
    try:
        while True:
            msg = await _pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] == "message":
                value = json.loads(msg["data"]) if msg["data"] else {}
                await handle_event(msg["channel"], None, value)
            await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        pass


async def start_consumer(topics: list[str]) -> None:
    """Subscribe to Redis channels."""
    global _client, _pubsub, _task  # noqa: PLW0603
    _client = redis.from_url(settings.redis_url, decode_responses=True)
    _pubsub = _client.pubsub()
    await _pubsub.subscribe(*topics)
    _task = asyncio.create_task(_consume_loop())
    logger.info("redis_consumer_started", topics=topics)


async def stop_consumer() -> None:
    """Unsubscribe and close Redis Pub/Sub."""
    global _client, _pubsub, _task  # noqa: PLW0603
    if _task is not None:
        _task.cancel()
        await asyncio.gather(_task, return_exceptions=True)
        _task = None
    if _pubsub is not None:
        await _pubsub.unsubscribe()
        await _pubsub.aclose()
        _pubsub = None
    if _client is not None:
        await _client.aclose()
        _client = None
{%- elif cookiecutter.streaming == "nats" %}

import nats as nats_client

from app.config import settings

_nc: nats_client.NATS | None = None
_subs: list = []


async def start_consumer(topics: list[str]) -> None:
    """Subscribe to NATS subjects."""
    global _nc  # noqa: PLW0603
    _nc = await nats_client.connect(settings.nats_url)

    async def _on_message(msg) -> None:
        value = json.loads(msg.data) if msg.data else {}
        await handle_event(msg.subject, None, value)

    for topic in topics:
        sub = await _nc.subscribe(topic, cb=_on_message)
        _subs.append(sub)

    logger.info("nats_consumer_started", topics=topics)


async def stop_consumer() -> None:
    """Unsubscribe and close NATS connection."""
    global _nc  # noqa: PLW0603
    for sub in _subs:
        await sub.unsubscribe()
    _subs.clear()
    if _nc is not None:
        await _nc.drain()
        _nc = None
{%- endif %}
