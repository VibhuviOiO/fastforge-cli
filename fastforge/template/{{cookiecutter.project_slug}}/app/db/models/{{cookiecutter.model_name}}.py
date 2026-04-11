{%- if cookiecutter.database in ("postgres", "mysql", "sqlite") -%}
"""SQLAlchemy model for {{cookiecutter.model_name_class}}."""

import uuid

from sqlalchemy import String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class {{cookiecutter.model_name_class}}Model(Base):
    __tablename__ = "{{cookiecutter.model_name_plural}}"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
{%- endif -%}
{%- if cookiecutter.database == "mongodb" -%}
"""MongoDB document schema reference for {{cookiecutter.model_name_class}}.

MongoDB is schema-less. This file documents the expected shape
for the '{{cookiecutter.model_name_plural}}' collection.

Document shape:
{
    "_id": str (UUID),
    "name": str,
    "description": str | null,
}
"""
{%- endif -%}
