"""Password hashing and verification."""

import hashlib
import os
import secrets
from typing import Tuple

# Try to use bcrypt if available, fall back to PBKDF2
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

from src.utils import get_logger

logger = get_logger("auth.password")


def hash_password(password: str) -> str:
    """Hash a password securely.

    Uses bcrypt if available, otherwise falls back to PBKDF2-SHA256.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    if BCRYPT_AVAILABLE:
        # Use bcrypt with cost factor 12
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    else:
        # Fallback to PBKDF2-SHA256
        salt = secrets.token_hex(16)
        iterations = 100000
        hash_bytes = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations
        )
        return f"pbkdf2:sha256:{iterations}${salt}${hash_bytes.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash.

    Args:
        password: Plain text password to verify
        hashed: Previously hashed password

    Returns:
        True if password matches, False otherwise
    """
    try:
        if hashed.startswith("pbkdf2:"):
            # PBKDF2 hash
            parts = hashed.split("$")
            if len(parts) != 3:
                return False

            config = parts[0].split(":")
            if len(config) != 3:
                return False

            algorithm = config[1]
            iterations = int(config[2])
            salt = parts[1]
            stored_hash = parts[2]

            if algorithm != "sha256":
                logger.warning(f"Unsupported hash algorithm: {algorithm}")
                return False

            computed_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                iterations
            ).hex()

            return secrets.compare_digest(computed_hash, stored_hash)

        elif BCRYPT_AVAILABLE:
            # Bcrypt hash
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed.encode('utf-8')
            )
        else:
            logger.error("Cannot verify bcrypt hash without bcrypt library")
            return False

    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def generate_random_password(length: int = 16) -> str:
    """Generate a secure random password.

    Args:
        length: Desired password length (minimum 8)

    Returns:
        Random password string
    """
    length = max(8, length)
    # Use a mix of characters
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Validate password meets strength requirements.

    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    return True, ""
