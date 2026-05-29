"""Repository interface and implementations for {{cookiecutter.model_name_class}} — Data access layer (SOLID: Single Responsibility)."""

import uuid
from abc import ABC, abstractmethod

from app.api.models.{{cookiecutter.model_name}} import (
    {{cookiecutter.model_name_class}}Create,
    {{cookiecutter.model_name_class}}Response,
    {{cookiecutter.model_name_class}}Update,
)


class {{cookiecutter.model_name_class}}Repository(ABC):
    """Abstract repository — swap implementations without changing service layer (SOLID: DIP)."""

    @abstractmethod
    async def create(self, data: {{cookiecutter.model_name_class}}Create) -> {{cookiecutter.model_name_class}}Response: ...

    @abstractmethod
    async def get_by_id(self, item_id: str) -> {{cookiecutter.model_name_class}}Response | None: ...

    @abstractmethod
    async def list(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[{{cookiecutter.model_name_class}}Response], int]:
        """Return ``(page_items, total_count)``."""
        ...

    @abstractmethod
    async def update(self, item_id: str, data: {{cookiecutter.model_name_class}}Update) -> {{cookiecutter.model_name_class}}Response | None: ...

    @abstractmethod
    async def delete(self, item_id: str) -> bool: ...


class InMemory{{cookiecutter.model_name_class}}Repository({{cookiecutter.model_name_class}}Repository):
    """In-memory implementation — used for development and testing."""

    def __init__(self) -> None:
        self._store: dict[str, {{cookiecutter.model_name_class}}Response] = {}

    async def create(self, data: {{cookiecutter.model_name_class}}Create) -> {{cookiecutter.model_name_class}}Response:
        item_id = str(uuid.uuid4())
        item = {{cookiecutter.model_name_class}}Response(id=item_id, **data.model_dump())
        self._store[item_id] = item
        return item

    async def get_by_id(self, item_id: str) -> {{cookiecutter.model_name_class}}Response | None:
        return self._store.get(item_id)

    async def list(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[{{cookiecutter.model_name_class}}Response], int]:
        items = list(self._store.values())
        return items[offset : offset + limit], len(items)

    async def update(self, item_id: str, data: {{cookiecutter.model_name_class}}Update) -> {{cookiecutter.model_name_class}}Response | None:
        existing = self._store.get(item_id)
        if not existing:
            return None
        updated = existing.model_copy(update={k: v for k, v in data.model_dump().items() if v is not None})
        self._store[item_id] = updated
        return updated

    async def delete(self, item_id: str) -> bool:
        return self._store.pop(item_id, None) is not None
{%- if cookiecutter.database in ("postgres", "mysql", "sqlite") %}


class SQLAlchemy{{cookiecutter.model_name_class}}Repository({{cookiecutter.model_name_class}}Repository):
    """SQLAlchemy implementation — PostgreSQL, MySQL, SQLite."""

    def __init__(self, session) -> None:
        self._session = session

    async def create(self, data: {{cookiecutter.model_name_class}}Create) -> {{cookiecutter.model_name_class}}Response:
        from app.db.models.{{cookiecutter.model_name}} import {{cookiecutter.model_name_class}}Model

        obj = {{cookiecutter.model_name_class}}Model(**data.model_dump())
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return {{cookiecutter.model_name_class}}Response(id=str(obj.id), **data.model_dump())

    async def get_by_id(self, item_id: str) -> {{cookiecutter.model_name_class}}Response | None:
        from sqlalchemy import select

        from app.db.models.{{cookiecutter.model_name}} import {{cookiecutter.model_name_class}}Model

        result = await self._session.execute(select({{cookiecutter.model_name_class}}Model).where({{cookiecutter.model_name_class}}Model.id == item_id))
        obj = result.scalar_one_or_none()
        if not obj:
            return None
        return {{cookiecutter.model_name_class}}Response(id=str(obj.id), name=obj.name, description=obj.description)

    async def list(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[{{cookiecutter.model_name_class}}Response], int]:
        from sqlalchemy import func, select

        from app.db.models.{{cookiecutter.model_name}} import {{cookiecutter.model_name_class}}Model

        total_result = await self._session.execute(
            select(func.count()).select_from({{cookiecutter.model_name_class}}Model)
        )
        total = int(total_result.scalar_one())

        page_stmt = (
            select({{cookiecutter.model_name_class}}Model)
            .order_by({{cookiecutter.model_name_class}}Model.id)
            .limit(limit)
            .offset(offset)
        )
        page_result = await self._session.execute(page_stmt)
        items = [
            {{cookiecutter.model_name_class}}Response(id=str(obj.id), name=obj.name, description=obj.description)
            for obj in page_result.scalars()
        ]
        return items, total

    async def update(self, item_id: str, data: {{cookiecutter.model_name_class}}Update) -> {{cookiecutter.model_name_class}}Response | None:
        from sqlalchemy import select

        from app.db.models.{{cookiecutter.model_name}} import {{cookiecutter.model_name_class}}Model

        result = await self._session.execute(select({{cookiecutter.model_name_class}}Model).where({{cookiecutter.model_name_class}}Model.id == item_id))
        obj = result.scalar_one_or_none()
        if not obj:
            return None
        for key, value in data.model_dump(exclude_none=True).items():
            setattr(obj, key, value)
        await self._session.commit()
        await self._session.refresh(obj)
        return {{cookiecutter.model_name_class}}Response(id=str(obj.id), name=obj.name, description=obj.description)

    async def delete(self, item_id: str) -> bool:
        from sqlalchemy import select

        from app.db.models.{{cookiecutter.model_name}} import {{cookiecutter.model_name_class}}Model

        result = await self._session.execute(select({{cookiecutter.model_name_class}}Model).where({{cookiecutter.model_name_class}}Model.id == item_id))
        obj = result.scalar_one_or_none()
        if not obj:
            return False
        await self._session.delete(obj)
        await self._session.commit()
        return True
{%- endif %}
{%- if cookiecutter.database == "mongodb" %}


class Mongo{{cookiecutter.model_name_class}}Repository({{cookiecutter.model_name_class}}Repository):
    """MongoDB implementation using Motor async."""

    def __init__(self, collection) -> None:
        self._collection = collection

    async def create(self, data: {{cookiecutter.model_name_class}}Create) -> {{cookiecutter.model_name_class}}Response:
        item_id = str(uuid.uuid4())
        doc = {"_id": item_id, **data.model_dump()}
        await self._collection.insert_one(doc)
        return {{cookiecutter.model_name_class}}Response(id=item_id, **data.model_dump())

    async def get_by_id(self, item_id: str) -> {{cookiecutter.model_name_class}}Response | None:
        doc = await self._collection.find_one({"_id": item_id})
        if not doc:
            return None
        return {{cookiecutter.model_name_class}}Response(id=doc["_id"], name=doc["name"], description=doc.get("description"))

    async def list(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[{{cookiecutter.model_name_class}}Response], int]:
        total = await self._collection.count_documents({})
        cursor = self._collection.find().sort("_id", 1).skip(offset).limit(limit)
        items: list[{{cookiecutter.model_name_class}}Response] = []
        async for doc in cursor:
            items.append(
                {{cookiecutter.model_name_class}}Response(
                    id=doc["_id"], name=doc["name"], description=doc.get("description")
                )
            )
        return items, total

    async def update(self, item_id: str, data: {{cookiecutter.model_name_class}}Update) -> {{cookiecutter.model_name_class}}Response | None:
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        if not updates:
            return await self.get_by_id(item_id)
        result = await self._collection.update_one({"_id": item_id}, {"$set": updates})
        if result.matched_count == 0:
            return None
        return await self.get_by_id(item_id)

    async def delete(self, item_id: str) -> bool:
        result = await self._collection.delete_one({"_id": item_id})
        return result.deleted_count > 0
{%- endif %}
