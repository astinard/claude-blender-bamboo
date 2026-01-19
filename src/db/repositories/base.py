"""Base repository with common CRUD operations."""

from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base repository providing common CRUD operations."""

    def __init__(self, session: AsyncSession, model: Type[T]):
        self.session = session
        self.model = model

    async def create(self, **kwargs) -> T:
        """Create a new entity."""
        entity = self.model(**kwargs)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def get_by_id(self, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters
    ) -> List[T]:
        """Get all entities with optional filtering."""
        query = select(self.model)

        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, entity_id: str, **kwargs) -> Optional[T]:
        """Update an entity."""
        await self.session.execute(
            update(self.model)
            .where(self.model.id == entity_id)
            .values(**kwargs)
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: str) -> bool:
        """Delete an entity."""
        result = await self.session.execute(
            delete(self.model).where(self.model.id == entity_id)
        )
        return result.rowcount > 0

    async def count(self, **filters) -> int:
        """Count entities with optional filtering."""
        query = select(func.count(self.model.id))

        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def exists(self, entity_id: str) -> bool:
        """Check if entity exists."""
        result = await self.session.execute(
            select(func.count(self.model.id)).where(self.model.id == entity_id)
        )
        return (result.scalar() or 0) > 0
