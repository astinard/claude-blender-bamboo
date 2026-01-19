"""Material repository for material-related database operations."""

from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Material, MaterialType
from src.db.repositories.base import BaseRepository


class MaterialRepository(BaseRepository[Material]):
    """Repository for Material entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Material)

    async def get_by_organization(
        self,
        organization_id: str,
        material_type: Optional[MaterialType] = None,
        low_stock_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[Material]:
        """Get materials in an organization."""
        query = select(Material).where(Material.organization_id == organization_id)

        if material_type:
            query = query.where(Material.material_type == material_type)

        if low_stock_only:
            query = query.where(Material.remaining_grams < Material.low_threshold_grams)

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_low_stock(self, organization_id: str) -> List[Material]:
        """Get materials below their low stock threshold."""
        result = await self.session.execute(
            select(Material).where(
                Material.organization_id == organization_id,
                Material.remaining_grams < Material.low_threshold_grams
            )
        )
        return list(result.scalars().all())

    async def get_by_type_and_color(
        self,
        organization_id: str,
        material_type: MaterialType,
        color: str
    ) -> List[Material]:
        """Get materials matching type and color."""
        result = await self.session.execute(
            select(Material).where(
                Material.organization_id == organization_id,
                Material.material_type == material_type,
                Material.color.ilike(f"%{color}%")
            )
        )
        return list(result.scalars().all())

    async def create_material(
        self,
        organization_id: str,
        name: str,
        material_type: MaterialType,
        color: str,
        total_weight_grams: float = 1000.0,
        cost_per_gram: float = 0.025,
        brand: Optional[str] = None,
        color_hex: Optional[str] = None,
        print_temp_min: int = 190,
        print_temp_max: int = 220,
        bed_temp_min: int = 50,
        bed_temp_max: int = 60
    ) -> Material:
        """Create a new material entry."""
        material = Material(
            organization_id=organization_id,
            name=name,
            material_type=material_type,
            color=color,
            brand=brand,
            color_hex=color_hex,
            total_weight_grams=total_weight_grams,
            remaining_grams=total_weight_grams,
            cost_per_gram=cost_per_gram,
            print_temp_min=print_temp_min,
            print_temp_max=print_temp_max,
            bed_temp_min=bed_temp_min,
            bed_temp_max=bed_temp_max
        )
        self.session.add(material)
        await self.session.flush()
        await self.session.refresh(material)
        return material

    async def use_material(
        self,
        material_id: str,
        grams_used: float
    ) -> Optional[Material]:
        """Record material usage."""
        material = await self.get_by_id(material_id)
        if not material:
            return None

        new_remaining = max(0, material.remaining_grams - grams_used)
        return await self.update(material_id, remaining_grams=new_remaining)

    async def refill_material(
        self,
        material_id: str,
        grams_added: float,
        new_cost_per_gram: Optional[float] = None
    ) -> Optional[Material]:
        """Add material to existing spool."""
        material = await self.get_by_id(material_id)
        if not material:
            return None

        updates = {
            "remaining_grams": material.remaining_grams + grams_added,
            "total_weight_grams": material.total_weight_grams + grams_added
        }
        if new_cost_per_gram is not None:
            updates["cost_per_gram"] = new_cost_per_gram

        return await self.update(material_id, **updates)

    async def get_compatible_with(
        self,
        organization_id: str,
        material_type: MaterialType
    ) -> List[Material]:
        """Get materials compatible with a given type for multi-material printing."""
        # Compatibility rules (simplified)
        compatible_types = {
            MaterialType.PLA: [MaterialType.PLA, MaterialType.PVA],
            MaterialType.PETG: [MaterialType.PETG],
            MaterialType.ABS: [MaterialType.ABS, MaterialType.ASA],
            MaterialType.ASA: [MaterialType.ASA, MaterialType.ABS],
            MaterialType.TPU: [MaterialType.TPU],
            MaterialType.NYLON: [MaterialType.NYLON],
            MaterialType.PC: [MaterialType.PC],
            MaterialType.PVA: [MaterialType.PVA, MaterialType.PLA],
        }

        allowed = compatible_types.get(material_type, [material_type])

        result = await self.session.execute(
            select(Material).where(
                Material.organization_id == organization_id,
                Material.material_type.in_(allowed),
                Material.remaining_grams > 0
            )
        )
        return list(result.scalars().all())

    async def calculate_cost(
        self,
        material_id: str,
        grams: float
    ) -> Optional[float]:
        """Calculate cost for using a specific amount of material."""
        material = await self.get_by_id(material_id)
        if not material:
            return None
        return grams * material.cost_per_gram

    async def get_inventory_value(self, organization_id: str) -> dict:
        """Calculate total inventory value."""
        materials = await self.get_by_organization(organization_id)

        total_grams = sum(m.remaining_grams for m in materials)
        total_value = sum(m.remaining_grams * m.cost_per_gram for m in materials)
        by_type = {}

        for m in materials:
            type_name = m.material_type.value
            if type_name not in by_type:
                by_type[type_name] = {"grams": 0, "value": 0, "count": 0}
            by_type[type_name]["grams"] += m.remaining_grams
            by_type[type_name]["value"] += m.remaining_grams * m.cost_per_gram
            by_type[type_name]["count"] += 1

        return {
            "total_grams": total_grams,
            "total_value": round(total_value, 2),
            "spool_count": len(materials),
            "by_type": by_type
        }
