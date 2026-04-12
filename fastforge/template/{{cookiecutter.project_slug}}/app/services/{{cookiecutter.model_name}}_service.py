"""Service layer for {{cookiecutter.model_name_class}} — Business logic (SOLID: Single Responsibility)."""

from app.api.models.{{cookiecutter.model_name}} import (
    {{cookiecutter.model_name_class}}Create,
    {{cookiecutter.model_name_class}}ListResponse,
    {{cookiecutter.model_name_class}}Response,
    {{cookiecutter.model_name_class}}Update,
)
{%- if cookiecutter.logging == "structlog" %}
from app.logging_config import get_logger
{%- else %}
from logging import getLogger
{%- endif %}
from app.repositories.{{cookiecutter.model_name}}_repository import {{cookiecutter.model_name_class}}Repository
{% if cookiecutter.logging == "structlog" %}
logger = get_logger(__name__)
{%- else %}
logger = getLogger(__name__)
{%- endif %}


class {{cookiecutter.model_name_class}}Service:
    """Encapsulates business logic — depends on repository interface, not implementation (SOLID: DIP)."""

    def __init__(self, repository: {{cookiecutter.model_name_class}}Repository) -> None:
        self._repo = repository

    async def create(self, data: {{cookiecutter.model_name_class}}Create) -> {{cookiecutter.model_name_class}}Response:
        result = await self._repo.create(data)
{%- if cookiecutter.logging == "structlog" %}
        await logger.ainfo("{{cookiecutter.model_name}}_created", id=result.id, name=data.name)
{%- else %}
        logger.info("{{cookiecutter.model_name}}_created: %s", result.id)
{%- endif %}
        return result

    async def get_by_id(self, item_id: str) -> {{cookiecutter.model_name_class}}Response | None:
        return await self._repo.get_by_id(item_id)

    async def list_all(self) -> {{cookiecutter.model_name_class}}ListResponse:
        items = await self._repo.list_all()
        return {{cookiecutter.model_name_class}}ListResponse({{cookiecutter.model_name_plural}}=items, total=len(items))

    async def update(self, item_id: str, data: {{cookiecutter.model_name_class}}Update) -> {{cookiecutter.model_name_class}}Response | None:
        result = await self._repo.update(item_id, data)
{%- if cookiecutter.logging == "structlog" %}
        if result:
            await logger.ainfo("{{cookiecutter.model_name}}_updated", id=item_id)
{%- else %}
        if result:
            logger.info("{{cookiecutter.model_name}}_updated: %s", item_id)
{%- endif %}
        return result

    async def delete(self, item_id: str) -> bool:
        deleted = await self._repo.delete(item_id)
{%- if cookiecutter.logging == "structlog" %}
        if deleted:
            await logger.ainfo("{{cookiecutter.model_name}}_deleted", id=item_id)
{%- else %}
        if deleted:
            logger.info("{{cookiecutter.model_name}}_deleted: %s", item_id)
{%- endif %}
        return deleted
