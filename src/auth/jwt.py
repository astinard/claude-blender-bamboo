"""JWT token handling for authentication."""

import os
from datetime import datetime, timedelta
from typing import Optional, Any
from dataclasses import dataclass

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from src.utils import get_logger

logger = get_logger("auth.jwt")

# Configuration from environment
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


@dataclass
class TokenPayload:
    """JWT token payload structure."""
    sub: str  # User ID
    email: str
    org_id: str
    role: str
    exp: datetime
    iat: datetime
    type: str  # "access" or "refresh"
    scopes: list[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JWT encoding."""
        data = {
            "sub": self.sub,
            "email": self.email,
            "org_id": self.org_id,
            "role": self.role,
            "exp": self.exp,
            "iat": self.iat,
            "type": self.type,
        }
        if self.scopes:
            data["scopes"] = self.scopes
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "TokenPayload":
        """Create from dictionary (decoded JWT)."""
        return cls(
            sub=data["sub"],
            email=data["email"],
            org_id=data["org_id"],
            role=data["role"],
            exp=datetime.fromtimestamp(data["exp"]) if isinstance(data["exp"], (int, float)) else data["exp"],
            iat=datetime.fromtimestamp(data["iat"]) if isinstance(data["iat"], (int, float)) else data["iat"],
            type=data.get("type", "access"),
            scopes=data.get("scopes"),
        )


def create_access_token(
    user_id: str,
    email: str,
    org_id: str,
    role: str,
    scopes: Optional[list[str]] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a new access token."""
    now = datetime.utcnow()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = TokenPayload(
        sub=user_id,
        email=email,
        org_id=org_id,
        role=role,
        exp=expire,
        iat=now,
        type="access",
        scopes=scopes,
    )

    token = jwt.encode(payload.to_dict(), SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"Created access token for user {user_id}")
    return token


def create_refresh_token(
    user_id: str,
    email: str,
    org_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a new refresh token."""
    now = datetime.utcnow()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    payload = TokenPayload(
        sub=user_id,
        email=email,
        org_id=org_id,
        role=role,
        exp=expire,
        iat=now,
        type="refresh",
    )

    token = jwt.encode(payload.to_dict(), SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"Created refresh token for user {user_id}")
    return token


def verify_token(token: str, expected_type: str = "access") -> bool:
    """Verify a token is valid and not expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            logger.warning(f"Token type mismatch: expected {expected_type}, got {payload.get('type')}")
            return False
        return True
    except ExpiredSignatureError:
        logger.debug("Token has expired")
        return False
    except InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return False


def decode_token(token: str) -> Optional[TokenPayload]:
    """Decode a token and return the payload."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload.from_dict(payload)
    except ExpiredSignatureError:
        logger.debug("Token has expired")
        return None
    except InvalidTokenError as e:
        logger.warning(f"Failed to decode token: {e}")
        return None


def refresh_access_token(refresh_token: str) -> Optional[str]:
    """Use a refresh token to get a new access token."""
    if not verify_token(refresh_token, expected_type="refresh"):
        return None

    payload = decode_token(refresh_token)
    if not payload:
        return None

    return create_access_token(
        user_id=payload.sub,
        email=payload.email,
        org_id=payload.org_id,
        role=payload.role,
    )
