"""User management module for Claude Fab Lab.

Handles user invitations, authentication, organization management,
and billing integration.
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User, Organization, UserRole, PlanTier
from src.db.repositories.users import UserRepository
from src.db.repositories.organizations import OrganizationRepository
from src.auth.password import hash_password, verify_password
from src.auth.jwt import create_access_token, create_refresh_token
from src.utils import get_logger

logger = get_logger("users")


@dataclass
class AuthTokens:
    """Authentication token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes


@dataclass
class InvitationResult:
    """Result of creating an invitation."""
    invitation_id: str
    email: str
    invite_url: str
    expires_at: datetime


class UserExistsError(Exception):
    """Raised when email is already registered."""
    pass


class InvalidCredentialsError(Exception):
    """Raised when login credentials are invalid."""
    pass


class InvitationExpiredError(Exception):
    """Raised when invitation has expired."""
    pass


class QuotaExceededError(Exception):
    """Raised when organization quota is exceeded."""
    pass


class UserService:
    """Service for user management operations."""

    INVITE_EXPIRY_DAYS = 7
    BASE_URL = os.getenv("BASE_URL", "http://localhost:9880")

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.org_repo = OrganizationRepository(db)

    # =========================================================================
    # Authentication
    # =========================================================================

    async def register(
        self,
        email: str,
        password: str,
        name: str,
        organization_name: Optional[str] = None
    ) -> tuple[User, Organization, AuthTokens]:
        """Register a new user and create their organization.

        Args:
            email: User's email address
            password: User's password (will be hashed)
            name: User's display name
            organization_name: Name for the new organization

        Returns:
            Tuple of (user, organization, auth_tokens)

        Raises:
            UserExistsError: If email is already registered
        """
        # Check if email exists
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise UserExistsError(f"Email {email} is already registered")

        # Create organization
        org_name = organization_name or f"{name}'s Organization"
        org = await self.org_repo.create_organization(
            name=org_name,
            plan_tier=PlanTier.FREE
        )

        # Create user as admin of the org
        user = await self.user_repo.create_user(
            email=email,
            name=name,
            organization_id=org.id,
            password_hash=hash_password(password),
            role=UserRole.ADMIN
        )

        # Verify user immediately (no email verification for self-registration)
        await self.user_repo.verify_user(user.id)

        await self.db.commit()

        # Generate tokens
        tokens = self._create_tokens(user)

        logger.info(f"New user registered: {email} (org: {org.name})")
        return user, org, tokens

    async def login(self, email: str, password: str) -> tuple[User, AuthTokens]:
        """Authenticate user and return tokens.

        Args:
            email: User's email
            password: User's password

        Returns:
            Tuple of (user, auth_tokens)

        Raises:
            InvalidCredentialsError: If credentials are invalid
        """
        user = await self.user_repo.get_by_email(email)

        if not user or not user.is_active:
            raise InvalidCredentialsError("Invalid email or password")

        if not user.password_hash or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password")

        # Update last login
        await self.user_repo.update_last_login(user.id)
        await self.db.commit()

        tokens = self._create_tokens(user)

        logger.info(f"User logged in: {email}")
        return user, tokens

    async def login_oauth(
        self,
        provider: str,
        oauth_id: str,
        email: str,
        name: str
    ) -> tuple[User, AuthTokens]:
        """Login or register via OAuth provider.

        Args:
            provider: OAuth provider name (google, github, etc.)
            oauth_id: User ID from the OAuth provider
            email: User's email from OAuth
            name: User's name from OAuth

        Returns:
            Tuple of (user, auth_tokens)
        """
        # Check for existing OAuth user
        user = await self.user_repo.get_by_oauth(provider, oauth_id)

        if user:
            # Existing OAuth user - update last login
            await self.user_repo.update_last_login(user.id)
            await self.db.commit()
        else:
            # Check if email exists (link accounts)
            user = await self.user_repo.get_by_email(email)

            if user:
                # Link OAuth to existing account
                await self.user_repo.update(
                    user.id,
                    oauth_provider=provider,
                    oauth_id=oauth_id
                )
            else:
                # New user - create account and org
                org = await self.org_repo.create_organization(
                    name=f"{name}'s Organization",
                    plan_tier=PlanTier.FREE
                )

                user = await self.user_repo.create_user(
                    email=email,
                    name=name,
                    organization_id=org.id,
                    role=UserRole.ADMIN,
                    oauth_provider=provider,
                    oauth_id=oauth_id
                )
                await self.user_repo.verify_user(user.id)

            await self.db.commit()

        tokens = self._create_tokens(user)
        logger.info(f"OAuth login: {email} via {provider}")
        return user, tokens

    def _create_tokens(self, user: User) -> AuthTokens:
        """Create access and refresh tokens for user."""
        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            org_id=user.organization_id,
            role=user.role.value
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            email=user.email,
            org_id=user.organization_id,
            role=user.role.value
        )
        return AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token
        )

    # =========================================================================
    # Invitations
    # =========================================================================

    async def invite_user(
        self,
        inviter: User,
        email: str,
        name: str,
        role: UserRole = UserRole.VIEWER
    ) -> InvitationResult:
        """Invite a new user to the organization.

        Args:
            inviter: User sending the invitation
            email: Email to invite
            name: Name for the new user
            role: Role to assign

        Returns:
            InvitationResult with invite URL

        Raises:
            UserExistsError: If email is already registered
            QuotaExceededError: If org has reached user limit
        """
        # Check email doesn't exist
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise UserExistsError(f"Email {email} is already registered")

        # Check org quota
        org = await self.org_repo.get_by_id(inviter.organization_id)
        user_count = await self.user_repo.count(organization_id=org.id)
        if user_count >= org.max_users:
            raise QuotaExceededError(
                f"Organization has reached maximum users ({org.max_users}). "
                "Upgrade plan to add more users."
            )

        # Generate invite token
        invite_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=self.INVITE_EXPIRY_DAYS)

        # Create user with pending status
        user = await self.user_repo.create_user(
            email=email,
            name=name,
            organization_id=org.id,
            role=role
        )

        # Store invite token (in a real app, use a separate invitations table)
        # For now, we'll use a simple approach with the password hash field
        await self.user_repo.update(
            user.id,
            password_hash=f"INVITE:{invite_token}:{expires_at.isoformat()}"
        )

        await self.db.commit()

        invite_url = f"{self.BASE_URL}/invite/{invite_token}"

        logger.info(f"User {inviter.email} invited {email} to org {org.name}")

        return InvitationResult(
            invitation_id=user.id,
            email=email,
            invite_url=invite_url,
            expires_at=expires_at
        )

    async def accept_invitation(
        self,
        token: str,
        password: str
    ) -> tuple[User, AuthTokens]:
        """Accept an invitation and set password.

        Args:
            token: Invitation token
            password: New password for the user

        Returns:
            Tuple of (user, auth_tokens)

        Raises:
            InvitationExpiredError: If invitation has expired or is invalid
        """
        # Find user with this invite token
        # In production, use a proper invitations table
        users = await self.user_repo.get_all(limit=1000)  # Not ideal, use proper query

        target_user = None
        for user in users:
            if user.password_hash and user.password_hash.startswith("INVITE:"):
                parts = user.password_hash.split(":")
                if len(parts) == 3 and parts[1] == token:
                    expires_at = datetime.fromisoformat(parts[2])
                    if datetime.utcnow() < expires_at:
                        target_user = user
                    break

        if not target_user:
            raise InvitationExpiredError("Invalid or expired invitation")

        # Set password and activate
        await self.user_repo.update(
            target_user.id,
            password_hash=hash_password(password),
            is_verified=True
        )
        await self.db.commit()

        # Refresh user data
        user = await self.user_repo.get_by_id(target_user.id)
        tokens = self._create_tokens(user)

        logger.info(f"Invitation accepted: {user.email}")
        return user, tokens

    # =========================================================================
    # User Management
    # =========================================================================

    async def get_organization_users(
        self,
        organization_id: str,
        role: Optional[UserRole] = None
    ) -> List[User]:
        """Get all users in an organization."""
        return await self.user_repo.get_by_organization(
            organization_id,
            role=role
        )

    async def change_user_role(
        self,
        user_id: str,
        new_role: UserRole,
        changed_by: User
    ) -> User:
        """Change a user's role.

        Args:
            user_id: ID of user to change
            new_role: New role to assign
            changed_by: User making the change (must be admin)

        Returns:
            Updated user
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user or user.organization_id != changed_by.organization_id:
            raise ValueError("User not found")

        # Prevent removing last admin
        if user.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
            admins = await self.user_repo.get_by_organization(
                user.organization_id,
                role=UserRole.ADMIN
            )
            if len(admins) <= 1:
                raise ValueError("Cannot remove the last admin")

        user = await self.user_repo.change_role(user_id, new_role)
        await self.db.commit()

        logger.info(f"User {user.email} role changed to {new_role.value} by {changed_by.email}")
        return user

    async def deactivate_user(
        self,
        user_id: str,
        deactivated_by: User
    ) -> None:
        """Deactivate a user account."""
        if user_id == deactivated_by.id:
            raise ValueError("Cannot deactivate yourself")

        user = await self.user_repo.get_by_id(user_id)
        if not user or user.organization_id != deactivated_by.organization_id:
            raise ValueError("User not found")

        await self.user_repo.deactivate_user(user_id)
        await self.db.commit()

        logger.info(f"User {user.email} deactivated by {deactivated_by.email}")

    # =========================================================================
    # Organization Management
    # =========================================================================

    async def get_organization(self, org_id: str) -> Optional[Organization]:
        """Get organization by ID."""
        return await self.org_repo.get_by_id(org_id)

    async def update_organization(
        self,
        org_id: str,
        name: Optional[str] = None,
        billing_email: Optional[str] = None
    ) -> Organization:
        """Update organization details."""
        updates = {}
        if name:
            updates["name"] = name
        if billing_email:
            updates["billing_email"] = billing_email

        org = await self.org_repo.update(org_id, **updates)
        await self.db.commit()
        return org

    async def upgrade_organization(
        self,
        org_id: str,
        new_tier: PlanTier,
        stripe_customer_id: Optional[str] = None
    ) -> Organization:
        """Upgrade organization to a new plan tier."""
        org = await self.org_repo.upgrade_tier(org_id, new_tier, stripe_customer_id)
        await self.db.commit()

        logger.info(f"Organization {org.name} upgraded to {new_tier.value}")
        return org
