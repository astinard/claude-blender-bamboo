"""FastAPI authentication middleware and dependencies."""

from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader

from src.auth.jwt import decode_token, TokenPayload
from src.auth.api_keys import extract_key_prefix, verify_api_key
from src.auth.rbac import Permission, has_permission, PermissionDeniedError
from src.db import get_db
from src.db.models import User, UserRole, APIKey
from src.db.repositories.users import UserRepository
from src.utils import get_logger

logger = get_logger("auth.middleware")

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthenticatedUser:
    """Represents an authenticated user (via JWT or API key)."""

    def __init__(
        self,
        id: str,
        email: str,
        org_id: str,
        role: UserRole,
        auth_method: str = "jwt",
        scopes: Optional[list[str]] = None
    ):
        self.id = id
        self.email = email
        self.org_id = org_id
        self.role = role
        self.auth_method = auth_method
        self.scopes = scopes or []

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return has_permission(self.role, permission)

    def has_scope(self, scope: str) -> bool:
        """Check if user has a specific scope (for API keys)."""
        if not self.scopes:
            return True  # No scope restrictions
        return scope in self.scopes


async def get_token_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)]
) -> Optional[AuthenticatedUser]:
    """Extract user from JWT bearer token."""
    if not credentials:
        return None

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        return None

    if payload.type != "access":
        return None

    return AuthenticatedUser(
        id=payload.sub,
        email=payload.email,
        org_id=payload.org_id,
        role=UserRole(payload.role),
        auth_method="jwt",
        scopes=payload.scopes
    )


async def get_api_key_user(
    request: Request,
    api_key: Annotated[Optional[str], Depends(api_key_header)]
) -> Optional[AuthenticatedUser]:
    """Extract user from API key header."""
    if not api_key:
        return None

    # Extract key prefix for database lookup
    key_prefix = extract_key_prefix(api_key)
    if not key_prefix:
        logger.warning("Invalid API key format")
        return None

    # Look up API key in database
    async with get_db() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(APIKey).where(APIKey.key_prefix == key_prefix)
        )
        api_key_record = result.scalar_one_or_none()

        if not api_key_record:
            logger.warning(f"API key not found: {key_prefix}")
            return None

        # Verify the key hash
        if not verify_api_key(api_key, api_key_record.key_hash):
            logger.warning(f"API key verification failed: {key_prefix}")
            return None

        # Check expiration
        if api_key_record.expires_at:
            from datetime import datetime
            if datetime.utcnow() > api_key_record.expires_at:
                logger.warning(f"API key expired: {key_prefix}")
                return None

        # Get the user
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(api_key_record.user_id)

        if not user or not user.is_active:
            return None

        # Update last used
        from datetime import datetime
        api_key_record.last_used = datetime.utcnow()
        await session.commit()

        # Parse scopes
        scopes = None
        if api_key_record.scopes:
            import json
            scopes = json.loads(api_key_record.scopes)

        return AuthenticatedUser(
            id=user.id,
            email=user.email,
            org_id=user.organization_id,
            role=user.role,
            auth_method="api_key",
            scopes=scopes
        )


async def get_current_user(
    token_user: Annotated[Optional[AuthenticatedUser], Depends(get_token_user)],
    api_key_user: Annotated[Optional[AuthenticatedUser], Depends(get_api_key_user)]
) -> AuthenticatedUser:
    """Get the current authenticated user (JWT or API key).

    Raises HTTPException if not authenticated.
    """
    user = token_user or api_key_user

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    token_user: Annotated[Optional[AuthenticatedUser], Depends(get_token_user)],
    api_key_user: Annotated[Optional[AuthenticatedUser], Depends(get_api_key_user)]
) -> Optional[AuthenticatedUser]:
    """Get the current user if authenticated, None otherwise."""
    return token_user or api_key_user


def require_permission(permission: Permission):
    """FastAPI dependency to require a specific permission.

    Usage:
        @router.post("/printers/{id}/start")
        async def start_print(
            id: str,
            user: AuthenticatedUser = Depends(require_permission(Permission.PRINTERS_CONTROL))
        ):
            ...
    """
    async def permission_checker(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)]
    ) -> AuthenticatedUser:
        if not current_user.has_permission(permission):
            logger.warning(
                f"Permission denied: user {current_user.id} lacks {permission.value}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires {permission.value}"
            )
        return current_user

    return permission_checker


def require_any_permission(*permissions: Permission):
    """FastAPI dependency to require any of the specified permissions."""
    async def permission_checker(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)]
    ) -> AuthenticatedUser:
        if not any(current_user.has_permission(p) for p in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires one of {[p.value for p in permissions]}"
            )
        return current_user

    return permission_checker


def require_role(min_role: UserRole):
    """FastAPI dependency to require a minimum role level."""
    role_hierarchy = {
        UserRole.VIEWER: 0,
        UserRole.OPERATOR: 1,
        UserRole.ADMIN: 2
    }

    async def role_checker(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)]
    ) -> AuthenticatedUser:
        user_level = role_hierarchy.get(current_user.role, 0)
        required_level = role_hierarchy.get(min_role, 0)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role.value} role or higher"
            )
        return current_user

    return role_checker


# Common dependencies
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
OptionalUser = Annotated[Optional[AuthenticatedUser], Depends(get_current_user_optional)]
AdminUser = Annotated[AuthenticatedUser, Depends(require_role(UserRole.ADMIN))]
OperatorUser = Annotated[AuthenticatedUser, Depends(require_role(UserRole.OPERATOR))]
