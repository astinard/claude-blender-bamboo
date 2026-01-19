"""Role-Based Access Control (RBAC) for Claude Fab Lab."""

from enum import Enum
from typing import List, Set, Optional, Callable
from functools import wraps

from src.db.models import UserRole
from src.utils import get_logger

logger = get_logger("auth.rbac")


class Permission(str, Enum):
    """Granular permissions for resources."""

    # Printer permissions
    PRINTERS_READ = "printers:read"
    PRINTERS_CREATE = "printers:create"
    PRINTERS_UPDATE = "printers:update"
    PRINTERS_DELETE = "printers:delete"
    PRINTERS_CONTROL = "printers:control"  # Start/stop/pause prints

    # Print job permissions
    JOBS_READ = "jobs:read"
    JOBS_CREATE = "jobs:create"
    JOBS_UPDATE = "jobs:update"
    JOBS_DELETE = "jobs:delete"
    JOBS_CANCEL = "jobs:cancel"

    # Model permissions
    MODELS_READ = "models:read"
    MODELS_CREATE = "models:create"
    MODELS_UPDATE = "models:update"
    MODELS_DELETE = "models:delete"

    # Material permissions
    MATERIALS_READ = "materials:read"
    MATERIALS_CREATE = "materials:create"
    MATERIALS_UPDATE = "materials:update"
    MATERIALS_DELETE = "materials:delete"

    # Analytics permissions
    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_EXPORT = "analytics:export"

    # AI features
    AI_GENERATE = "ai:generate"
    AI_ANALYZE = "ai:analyze"

    # User management
    USERS_READ = "users:read"
    USERS_INVITE = "users:invite"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"

    # Organization management
    ORG_READ = "org:read"
    ORG_UPDATE = "org:update"
    ORG_BILLING = "org:billing"

    # API key management
    API_KEYS_READ = "api_keys:read"
    API_KEYS_CREATE = "api_keys:create"
    API_KEYS_DELETE = "api_keys:delete"

    # Audit logs
    AUDIT_READ = "audit:read"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[UserRole, Set[Permission]] = {
    UserRole.VIEWER: {
        Permission.PRINTERS_READ,
        Permission.JOBS_READ,
        Permission.MODELS_READ,
        Permission.MATERIALS_READ,
        Permission.ANALYTICS_VIEW,
        Permission.ORG_READ,
    },

    UserRole.OPERATOR: {
        # All viewer permissions
        Permission.PRINTERS_READ,
        Permission.JOBS_READ,
        Permission.MODELS_READ,
        Permission.MATERIALS_READ,
        Permission.ANALYTICS_VIEW,
        Permission.ORG_READ,

        # Plus operational permissions
        Permission.PRINTERS_CONTROL,
        Permission.JOBS_CREATE,
        Permission.JOBS_UPDATE,
        Permission.JOBS_CANCEL,
        Permission.MODELS_CREATE,
        Permission.MODELS_UPDATE,
        Permission.MATERIALS_UPDATE,
        Permission.AI_GENERATE,
        Permission.AI_ANALYZE,
        Permission.API_KEYS_READ,
        Permission.API_KEYS_CREATE,
    },

    UserRole.ADMIN: {
        # All permissions
        Permission.PRINTERS_READ,
        Permission.PRINTERS_CREATE,
        Permission.PRINTERS_UPDATE,
        Permission.PRINTERS_DELETE,
        Permission.PRINTERS_CONTROL,

        Permission.JOBS_READ,
        Permission.JOBS_CREATE,
        Permission.JOBS_UPDATE,
        Permission.JOBS_DELETE,
        Permission.JOBS_CANCEL,

        Permission.MODELS_READ,
        Permission.MODELS_CREATE,
        Permission.MODELS_UPDATE,
        Permission.MODELS_DELETE,

        Permission.MATERIALS_READ,
        Permission.MATERIALS_CREATE,
        Permission.MATERIALS_UPDATE,
        Permission.MATERIALS_DELETE,

        Permission.ANALYTICS_VIEW,
        Permission.ANALYTICS_EXPORT,

        Permission.AI_GENERATE,
        Permission.AI_ANALYZE,

        Permission.USERS_READ,
        Permission.USERS_INVITE,
        Permission.USERS_UPDATE,
        Permission.USERS_DELETE,

        Permission.ORG_READ,
        Permission.ORG_UPDATE,
        Permission.ORG_BILLING,

        Permission.API_KEYS_READ,
        Permission.API_KEYS_CREATE,
        Permission.API_KEYS_DELETE,

        Permission.AUDIT_READ,
    },
}


def get_user_permissions(role: UserRole) -> Set[Permission]:
    """Get all permissions for a user role."""
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: UserRole, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    permissions = get_user_permissions(role)
    return permission in permissions


def has_any_permission(role: UserRole, permissions: List[Permission]) -> bool:
    """Check if a role has any of the specified permissions."""
    user_permissions = get_user_permissions(role)
    return any(p in user_permissions for p in permissions)


def has_all_permissions(role: UserRole, permissions: List[Permission]) -> bool:
    """Check if a role has all of the specified permissions."""
    user_permissions = get_user_permissions(role)
    return all(p in user_permissions for p in permissions)


class PermissionDeniedError(Exception):
    """Raised when a user lacks required permissions."""

    def __init__(self, required: Permission, role: UserRole):
        self.required = required
        self.role = role
        super().__init__(
            f"Permission denied: role '{role.value}' lacks '{required.value}' permission"
        )


def require_permission(permission: Permission):
    """Decorator to require a specific permission.

    Usage:
        @require_permission(Permission.PRINTERS_CONTROL)
        async def start_print(user: User, printer_id: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from args or kwargs
            user = kwargs.get("user") or kwargs.get("current_user")
            if user is None and args:
                # Try to find user in positional args
                for arg in args:
                    if hasattr(arg, "role"):
                        user = arg
                        break

            if user is None:
                raise ValueError("No user found in function arguments")

            role = user.role if isinstance(user.role, UserRole) else UserRole(user.role)

            if not has_permission(role, permission):
                logger.warning(
                    f"Permission denied: user {getattr(user, 'id', 'unknown')} "
                    f"with role {role.value} tried to access {permission.value}"
                )
                raise PermissionDeniedError(permission, role)

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(*permissions: Permission):
    """Decorator to require any of the specified permissions."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("user") or kwargs.get("current_user")
            if user is None and args:
                for arg in args:
                    if hasattr(arg, "role"):
                        user = arg
                        break

            if user is None:
                raise ValueError("No user found in function arguments")

            role = user.role if isinstance(user.role, UserRole) else UserRole(user.role)

            if not has_any_permission(role, list(permissions)):
                logger.warning(
                    f"Permission denied: user {getattr(user, 'id', 'unknown')} "
                    f"with role {role.value} lacks any of {[p.value for p in permissions]}"
                )
                raise PermissionDeniedError(permissions[0], role)

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def check_resource_ownership(
    user_id: str,
    resource_owner_id: str,
    role: UserRole,
    admin_override: bool = True
) -> bool:
    """Check if a user owns a resource or has admin override.

    Args:
        user_id: The ID of the current user
        resource_owner_id: The ID of the resource owner
        role: The user's role
        admin_override: Whether admin role bypasses ownership check

    Returns:
        True if user can access the resource
    """
    # Owner always has access
    if user_id == resource_owner_id:
        return True

    # Admin override
    if admin_override and role == UserRole.ADMIN:
        return True

    return False
