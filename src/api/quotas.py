"""Quota management for enterprise resource control.

Provides per-organization and per-user quota enforcement for:
- API calls
- Storage usage
- Print jobs
- AI generations
- Team members
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List

from src.utils import get_logger

logger = get_logger("api.quotas")


class QuotaType(str, Enum):
    """Types of quotas."""
    API_CALLS = "api_calls"
    STORAGE_MB = "storage_mb"
    PRINT_JOBS = "print_jobs"
    AI_GENERATIONS = "ai_generations"
    TEAM_MEMBERS = "team_members"
    MODELS = "models"
    PROJECTS = "projects"
    CONCURRENT_PRINTS = "concurrent_prints"


class QuotaPeriod(str, Enum):
    """Quota reset periods."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    UNLIMITED = "unlimited"  # No reset, lifetime limit


@dataclass
class QuotaLimit:
    """A quota limit definition."""

    quota_type: QuotaType
    limit: int
    period: QuotaPeriod
    enabled: bool = True

    # Optional burst allowance
    burst_limit: Optional[int] = None  # Allow temporary exceeding
    burst_window_minutes: int = 5

    # Grace period before hard blocking
    grace_percent: float = 0.0  # Allow X% over limit with warning


@dataclass
class QuotaUsage:
    """Current quota usage."""

    quota_type: QuotaType
    current: int
    limit: int
    period: QuotaPeriod
    period_start: datetime
    period_end: datetime

    @property
    def remaining(self) -> int:
        """Get remaining quota."""
        return max(0, self.limit - self.current)

    @property
    def percent_used(self) -> float:
        """Get percentage of quota used."""
        if self.limit == 0:
            return 100.0
        return (self.current / self.limit) * 100

    @property
    def is_exceeded(self) -> bool:
        """Check if quota is exceeded."""
        return self.current >= self.limit

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "quota_type": self.quota_type.value,
            "current": self.current,
            "limit": self.limit,
            "remaining": self.remaining,
            "percent_used": round(self.percent_used, 2),
            "period": self.period.value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "is_exceeded": self.is_exceeded,
        }


@dataclass
class QuotaPlan:
    """Quota plan for a subscription tier."""

    name: str
    limits: Dict[QuotaType, QuotaLimit] = field(default_factory=dict)

    def get_limit(self, quota_type: QuotaType) -> Optional[QuotaLimit]:
        """Get limit for a quota type."""
        return self.limits.get(quota_type)


class QuotaExceededError(Exception):
    """Raised when quota is exceeded."""

    def __init__(
        self,
        quota_type: QuotaType,
        current: int,
        limit: int,
        reset_at: Optional[datetime] = None,
    ):
        self.quota_type = quota_type
        self.current = current
        self.limit = limit
        self.reset_at = reset_at
        message = f"Quota exceeded: {quota_type.value} ({current}/{limit})"
        if reset_at:
            message += f", resets at {reset_at.isoformat()}"
        super().__init__(message)


class QuotaManager:
    """
    Manages quotas for organizations and users.

    Features:
    - Per-organization and per-user quotas
    - Multiple quota types with different periods
    - Burst allowance for temporary spikes
    - Grace periods with warnings
    - Automatic period reset
    """

    # Default plans
    FREE_PLAN = QuotaPlan(
        name="free",
        limits={
            QuotaType.API_CALLS: QuotaLimit(QuotaType.API_CALLS, 1000, QuotaPeriod.DAILY),
            QuotaType.STORAGE_MB: QuotaLimit(QuotaType.STORAGE_MB, 500, QuotaPeriod.UNLIMITED),
            QuotaType.PRINT_JOBS: QuotaLimit(QuotaType.PRINT_JOBS, 50, QuotaPeriod.MONTHLY),
            QuotaType.AI_GENERATIONS: QuotaLimit(QuotaType.AI_GENERATIONS, 10, QuotaPeriod.MONTHLY),
            QuotaType.TEAM_MEMBERS: QuotaLimit(QuotaType.TEAM_MEMBERS, 2, QuotaPeriod.UNLIMITED),
            QuotaType.MODELS: QuotaLimit(QuotaType.MODELS, 25, QuotaPeriod.UNLIMITED),
            QuotaType.PROJECTS: QuotaLimit(QuotaType.PROJECTS, 5, QuotaPeriod.UNLIMITED),
            QuotaType.CONCURRENT_PRINTS: QuotaLimit(QuotaType.CONCURRENT_PRINTS, 1, QuotaPeriod.UNLIMITED),
        },
    )

    PRO_PLAN = QuotaPlan(
        name="pro",
        limits={
            QuotaType.API_CALLS: QuotaLimit(QuotaType.API_CALLS, 10000, QuotaPeriod.DAILY),
            QuotaType.STORAGE_MB: QuotaLimit(QuotaType.STORAGE_MB, 10000, QuotaPeriod.UNLIMITED),
            QuotaType.PRINT_JOBS: QuotaLimit(QuotaType.PRINT_JOBS, 500, QuotaPeriod.MONTHLY),
            QuotaType.AI_GENERATIONS: QuotaLimit(QuotaType.AI_GENERATIONS, 100, QuotaPeriod.MONTHLY),
            QuotaType.TEAM_MEMBERS: QuotaLimit(QuotaType.TEAM_MEMBERS, 10, QuotaPeriod.UNLIMITED),
            QuotaType.MODELS: QuotaLimit(QuotaType.MODELS, 500, QuotaPeriod.UNLIMITED),
            QuotaType.PROJECTS: QuotaLimit(QuotaType.PROJECTS, 50, QuotaPeriod.UNLIMITED),
            QuotaType.CONCURRENT_PRINTS: QuotaLimit(QuotaType.CONCURRENT_PRINTS, 3, QuotaPeriod.UNLIMITED),
        },
    )

    TEAM_PLAN = QuotaPlan(
        name="team",
        limits={
            QuotaType.API_CALLS: QuotaLimit(QuotaType.API_CALLS, 50000, QuotaPeriod.DAILY),
            QuotaType.STORAGE_MB: QuotaLimit(QuotaType.STORAGE_MB, 100000, QuotaPeriod.UNLIMITED),
            QuotaType.PRINT_JOBS: QuotaLimit(QuotaType.PRINT_JOBS, 2000, QuotaPeriod.MONTHLY),
            QuotaType.AI_GENERATIONS: QuotaLimit(QuotaType.AI_GENERATIONS, 500, QuotaPeriod.MONTHLY),
            QuotaType.TEAM_MEMBERS: QuotaLimit(QuotaType.TEAM_MEMBERS, 50, QuotaPeriod.UNLIMITED),
            QuotaType.MODELS: QuotaLimit(QuotaType.MODELS, 5000, QuotaPeriod.UNLIMITED),
            QuotaType.PROJECTS: QuotaLimit(QuotaType.PROJECTS, 500, QuotaPeriod.UNLIMITED),
            QuotaType.CONCURRENT_PRINTS: QuotaLimit(QuotaType.CONCURRENT_PRINTS, 10, QuotaPeriod.UNLIMITED),
        },
    )

    ENTERPRISE_PLAN = QuotaPlan(
        name="enterprise",
        limits={
            QuotaType.API_CALLS: QuotaLimit(QuotaType.API_CALLS, 500000, QuotaPeriod.DAILY),
            QuotaType.STORAGE_MB: QuotaLimit(QuotaType.STORAGE_MB, 1000000, QuotaPeriod.UNLIMITED),
            QuotaType.PRINT_JOBS: QuotaLimit(QuotaType.PRINT_JOBS, 10000, QuotaPeriod.MONTHLY),
            QuotaType.AI_GENERATIONS: QuotaLimit(QuotaType.AI_GENERATIONS, 5000, QuotaPeriod.MONTHLY),
            QuotaType.TEAM_MEMBERS: QuotaLimit(QuotaType.TEAM_MEMBERS, 500, QuotaPeriod.UNLIMITED),
            QuotaType.MODELS: QuotaLimit(QuotaType.MODELS, 50000, QuotaPeriod.UNLIMITED),
            QuotaType.PROJECTS: QuotaLimit(QuotaType.PROJECTS, 5000, QuotaPeriod.UNLIMITED),
            QuotaType.CONCURRENT_PRINTS: QuotaLimit(QuotaType.CONCURRENT_PRINTS, 100, QuotaPeriod.UNLIMITED),
        },
    )

    PLANS = {
        "free": FREE_PLAN,
        "pro": PRO_PLAN,
        "team": TEAM_PLAN,
        "enterprise": ENTERPRISE_PLAN,
    }

    def __init__(self):
        # In-memory storage (use Redis in production)
        self._usage: Dict[str, Dict[QuotaType, int]] = {}
        self._period_starts: Dict[str, Dict[QuotaType, datetime]] = {}
        self._org_plans: Dict[str, str] = {}
        self._custom_limits: Dict[str, Dict[QuotaType, QuotaLimit]] = {}

    def set_organization_plan(self, organization_id: str, plan_name: str) -> None:
        """Set the quota plan for an organization."""
        if plan_name not in self.PLANS:
            raise ValueError(f"Unknown plan: {plan_name}")
        self._org_plans[organization_id] = plan_name
        logger.info(f"Set plan {plan_name} for org {organization_id}")

    def set_custom_limit(
        self,
        organization_id: str,
        quota_type: QuotaType,
        limit: int,
        period: QuotaPeriod = QuotaPeriod.MONTHLY,
    ) -> None:
        """Set a custom limit for an organization."""
        if organization_id not in self._custom_limits:
            self._custom_limits[organization_id] = {}

        self._custom_limits[organization_id][quota_type] = QuotaLimit(
            quota_type=quota_type,
            limit=limit,
            period=period,
        )
        logger.info(f"Set custom limit {quota_type.value}={limit} for org {organization_id}")

    def get_plan(self, organization_id: str) -> QuotaPlan:
        """Get the quota plan for an organization."""
        plan_name = self._org_plans.get(organization_id, "free")
        return self.PLANS[plan_name]

    def get_limit(self, organization_id: str, quota_type: QuotaType) -> QuotaLimit:
        """Get the limit for a specific quota type."""
        # Check custom limits first
        if organization_id in self._custom_limits:
            if quota_type in self._custom_limits[organization_id]:
                return self._custom_limits[organization_id][quota_type]

        # Fall back to plan limits
        plan = self.get_plan(organization_id)
        limit = plan.get_limit(quota_type)

        if not limit:
            # Default to unlimited
            return QuotaLimit(
                quota_type=quota_type,
                limit=999999999,
                period=QuotaPeriod.UNLIMITED,
                enabled=False,
            )

        return limit

    def _get_period_bounds(self, period: QuotaPeriod) -> tuple[datetime, datetime]:
        """Get the start and end of the current period."""
        now = datetime.utcnow()

        if period == QuotaPeriod.HOURLY:
            start = now.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
        elif period == QuotaPeriod.DAILY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == QuotaPeriod.WEEKLY:
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(weeks=1)
        elif period == QuotaPeriod.MONTHLY:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Next month
            if now.month == 12:
                end = start.replace(year=now.year + 1, month=1)
            else:
                end = start.replace(month=now.month + 1)
        else:  # UNLIMITED
            start = datetime(2000, 1, 1)
            end = datetime(2100, 1, 1)

        return start, end

    def _get_usage_key(self, organization_id: str, quota_type: QuotaType) -> str:
        """Get the usage key for an org/quota combination."""
        return f"{organization_id}:{quota_type.value}"

    def _should_reset(
        self,
        organization_id: str,
        quota_type: QuotaType,
        period: QuotaPeriod,
    ) -> bool:
        """Check if the quota period should reset."""
        key = self._get_usage_key(organization_id, quota_type)

        if key not in self._period_starts:
            return True

        period_start = self._period_starts.get(key, {}).get(quota_type)
        if not period_start:
            return True

        current_start, _ = self._get_period_bounds(period)
        return period_start < current_start

    def get_usage(self, organization_id: str, quota_type: QuotaType) -> QuotaUsage:
        """Get current usage for a quota type."""
        limit = self.get_limit(organization_id, quota_type)
        key = self._get_usage_key(organization_id, quota_type)

        # Check if period should reset
        if self._should_reset(organization_id, quota_type, limit.period):
            self._usage[key] = {quota_type: 0}
            if key not in self._period_starts:
                self._period_starts[key] = {}
            self._period_starts[key][quota_type] = datetime.utcnow()

        current = self._usage.get(key, {}).get(quota_type, 0)
        period_start, period_end = self._get_period_bounds(limit.period)

        return QuotaUsage(
            quota_type=quota_type,
            current=current,
            limit=limit.limit,
            period=limit.period,
            period_start=period_start,
            period_end=period_end,
        )

    def get_all_usage(self, organization_id: str) -> List[QuotaUsage]:
        """Get usage for all quota types."""
        return [
            self.get_usage(organization_id, qt)
            for qt in QuotaType
        ]

    async def check_quota(
        self,
        organization_id: str,
        quota_type: QuotaType,
        amount: int = 1,
    ) -> bool:
        """
        Check if quota allows the operation.

        Args:
            organization_id: Organization ID
            quota_type: Type of quota to check
            amount: Amount to consume

        Returns:
            True if quota is available
        """
        usage = self.get_usage(organization_id, quota_type)
        return usage.current + amount <= usage.limit

    async def consume(
        self,
        organization_id: str,
        quota_type: QuotaType,
        amount: int = 1,
        raise_on_exceed: bool = True,
    ) -> QuotaUsage:
        """
        Consume quota.

        Args:
            organization_id: Organization ID
            quota_type: Type of quota to consume
            amount: Amount to consume
            raise_on_exceed: Raise exception if quota exceeded

        Returns:
            Updated quota usage

        Raises:
            QuotaExceededError: If quota is exceeded and raise_on_exceed is True
        """
        usage = self.get_usage(organization_id, quota_type)

        if usage.current + amount > usage.limit:
            if raise_on_exceed:
                raise QuotaExceededError(
                    quota_type=quota_type,
                    current=usage.current,
                    limit=usage.limit,
                    reset_at=usage.period_end,
                )
            return usage

        # Update usage
        key = self._get_usage_key(organization_id, quota_type)
        if key not in self._usage:
            self._usage[key] = {}
        self._usage[key][quota_type] = usage.current + amount

        logger.debug(f"Consumed {amount} {quota_type.value} for org {organization_id}")

        return self.get_usage(organization_id, quota_type)

    async def release(
        self,
        organization_id: str,
        quota_type: QuotaType,
        amount: int = 1,
    ) -> QuotaUsage:
        """Release consumed quota (for cancellations, etc.)."""
        key = self._get_usage_key(organization_id, quota_type)

        if key in self._usage and quota_type in self._usage[key]:
            self._usage[key][quota_type] = max(0, self._usage[key][quota_type] - amount)

        return self.get_usage(organization_id, quota_type)

    def get_quota_status(self, organization_id: str) -> dict:
        """Get complete quota status for an organization."""
        plan = self.get_plan(organization_id)
        usages = self.get_all_usage(organization_id)

        return {
            "plan": plan.name,
            "quotas": [u.to_dict() for u in usages],
            "warnings": [
                u.to_dict() for u in usages
                if u.percent_used >= 80 and not u.is_exceeded
            ],
            "exceeded": [
                u.to_dict() for u in usages
                if u.is_exceeded
            ],
        }


# Global quota manager instance
_quota_manager: Optional[QuotaManager] = None


def get_quota_manager() -> QuotaManager:
    """Get the global quota manager instance."""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = QuotaManager()
    return _quota_manager


async def check_and_consume(
    organization_id: str,
    quota_type: QuotaType,
    amount: int = 1,
) -> QuotaUsage:
    """
    Check and consume quota in one operation.

    Convenience function for common use case.
    """
    manager = get_quota_manager()
    return await manager.consume(organization_id, quota_type, amount)
