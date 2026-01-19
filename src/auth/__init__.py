"""Authentication and authorization module for Claude Fab Lab.

Provides JWT-based authentication, role-based access control (RBAC),
API key management, and OAuth2 integration.
"""

from src.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
    decode_token,
    TokenPayload,
)
from src.auth.rbac import (
    Permission,
    has_permission,
    require_permission,
    get_user_permissions,
)
from src.auth.password import (
    hash_password,
    verify_password,
)
from src.auth.api_keys import (
    generate_api_key,
    verify_api_key,
)

__all__ = [
    # JWT
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "decode_token",
    "TokenPayload",
    # RBAC
    "Permission",
    "has_permission",
    "require_permission",
    "get_user_permissions",
    # Password
    "hash_password",
    "verify_password",
    # API Keys
    "generate_api_key",
    "verify_api_key",
]
