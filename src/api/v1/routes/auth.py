"""Authentication routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.repositories.users import UserRepository
from src.db.repositories.organizations import OrganizationRepository
from src.db.models import UserRole, PlanTier
from src.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    decode_token,
    hash_password,
    verify_password,
    generate_api_key,
)
from src.auth.middleware import CurrentUser, AuthenticatedUser
from src.utils import get_logger

logger = get_logger("api.auth")
router = APIRouter()


# Request/Response models
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    organization_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    organization_id: str
    is_active: bool


class APIKeyRequest(BaseModel):
    name: str
    scopes: Optional[list[str]] = None


class APIKeyResponse(BaseModel):
    key: str
    name: str
    key_prefix: str
    message: str = "Save this key securely. It will not be shown again."


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user and organization."""
    user_repo = UserRepository(db)
    org_repo = OrganizationRepository(db)

    # Check if email already exists
    existing = await user_repo.get_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create organization
    org_name = request.organization_name or f"{request.name}'s Workspace"
    org = await org_repo.create_organization(name=org_name, plan_tier=PlanTier.FREE)

    # Create user as admin of the new org
    password_hash = hash_password(request.password)
    user = await user_repo.create_user(
        email=request.email,
        name=request.name,
        organization_id=org.id,
        password_hash=password_hash,
        role=UserRole.ADMIN
    )

    await db.commit()

    logger.info(f"New user registered: {user.email}")

    # Generate tokens
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        org_id=org.id,
        role=user.role.value
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        email=user.email,
        org_id=org.id,
        role=user.role.value
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password."""
    user_repo = UserRepository(db)

    # Find user
    user = await user_repo.get_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled"
        )

    # Verify password
    if not user.password_hash or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Update last login
    await user_repo.update_last_login(user.id)
    await db.commit()

    logger.info(f"User logged in: {user.email}")

    # Generate tokens
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        org_id=user.organization_id,
        role=user.role.value
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        email=user.email,
        org_id=user.organization_id,
        role=user.role.value
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest):
    """Refresh access token using refresh token."""
    if not verify_token(request.refresh_token, expected_type="refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    payload = decode_token(request.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Generate new tokens
    access_token = create_access_token(
        user_id=payload.sub,
        email=payload.email,
        org_id=payload.org_id,
        role=payload.role
    )
    new_refresh_token = create_refresh_token(
        user_id=payload.sub,
        email=payload.email,
        org_id=payload.org_id,
        role=payload.role
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.email.split("@")[0],  # Simplified, should fetch from DB
        role=current_user.role.value,
        organization_id=current_user.org_id,
        is_active=True
    )


@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: APIKeyRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Create a new API key for the current user."""
    import json
    from src.db.models import APIKey

    # Generate key
    full_key, key_prefix, key_hash = generate_api_key()

    # Store in database
    api_key = APIKey(
        user_id=current_user.id,
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=json.dumps(request.scopes) if request.scopes else None
    )
    db.add(api_key)
    await db.commit()

    logger.info(f"API key created for user {current_user.id}: {key_prefix}")

    return APIKeyResponse(
        key=full_key,
        name=request.name,
        key_prefix=key_prefix
    )


@router.get("/api-keys")
async def list_api_keys(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """List all API keys for the current user."""
    from sqlalchemy import select
    from src.db.models import APIKey

    result = await db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id)
    )
    keys = result.scalars().all()

    return [
        {
            "id": k.id,
            "name": k.name,
            "key_prefix": k.key_prefix,
            "last_used": k.last_used.isoformat() if k.last_used else None,
            "created_at": k.created_at.isoformat()
        }
        for k in keys
    ]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Delete an API key."""
    from sqlalchemy import select, delete
    from src.db.models import APIKey

    # Verify ownership
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.user_id == current_user.id
        )
    )
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    await db.execute(delete(APIKey).where(APIKey.id == key_id))
    await db.commit()

    logger.info(f"API key deleted: {key.key_prefix}")
