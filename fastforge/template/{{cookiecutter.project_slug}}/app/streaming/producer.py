"""Event producer — {{ cookiecutter.streaming }}."""
{%- if cookiecutter.logging == "structlog" %}

from app.logging_config import get_logger

logger = get_logger(__name__)
{%- else %}

from logging import getLogger

logger = getLogger(__name__)
{%- endif %}
{%- if cookiecutter.streaming == "kafka" %}

import json

from aiokafka import AIOKafkaProducer

from app.config import settings

_producer: AIOKafkaProducer | None = None


async def init_producer() -> None:
    """Connect to Kafka and start the producer."""
    global _producer  # noqa: PLW0603
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode(),
        key_serializer=lambda k: k.encode() if k else None,
    )
    await _producer.start()
    logger.info("kafka_producer_started", servers=settings.kafka_bootstrap_servers)


async def send_event(topic: str, value: dict, key: str | None = None) -> None:
    """Send an event to a Kafka topic."""
    if _producer is None:
        raise RuntimeError("Producer not initialized — call init_producer() first")
    await _producer.send(topic, value=value, key=key)


async def close_producer() -> None:
    """Stop the Kafka producer."""
    global _producer  # noqa: PLW0603
    if _producer is not None:
        await _producer.stop()
        _producer = None
{%- elif cookiecutter.streaming == "rabbitmq" %}

import json

import aio_pika

from app.config import settings

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None


async def init_producer() -> None:
    """Connect to RabbitMQ."""
    global _connection, _channel  # noqa: PLW0603
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    _channel = await _connection.channel()
    logger.info("rabbitmq_producer_started", url=settings.rabbitmq_url)


async def send_event(topic: str, value: dict, key: str | None = None) -> None:
    """Publish a message to a RabbitMQ exchange."""
    if _channel is None:
        raise RuntimeError("Producer not initialized — call init_producer() first")
    exchange = await _channel.declare_exchange(topic, aio_pika.ExchangeType.TOPIC, durable=True)
    await exchange.publish(
        aio_pika.Message(body=json.dumps(value).encode(), content_type="application/json"),
        routing_key=key or "",
    )


async def close_producer() -> None:
    """Close the RabbitMQ connection."""
    global _connection, _channel  # noqa: PLW0603
    if _channel is not None:
        await _channel.close()
        _channel = None
    if _connection is not None:
        await _connection.close()
        _connection = None
{%- elif cookiecutter.streaming == "redis_pubsub" %}

import json

import redis.asyncio as redis

from app.config import settings

_client: redis.Redis | None = None


async def init_producer() -> None:
    """Connect to Redis for Pub/Sub publishing."""
    global _client  # noqa: PLW0603
    _client = redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("redis_pubsub_producer_started", url=settings.redis_url)


async def send_event(topic: str, value: dict, key: str | None = None) -> None:
    """Publish a message to a Redis channel."""
    if _client is None:
        raise RuntimeError("Producer not initialized — call init_producer() first")
    await _client.publish(topic, json.dumps(value))


async def close_producer() -> None:
    """Close the Redis connection."""
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.aclose()
        _client = None
{%- elif cookiecutter.streaming == "nats" %}

import json

import nats as nats_client

from app.config import settings

_nc: nats_client.NATS | None = None


async def init_producer() -> None:
    """Connect to NATS."""
    global _nc  # noqa: PLW0603
    _nc = await nats_client.connect(settings.nats_url)
    logger.info("nats_producer_started", url=settings.nats_url)


async def send_event(topic: str, value: dict, key: str | None = None) -> None:
    """Publish a message to a NATS subject."""
    if _nc is None:
        raise RuntimeError("Producer not initialized — call init_producer() first")
    await _nc.publish(topic, json.dumps(value).encode())


async def close_producer() -> None:
    """Drain and close the NATS connection."""
    global _nc  # noqa: PLW0603
    if _nc is not None:
        await _nc.drain()
        _nc = None
{%- endif %}
