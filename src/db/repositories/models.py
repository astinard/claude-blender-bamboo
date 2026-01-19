"""3D Model repository for model-related database operations."""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Model3D
from src.db.repositories.base import BaseRepository


class Model3DRepository(BaseRepository[Model3D]):
    """Repository for Model3D entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Model3D)

    async def get_by_organization(
        self,
        organization_id: str,
        user_id: Optional[str] = None,
        ai_generated_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[Model3D]:
        """Get models in an organization."""
        query = select(Model3D).where(Model3D.organization_id == organization_id)

        if user_id:
            query = query.where(Model3D.user_id == user_id)

        if ai_generated_only:
            query = query.where(Model3D.was_ai_generated == True)

        query = query.order_by(Model3D.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Model3D]:
        """Get models uploaded/created by a user."""
        result = await self.session.execute(
            select(Model3D)
            .where(Model3D.user_id == user_id)
            .order_by(Model3D.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def search(
        self,
        organization_id: str,
        query: str,
        limit: int = 20
    ) -> List[Model3D]:
        """Search models by name or description."""
        search_pattern = f"%{query}%"
        result = await self.session.execute(
            select(Model3D)
            .where(
                Model3D.organization_id == organization_id,
                or_(
                    Model3D.name.ilike(search_pattern),
                    Model3D.description.ilike(search_pattern)
                )
            )
            .order_by(Model3D.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_model(
        self,
        organization_id: str,
        user_id: str,
        name: str,
        file_path: str,
        file_format: str = "stl",
        file_size_bytes: int = 0,
        description: Optional[str] = None,
        was_ai_generated: bool = False,
        generation_prompt: Optional[str] = None,
        generation_provider: Optional[str] = None
    ) -> Model3D:
        """Create a new model entry."""
        model = Model3D(
            organization_id=organization_id,
            user_id=user_id,
            name=name,
            file_path=file_path,
            file_format=file_format,
            file_size_bytes=file_size_bytes,
            description=description,
            was_ai_generated=was_ai_generated,
            generation_prompt=generation_prompt,
            generation_provider=generation_provider
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return model

    async def update_geometry(
        self,
        model_id: str,
        vertices: int,
        faces: int,
        volume_cm3: float,
        bounding_box: List[float],
        is_watertight: bool
    ) -> Optional[Model3D]:
        """Update model geometry metadata after analysis."""
        import json
        return await self.update(
            model_id,
            vertices=vertices,
            faces=faces,
            volume_cm3=volume_cm3,
            bounding_box=json.dumps(bounding_box),
            is_watertight=is_watertight
        )

    async def update_estimates(
        self,
        model_id: str,
        estimated_print_time_minutes: int,
        estimated_material_grams: float
    ) -> Optional[Model3D]:
        """Update print time and material estimates."""
        return await self.update(
            model_id,
            estimated_print_time_minutes=estimated_print_time_minutes,
            estimated_material_grams=estimated_material_grams
        )

    async def set_thumbnail(
        self,
        model_id: str,
        thumbnail_path: str
    ) -> Optional[Model3D]:
        """Set model thumbnail path."""
        return await self.update(model_id, thumbnail_path=thumbnail_path)

    async def create_version(
        self,
        parent_id: str,
        user_id: str,
        file_path: str,
        file_size_bytes: int = 0
    ) -> Optional[Model3D]:
        """Create a new version of an existing model."""
        parent = await self.get_by_id(parent_id)
        if not parent:
            return None

        new_version = Model3D(
            organization_id=parent.organization_id,
            user_id=user_id,
            name=parent.name,
            description=parent.description,
            file_path=file_path,
            file_format=parent.file_format,
            file_size_bytes=file_size_bytes,
            version=parent.version + 1,
            parent_id=parent_id,
            was_ai_generated=parent.was_ai_generated,
            generation_prompt=parent.generation_prompt
        )
        self.session.add(new_version)
        await self.session.flush()
        await self.session.refresh(new_version)
        return new_version

    async def get_versions(self, model_id: str) -> List[Model3D]:
        """Get all versions of a model (including original)."""
        # Get the root model first
        model = await self.get_by_id(model_id)
        if not model:
            return []

        # Find the root
        root_id = model_id
        while model.parent_id:
            root_id = model.parent_id
            model = await self.get_by_id(root_id)

        # Get all versions
        result = await self.session.execute(
            select(Model3D)
            .where(
                or_(
                    Model3D.id == root_id,
                    Model3D.parent_id == root_id
                )
            )
            .order_by(Model3D.version)
        )
        return list(result.scalars().all())

    async def get_storage_usage(self, organization_id: str) -> dict:
        """Get storage usage for an organization."""
        result = await self.session.execute(
            select(
                func.count(Model3D.id),
                func.sum(Model3D.file_size_bytes)
            ).where(Model3D.organization_id == organization_id)
        )
        row = result.one()

        return {
            "model_count": row[0] or 0,
            "total_bytes": row[1] or 0,
            "total_mb": round((row[1] or 0) / (1024 * 1024), 2),
            "total_gb": round((row[1] or 0) / (1024 * 1024 * 1024), 3)
        }

    async def get_ai_generation_count(
        self,
        organization_id: str,
        since: Optional[datetime] = None
    ) -> int:
        """Count AI-generated models (for quota tracking)."""
        if not since:
            since = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)

        result = await self.session.execute(
            select(func.count(Model3D.id)).where(
                Model3D.organization_id == organization_id,
                Model3D.was_ai_generated == True,
                Model3D.created_at >= since
            )
        )
        return result.scalar() or 0
