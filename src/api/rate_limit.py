"""Rate limiting middleware for API protection.

Implements sliding window rate limiting with support for:
- Per-IP rate limits
- Per-user rate limits
- Per-API-key rate limits
- Endpoint-specific limits
- Burst allowance
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Tuple

from src.utils import get_logger

logger = get_logger("api.rate_limit")


class RateLimitScope(str, Enum):
    """Scope for rate limiting."""
    IP = "ip"
    USER = "user"
    API_KEY = "api_key"
    ORGANIZATION = "organization"
    GLOBAL = "global"


class RateLimitStatus(str, Enum):
    """Status of rate limit check."""
    ALLOWED = "allowed"
    LIMITED = "limited"
    BLOCKED = "blocked"


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule."""

    name: str
    requests: int  # Number of requests allowed
    window_seconds: int  # Time window in seconds
    scope: RateLimitScope = RateLimitScope.IP

    # Optional burst allowance
    burst_requests: Optional[int] = None
    burst_window_seconds: int = 10

    # Blocking for repeated violations
    block_after_violations: int = 5
    block_duration_seconds: int = 300  # 5 minutes

    # Whitelist/blacklist
    whitelist: List[str] = field(default_factory=list)
    blacklist: List[str] = field(default_factory=list)

    # Response customization
    retry_after_header: bool = True
    include_remaining: bool = True


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    status: RateLimitStatus
    allowed: bool
    remaining: int
    limit: int
    reset_at: datetime
    retry_after_seconds: Optional[int] = None

    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_at.timestamp())),
        }
        if self.retry_after_seconds:
            headers["Retry-After"] = str(self.retry_after_seconds)
        return headers


@dataclass
class SlidingWindow:
    """Sliding window for rate limiting."""

    requests: List[float] = field(default_factory=list)  # Timestamps
    violations: int = 0
    blocked_until: Optional[float] = None


class RateLimiter:
    """
    Sliding window rate limiter.

    Features:
    - Multiple rate limit rules
    - Per-scope tracking (IP, user, API key, etc.)
    - Burst allowance
    - Automatic blocking for repeated violations
    - Whitelist/blacklist support
    - Redis-compatible for distributed deployments
    """

    # Default rate limits
    DEFAULT_LIMITS = {
        "default": RateLimitConfig(
            name="default",
            requests=100,
            window_seconds=60,
            scope=RateLimitScope.IP,
        ),
        "auth": RateLimitConfig(
            name="auth",
            requests=10,
            window_seconds=60,
            scope=RateLimitScope.IP,
            block_after_violations=3,
            block_duration_seconds=600,
        ),
        "api_generate": RateLimitConfig(
            name="api_generate",
            requests=20,
            window_seconds=60,
            scope=RateLimitScope.USER,
            burst_requests=5,
            burst_window_seconds=10,
        ),
        "api_heavy": RateLimitConfig(
            name="api_heavy",
            requests=10,
            window_seconds=60,
            scope=RateLimitScope.USER,
        ),
    }

    def __init__(self):
        # In-memory storage (use Redis in production)
        self._windows: Dict[str, SlidingWindow] = defaultdict(SlidingWindow)
        self._configs: Dict[str, RateLimitConfig] = dict(self.DEFAULT_LIMITS)
        self._global_whitelist: List[str] = []
        self._global_blacklist: List[str] = []

    def add_config(self, config: RateLimitConfig) -> None:
        """Add or update a rate limit configuration."""
        self._configs[config.name] = config
        logger.info(f"Added rate limit config: {config.name}")

    def remove_config(self, name: str) -> bool:
        """Remove a rate limit configuration."""
        if name in self._configs:
            del self._configs[name]
            return True
        return False

    def add_to_whitelist(self, identifier: str) -> None:
        """Add identifier to global whitelist."""
        if identifier not in self._global_whitelist:
            self._global_whitelist.append(identifier)

    def add_to_blacklist(self, identifier: str) -> None:
        """Add identifier to global blacklist."""
        if identifier not in self._global_blacklist:
            self._global_blacklist.append(identifier)

    def _get_window_key(
        self,
        config: RateLimitConfig,
        identifier: str,
    ) -> str:
        """Get the storage key for a rate limit window."""
        return f"{config.name}:{config.scope.value}:{identifier}"

    def _clean_window(
        self,
        window: SlidingWindow,
        window_seconds: int,
    ) -> None:
        """Remove expired entries from sliding window."""
        cutoff = time.time() - window_seconds
        window.requests = [ts for ts in window.requests if ts > cutoff]

    async def check(
        self,
        config_name: str,
        identifier: str,
        cost: int = 1,
    ) -> RateLimitResult:
        """
        Check rate limit without consuming.

        Args:
            config_name: Name of the rate limit config
            identifier: Identifier (IP, user ID, etc.)
            cost: Cost of the request (default 1)

        Returns:
            RateLimitResult with status
        """
        config = self._configs.get(config_name)
        if not config:
            config = self._configs["default"]

        # Check whitelist
        if identifier in self._global_whitelist or identifier in config.whitelist:
            return RateLimitResult(
                status=RateLimitStatus.ALLOWED,
                allowed=True,
                remaining=config.requests,
                limit=config.requests,
                reset_at=datetime.utcnow() + timedelta(seconds=config.window_seconds),
            )

        # Check blacklist
        if identifier in self._global_blacklist or identifier in config.blacklist:
            return RateLimitResult(
                status=RateLimitStatus.BLOCKED,
                allowed=False,
                remaining=0,
                limit=config.requests,
                reset_at=datetime.utcnow() + timedelta(hours=24),
                retry_after_seconds=86400,
            )

        key = self._get_window_key(config, identifier)
        window = self._windows[key]

        # Check if blocked
        now = time.time()
        if window.blocked_until and now < window.blocked_until:
            retry_after = int(window.blocked_until - now)
            return RateLimitResult(
                status=RateLimitStatus.BLOCKED,
                allowed=False,
                remaining=0,
                limit=config.requests,
                reset_at=datetime.fromtimestamp(window.blocked_until),
                retry_after_seconds=retry_after,
            )

        # Clean expired entries
        self._clean_window(window, config.window_seconds)

        # Calculate remaining
        current_count = len(window.requests)
        remaining = config.requests - current_count - cost + 1

        reset_at = datetime.utcnow() + timedelta(seconds=config.window_seconds)

        if remaining >= 0:
            return RateLimitResult(
                status=RateLimitStatus.ALLOWED,
                allowed=True,
                remaining=remaining,
                limit=config.requests,
                reset_at=reset_at,
            )
        else:
            # Check burst allowance
            if config.burst_requests:
                burst_cutoff = now - config.burst_window_seconds
                burst_count = sum(1 for ts in window.requests if ts > burst_cutoff)
                if burst_count < config.burst_requests:
                    return RateLimitResult(
                        status=RateLimitStatus.ALLOWED,
                        allowed=True,
                        remaining=0,
                        limit=config.requests,
                        reset_at=reset_at,
                    )

            # Calculate retry after
            if window.requests:
                oldest = min(window.requests)
                retry_after = int(oldest + config.window_seconds - now) + 1
            else:
                retry_after = config.window_seconds

            return RateLimitResult(
                status=RateLimitStatus.LIMITED,
                allowed=False,
                remaining=0,
                limit=config.requests,
                reset_at=reset_at,
                retry_after_seconds=max(1, retry_after),
            )

    async def consume(
        self,
        config_name: str,
        identifier: str,
        cost: int = 1,
    ) -> RateLimitResult:
        """
        Check and consume rate limit.

        Args:
            config_name: Name of the rate limit config
            identifier: Identifier (IP, user ID, etc.)
            cost: Cost of the request (default 1)

        Returns:
            RateLimitResult with status
        """
        result = await self.check(config_name, identifier, cost)

        if result.allowed:
            # Record the request
            config = self._configs.get(config_name, self._configs["default"])
            key = self._get_window_key(config, identifier)
            window = self._windows[key]

            now = time.time()
            for _ in range(cost):
                window.requests.append(now)

            result.remaining = max(0, result.remaining - 1)

        elif result.status == RateLimitStatus.LIMITED:
            # Track violation
            config = self._configs.get(config_name, self._configs["default"])
            key = self._get_window_key(config, identifier)
            window = self._windows[key]

            window.violations += 1
            logger.warning(f"Rate limit violation #{window.violations} for {identifier}")

            # Block if too many violations
            if window.violations >= config.block_after_violations:
                window.blocked_until = time.time() + config.block_duration_seconds
                result.status = RateLimitStatus.BLOCKED
                result.retry_after_seconds = config.block_duration_seconds
                logger.warning(f"Blocked {identifier} for {config.block_duration_seconds}s")

        return result

    def reset(self, config_name: str, identifier: str) -> None:
        """Reset rate limit for an identifier."""
        config = self._configs.get(config_name)
        if config:
            key = self._get_window_key(config, identifier)
            if key in self._windows:
                del self._windows[key]

    def unblock(self, config_name: str, identifier: str) -> bool:
        """Unblock a blocked identifier."""
        config = self._configs.get(config_name)
        if config:
            key = self._get_window_key(config, identifier)
            window = self._windows.get(key)
            if window and window.blocked_until:
                window.blocked_until = None
                window.violations = 0
                return True
        return False

    def get_stats(self, config_name: str, identifier: str) -> dict:
        """Get rate limit statistics for an identifier."""
        config = self._configs.get(config_name)
        if not config:
            return {}

        key = self._get_window_key(config, identifier)
        window = self._windows.get(key, SlidingWindow())

        self._clean_window(window, config.window_seconds)

        return {
            "config": config.name,
            "scope": config.scope.value,
            "identifier": identifier,
            "current_requests": len(window.requests),
            "limit": config.requests,
            "window_seconds": config.window_seconds,
            "violations": window.violations,
            "blocked": window.blocked_until is not None and time.time() < window.blocked_until,
            "blocked_until": (
                datetime.fromtimestamp(window.blocked_until).isoformat()
                if window.blocked_until else None
            ),
        }

    def cleanup_expired(self) -> int:
        """Clean up expired windows. Returns number of windows cleaned."""
        cleaned = 0
        now = time.time()
        keys_to_delete = []

        for key, window in self._windows.items():
            # Parse config name from key
            parts = key.split(":")
            if len(parts) >= 1:
                config = self._configs.get(parts[0])
                if config:
                    self._clean_window(window, config.window_seconds)
                    # Remove empty windows that aren't blocked
                    if not window.requests and (not window.blocked_until or window.blocked_until < now):
                        keys_to_delete.append(key)
                        cleaned += 1

        for key in keys_to_delete:
            del self._windows[key]

        return cleaned


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def rate_limit(
    config_name: str = "default",
    identifier: Optional[str] = None,
    ip: Optional[str] = None,
    user_id: Optional[str] = None,
) -> RateLimitResult:
    """
    Check and consume rate limit.

    Convenience function that auto-detects identifier.
    """
    limiter = get_rate_limiter()

    if identifier:
        ident = identifier
    elif user_id:
        ident = f"user:{user_id}"
    elif ip:
        ident = f"ip:{ip}"
    else:
        ident = "unknown"

    return await limiter.consume(config_name, ident)


def rate_limit_decorator(
    config_name: str = "default",
    get_identifier: Optional[Callable] = None,
):
    """
    Decorator for rate limiting async functions.

    Args:
        config_name: Name of the rate limit config
        get_identifier: Function to extract identifier from args
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Try to get identifier
            if get_identifier:
                identifier = get_identifier(*args, **kwargs)
            else:
                identifier = "unknown"

            result = await rate_limit(config_name, identifier=identifier)

            if not result.allowed:
                raise RateLimitExceeded(result)

            return await func(*args, **kwargs)
        return wrapper
    return decorator


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, result: RateLimitResult):
        self.result = result
        self.retry_after = result.retry_after_seconds
        super().__init__(f"Rate limit exceeded. Retry after {self.retry_after}s")
