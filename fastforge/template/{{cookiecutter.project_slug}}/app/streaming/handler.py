"""Event handler — customize this to process incoming events."""
{%- if cookiecutter.logging == "structlog" %}

from app.logging_config import get_logger

logger = get_logger(__name__)
{%- else %}

from logging import getLogger

logger = getLogger(__name__)
{%- endif %}


async def handle_event(topic: str, key: str | None, value: dict) -> None:
    """Process an incoming event.

    This is the entry point for all consumed messages.
    Add your business logic here — call services, write to DB, make API calls, etc.

    Args:
        topic: The topic/channel/subject the event came from.
        key: Optional message key (Kafka/RabbitMQ routing key).
        value: The decoded message payload.
    """
    logger.info("event_received", topic=topic, key=key, payload_keys=list(value.keys()))

    # TODO: Add your event processing logic here
    # Example:
    #   if topic == "{{ cookiecutter.project_slug }}-events":
    #       await some_service.process(value)
