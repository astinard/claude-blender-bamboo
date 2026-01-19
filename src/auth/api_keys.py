"""API key generation and verification."""

import hashlib
import secrets
from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.utils import get_logger

logger = get_logger("auth.api_keys")

# API key prefix for identification
API_KEY_PREFIX = "cfl_"  # Claude Fab Lab


@dataclass
class APIKeyData:
    """Parsed API key data."""
    prefix: str
    key_id: str
    secret: str

    @property
    def full_key(self) -> str:
        """Return the full API key string."""
        return f"{self.prefix}{self.key_id}_{self.secret}"

    @property
    def display_key(self) -> str:
        """Return a safely displayable version (masked secret)."""
        return f"{self.prefix}{self.key_id}_{'*' * 8}"


def generate_api_key() -> Tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix_for_display, key_hash_for_storage)

    The full_key is shown to the user once and should never be stored.
    The key_prefix (first 8 chars) is stored for identification.
    The key_hash is stored for verification.
    """
    # Generate components
    key_id = secrets.token_hex(4)  # 8 chars
    secret = secrets.token_hex(16)  # 32 chars

    # Full key format: cfl_<key_id>_<secret>
    full_key = f"{API_KEY_PREFIX}{key_id}_{secret}"

    # Prefix for display/identification (first 12 chars)
    key_prefix = f"{API_KEY_PREFIX}{key_id}"

    # Hash for storage (using SHA-256)
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    logger.info(f"Generated new API key with prefix {key_prefix}")

    return full_key, key_prefix, key_hash


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage or comparison.

    Args:
        api_key: The full API key

    Returns:
        SHA-256 hash of the key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Verify an API key against its stored hash.

    Args:
        api_key: The full API key to verify
        stored_hash: The stored hash to compare against

    Returns:
        True if the key is valid
    """
    computed_hash = hash_api_key(api_key)
    return secrets.compare_digest(computed_hash, stored_hash)


def parse_api_key(api_key: str) -> Optional[APIKeyData]:
    """Parse an API key into its components.

    Args:
        api_key: The full API key string

    Returns:
        APIKeyData if valid, None otherwise
    """
    if not api_key.startswith(API_KEY_PREFIX):
        logger.warning("API key has invalid prefix")
        return None

    # Remove prefix
    key_part = api_key[len(API_KEY_PREFIX):]

    # Split into key_id and secret
    parts = key_part.split("_", 1)
    if len(parts) != 2:
        logger.warning("API key has invalid format")
        return None

    key_id, secret = parts

    if len(key_id) != 8 or len(secret) != 32:
        logger.warning("API key has invalid component lengths")
        return None

    return APIKeyData(
        prefix=API_KEY_PREFIX,
        key_id=key_id,
        secret=secret
    )


def extract_key_prefix(api_key: str) -> Optional[str]:
    """Extract the key prefix (for database lookup).

    Args:
        api_key: The full API key

    Returns:
        The key prefix (first 12 chars) or None if invalid
    """
    parsed = parse_api_key(api_key)
    if not parsed:
        return None
    return f"{parsed.prefix}{parsed.key_id}"


def is_valid_api_key_format(api_key: str) -> bool:
    """Check if a string has valid API key format.

    Args:
        api_key: String to check

    Returns:
        True if format is valid
    """
    return parse_api_key(api_key) is not None


def mask_api_key(api_key: str) -> str:
    """Mask an API key for safe display.

    Args:
        api_key: The full API key

    Returns:
        Masked version showing only prefix
    """
    parsed = parse_api_key(api_key)
    if not parsed:
        return "***invalid***"
    return parsed.display_key
