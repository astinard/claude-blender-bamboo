"""User repository for user-related database operations."""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User, UserRole
from src.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        result = await self.session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_oauth(self, provider: str, oauth_id: str) -> Optional[User]:
        """Get user by OAuth provider and ID."""
        result = await self.session.execute(
            select(User).where(
                User.oauth_provider == provider,
                User.oauth_id == oauth_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_organization(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 100,
        role: Optional[UserRole] = None
    ) -> List[User]:
        """Get users in an organization."""
        query = select(User).where(User.organization_id == organization_id)

        if role:
            query = query.where(User.role == role)

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_user(
        self,
        email: str,
        name: str,
        organization_id: str,
        password_hash: Optional[str] = None,
        role: UserRole = UserRole.VIEWER,
        oauth_provider: Optional[str] = None,
        oauth_id: Optional[str] = None
    ) -> User:
        """Create a new user."""
        user = User(
            email=email.lower(),
            name=name,
            organization_id=organization_id,
            password_hash=password_hash,
            role=role,
            oauth_provider=oauth_provider,
            oauth_id=oauth_id
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp."""
        await self.update(user_id, last_login=datetime.utcnow())

    async def verify_user(self, user_id: str) -> None:
        """Mark user as verified."""
        await self.update(user_id, is_verified=True)

    async def deactivate_user(self, user_id: str) -> None:
        """Deactivate a user account."""
        await self.update(user_id, is_active=False)

    async def change_role(self, user_id: str, new_role: UserRole) -> Optional[User]:
        """Change user's role."""
        return await self.update(user_id, role=new_role)

    async def search(
        self,
        organization_id: str,
        query: str,
        limit: int = 10
    ) -> List[User]:
        """Search users by name or email."""
        search_pattern = f"%{query}%"
        result = await self.session.execute(
            select(User)
            .where(
                User.organization_id == organization_id,
                or_(
                    User.name.ilike(search_pattern),
                    User.email.ilike(search_pattern)
                )
            )
            .limit(limit)
        )
        return list(result.scalars().all())
