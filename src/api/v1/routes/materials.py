"""Material management routes."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.repositories.materials import MaterialRepository
from src.db.models import MaterialType
from src.auth.middleware import CurrentUser, require_permission
from src.auth.rbac import Permission

router = APIRouter()


class MaterialCreate(BaseModel):
    name: str
    material_type: MaterialType
    color: str
    brand: Optional[str] = None
    total_weight_grams: float = 1000.0
    cost_per_gram: float = 0.025


class MaterialResponse(BaseModel):
    id: str
    name: str
    material_type: str
    color: str
    remaining_grams: float
    remaining_percent: float


@router.get("", response_model=List[MaterialResponse])
async def list_materials(
    current_user: CurrentUser,
    material_type: Optional[MaterialType] = None,
    low_stock: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """List materials in inventory."""
    repo = MaterialRepository(db)
    materials = await repo.get_by_organization(
        current_user.org_id,
        material_type=material_type,
        low_stock_only=low_stock
    )
    return [MaterialResponse(**m.to_dict()) for m in materials]


@router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    request: MaterialCreate,
    current_user: CurrentUser = Depends(require_permission(Permission.MATERIALS_CREATE)),
    db: AsyncSession = Depends(get_db)
):
    """Add new material to inventory."""
    repo = MaterialRepository(db)
    material = await repo.create_material(
        organization_id=current_user.org_id,
        **request.model_dump()
    )
    await db.commit()
    return MaterialResponse(**material.to_dict())


@router.get("/inventory-value")
async def get_inventory_value(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get total inventory value."""
    repo = MaterialRepository(db)
    return await repo.get_inventory_value(current_user.org_id)


@router.get("/low-stock")
async def get_low_stock_alerts(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get materials below low stock threshold."""
    repo = MaterialRepository(db)
    materials = await repo.get_low_stock(current_user.org_id)
    return [MaterialResponse(**m.to_dict()) for m in materials]


@router.post("/{material_id}/use")
async def use_material(
    material_id: str,
    grams: float,
    current_user: CurrentUser = Depends(require_permission(Permission.MATERIALS_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """Record material usage."""
    repo = MaterialRepository(db)
    material = await repo.get_by_id(material_id)
    if not material or material.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Material not found")

    material = await repo.use_material(material_id, grams)
    await db.commit()
    return MaterialResponse(**material.to_dict())
