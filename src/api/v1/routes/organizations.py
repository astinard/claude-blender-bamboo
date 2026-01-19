"""Organization management routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.repositories.organizations import OrganizationRepository
from src.db.models import PlanTier
from src.auth.middleware import CurrentUser, require_permission
from src.auth.rbac import Permission

router = APIRouter()


class OrgUpdate(BaseModel):
    name: Optional[str] = None


class OrgResponse(BaseModel):
    id: str
    name: str
    plan_tier: str
    max_printers: int
    max_users: int
    storage_limit_gb: int
    ai_generations_limit: int


@router.get("/current", response_model=OrgResponse)
async def get_current_organization(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get current organization details."""
    repo = OrganizationRepository(db)
    org = await repo.get_by_id(current_user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrgResponse(**org.to_dict())


@router.patch("/current", response_model=OrgResponse)
async def update_organization(
    request: OrgUpdate,
    current_user: CurrentUser = Depends(require_permission(Permission.ORG_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """Update organization settings."""
    repo = OrganizationRepository(db)
    updates = request.model_dump(exclude_unset=True)
    org = await repo.update(current_user.org_id, **updates)
    await db.commit()
    return OrgResponse(**org.to_dict())


@router.get("/current/usage")
async def get_organization_usage(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get current organization resource usage."""
    from src.db.repositories.printers import PrinterRepository
    from src.db.repositories.users import UserRepository
    from src.db.repositories.models import Model3DRepository

    org_repo = OrganizationRepository(db)
    printer_repo = PrinterRepository(db)
    user_repo = UserRepository(db)
    model_repo = Model3DRepository(db)

    org = await org_repo.get_by_id(current_user.org_id)
    printers = await printer_repo.count(organization_id=current_user.org_id)
    users = await user_repo.count(organization_id=current_user.org_id)
    storage = await model_repo.get_storage_usage(current_user.org_id)
    ai_gens = await model_repo.get_ai_generation_count(current_user.org_id)

    return {
        "printers": {"used": printers, "limit": org.max_printers},
        "users": {"used": users, "limit": org.max_users},
        "storage_gb": {"used": storage["total_gb"], "limit": org.storage_limit_gb},
        "ai_generations": {"used": ai_gens, "limit": org.ai_generations_limit}
    }
