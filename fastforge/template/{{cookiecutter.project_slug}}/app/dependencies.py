"""FastAPI dependency injection — wires repository → service (SOLID: Dependency Inversion)."""

from app.repositories.{{ cookiecutter.model_name }}_repository import (
    InMemory{{ cookiecutter.model_name_class }}Repository,
{%- if cookiecutter.database in ("postgres", "mysql", "sqlite") %}
    SQLAlchemy{{ cookiecutter.model_name_class }}Repository,
{%- endif %}
{%- if cookiecutter.database == "mongodb" %}
    Mongo{{ cookiecutter.model_name_class }}Repository,
{%- endif %}
)
from app.services.{{ cookiecutter.model_name }}_service import {{ cookiecutter.model_name_class }}Service
{%- if cookiecutter.database in ("postgres", "mysql", "sqlite") %}
from fastapi import Depends
from app.db.sqlalchemy import get_session
{%- endif %}
{%- if cookiecutter.database == "mongodb" %}
from app.db.mongodb import get_collection
{%- endif %}

{% if cookiecutter.database == "none" -%}
# Singleton in-memory repo — shared across requests
_repo = InMemory{{ cookiecutter.model_name_class }}Repository()


def get_{{ cookiecutter.model_name }}_service() -> {{ cookiecutter.model_name_class }}Service:
    """Provide {{ cookiecutter.model_name_class }}Service with in-memory repository."""
    return {{ cookiecutter.model_name_class }}Service(_repo)
{%- elif cookiecutter.database in ("postgres", "mysql", "sqlite") %}


async def get_{{ cookiecutter.model_name }}_service(session=Depends(get_session)) -> {{ cookiecutter.model_name_class }}Service:
    """Provide {{ cookiecutter.model_name_class }}Service with SQLAlchemy repository."""
    repo = SQLAlchemy{{ cookiecutter.model_name_class }}Repository(session)
    return {{ cookiecutter.model_name_class }}Service(repo)
{%- elif cookiecutter.database == "mongodb" %}


def get_{{ cookiecutter.model_name }}_service() -> {{ cookiecutter.model_name_class }}Service:
    """Provide {{ cookiecutter.model_name_class }}Service with MongoDB repository."""
    collection = get_collection("{{ cookiecutter.model_name_plural }}")
    repo = Mongo{{ cookiecutter.model_name_class }}Repository(collection)
    return {{ cookiecutter.model_name_class }}Service(repo)
{%- endif %}
