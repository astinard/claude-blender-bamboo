"""User management routes."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.repositories.users import UserRepository
from src.db.models import UserRole
from src.auth.middleware import CurrentUser, require_permission
from src.auth.rbac import Permission

router = APIRouter()


class UserInvite(BaseModel):
    email: EmailStr
    name: str
    role: UserRole = UserRole.VIEWER


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[UserRole] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: str


@router.get("", response_model=List[UserResponse])
async def list_users(
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_READ)),
    db: AsyncSession = Depends(get_db)
):
    """List users in the organization."""
    repo = UserRepository(db)
    users = await repo.get_by_organization(current_user.org_id)
    return [UserResponse(**u.to_dict()) for u in users]


@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_user(
    request: UserInvite,
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_INVITE)),
    db: AsyncSession = Depends(get_db)
):
    """Invite a new user to the organization."""
    repo = UserRepository(db)

    existing = await repo.get_by_email(request.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user without password (they'll set it via invite link)
    user = await repo.create_user(
        email=request.email,
        name=request.name,
        organization_id=current_user.org_id,
        role=request.role
    )
    await db.commit()

    # TODO: Send invitation email
    return {"message": "Invitation sent", "user_id": user.id}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_READ)),
    db: AsyncSession = Depends(get_db)
):
    """Get user details."""
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user or user.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user.to_dict())


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    request: UserUpdate,
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """Update user details."""
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user or user.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="User not found")

    updates = request.model_dump(exclude_unset=True)
    user = await repo.update(user_id, **updates)
    await db.commit()
    return UserResponse(**user.to_dict())


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_DELETE)),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate a user."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user or user.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="User not found")

    await repo.deactivate_user(user_id)
    await db.commit()
