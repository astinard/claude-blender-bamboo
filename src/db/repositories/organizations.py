"""Organization repository for organization-related database operations."""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Organization, PlanTier
from src.db.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Repository for Organization entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Organization)

    async def get_by_name(self, name: str) -> Optional[Organization]:
        """Get organization by name."""
        result = await self.session.execute(
            select(Organization).where(Organization.name == name)
        )
        return result.scalar_one_or_none()

    async def create_organization(
        self,
        name: str,
        plan_tier: PlanTier = PlanTier.FREE,
        billing_email: Optional[str] = None
    ) -> Organization:
        """Create a new organization with tier-appropriate limits."""
        limits = self._get_tier_limits(plan_tier)

        org = Organization(
            name=name,
            plan_tier=plan_tier,
            billing_email=billing_email,
            **limits
        )
        self.session.add(org)
        await self.session.flush()
        await self.session.refresh(org)
        return org

    def _get_tier_limits(self, tier: PlanTier) -> dict:
        """Get resource limits for a plan tier."""
        limits = {
            PlanTier.FREE: {
                "max_printers": 1,
                "max_users": 1,
                "storage_limit_gb": 1,
                "ai_generations_limit": 5
            },
            PlanTier.PRO: {
                "max_printers": 3,
                "max_users": 3,
                "storage_limit_gb": 10,
                "ai_generations_limit": 50
            },
            PlanTier.TEAM: {
                "max_printers": 10,
                "max_users": 10,
                "storage_limit_gb": 50,
                "ai_generations_limit": 200
            },
            PlanTier.ENTERPRISE: {
                "max_printers": 1000,
                "max_users": 100,
                "storage_limit_gb": 500,
                "ai_generations_limit": 1000
            }
        }
        return limits.get(tier, limits[PlanTier.FREE])

    async def upgrade_tier(
        self,
        organization_id: str,
        new_tier: PlanTier,
        stripe_customer_id: Optional[str] = None
    ) -> Optional[Organization]:
        """Upgrade organization to a new tier."""
        limits = self._get_tier_limits(new_tier)
        update_data = {
            "plan_tier": new_tier,
            **limits
        }
        if stripe_customer_id:
            update_data["stripe_customer_id"] = stripe_customer_id

        return await self.update(organization_id, **update_data)

    async def get_by_tier(
        self,
        tier: PlanTier,
        skip: int = 0,
        limit: int = 100
    ) -> List[Organization]:
        """Get all organizations with a specific tier."""
        result = await self.session.execute(
            select(Organization)
            .where(Organization.plan_tier == tier)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
