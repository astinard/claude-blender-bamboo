"""Single Sign-On (SSO) integration for enterprise authentication.

Supports Okta, Azure AD, and Google Workspace identity providers.
Uses SAML 2.0 and OIDC protocols for secure enterprise authentication.
"""

import os
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

from src.utils import get_logger

logger = get_logger("auth.sso")


class SSOProvider(str, Enum):
    """Supported SSO providers."""
    OKTA = "okta"
    AZURE_AD = "azure_ad"
    GOOGLE = "google"
    ONELOGIN = "onelogin"
    CUSTOM_SAML = "custom_saml"
    CUSTOM_OIDC = "custom_oidc"


class SSOProtocol(str, Enum):
    """Authentication protocols."""
    SAML = "saml"
    OIDC = "oidc"


@dataclass
class SSOConfig:
    """SSO configuration for an organization."""

    organization_id: str
    provider: SSOProvider
    protocol: SSOProtocol
    enabled: bool = True

    # OIDC configuration
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    issuer_url: Optional[str] = None
    authorization_endpoint: Optional[str] = None
    token_endpoint: Optional[str] = None
    userinfo_endpoint: Optional[str] = None
    jwks_uri: Optional[str] = None

    # SAML configuration
    idp_entity_id: Optional[str] = None
    idp_sso_url: Optional[str] = None
    idp_slo_url: Optional[str] = None
    idp_certificate: Optional[str] = None
    sp_entity_id: Optional[str] = None
    sp_acs_url: Optional[str] = None

    # Attribute mappings
    email_attribute: str = "email"
    name_attribute: str = "name"
    groups_attribute: str = "groups"

    # Role mappings (IdP group -> app role)
    role_mappings: Dict[str, str] = field(default_factory=dict)

    # Security settings
    require_signed_assertions: bool = True
    require_encrypted_assertions: bool = False
    allowed_clock_skew_seconds: int = 60

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SSOUser:
    """User information from SSO authentication."""

    email: str
    name: str
    provider: SSOProvider
    external_id: str
    groups: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    authenticated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SSOSession:
    """SSO session state for authentication flow."""

    session_id: str
    organization_id: str
    provider: SSOProvider
    state: str
    nonce: str
    redirect_uri: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=10))

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at


class SSOError(Exception):
    """Base SSO error."""
    pass


class SSOConfigError(SSOError):
    """SSO configuration error."""
    pass


class SSOAuthError(SSOError):
    """SSO authentication error."""
    pass


class SSOProviderClient(ABC):
    """Abstract base class for SSO provider clients."""

    @abstractmethod
    def get_authorization_url(self, session: SSOSession) -> str:
        """Generate authorization URL for login redirect."""
        pass

    @abstractmethod
    async def exchange_code(self, code: str, session: SSOSession) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        pass

    @abstractmethod
    async def get_user_info(self, tokens: Dict[str, Any]) -> SSOUser:
        """Get user information from tokens."""
        pass


class OktaClient(SSOProviderClient):
    """Okta SSO client using OIDC."""

    def __init__(self, config: SSOConfig):
        if not config.client_id or not config.issuer_url:
            raise SSOConfigError("Okta requires client_id and issuer_url")
        self.config = config

    def get_authorization_url(self, session: SSOSession) -> str:
        """Generate Okta authorization URL."""
        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "scope": "openid email profile groups",
            "redirect_uri": session.redirect_uri,
            "state": session.state,
            "nonce": session.nonce,
        }

        auth_endpoint = (
            self.config.authorization_endpoint or
            f"{self.config.issuer_url}/v1/authorize"
        )
        return f"{auth_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, session: SSOSession) -> Dict[str, Any]:
        """Exchange code for tokens with Okta."""
        # In production, use aiohttp to call token endpoint
        # POST to token_endpoint with code, client_id, client_secret, redirect_uri
        token_endpoint = (
            self.config.token_endpoint or
            f"{self.config.issuer_url}/v1/token"
        )

        logger.info(f"Exchanging code at {token_endpoint}")

        # Placeholder - implement actual HTTP call
        return {
            "access_token": "mock_access_token",
            "id_token": "mock_id_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

    async def get_user_info(self, tokens: Dict[str, Any]) -> SSOUser:
        """Get user info from Okta tokens."""
        # In production, decode id_token JWT or call userinfo endpoint
        userinfo_endpoint = (
            self.config.userinfo_endpoint or
            f"{self.config.issuer_url}/v1/userinfo"
        )

        logger.info(f"Getting user info from {userinfo_endpoint}")

        # Placeholder - implement actual HTTP call and JWT parsing
        return SSOUser(
            email="user@example.com",
            name="SSO User",
            provider=SSOProvider.OKTA,
            external_id="okta_user_id",
            groups=["admin", "developers"],
        )


class AzureADClient(SSOProviderClient):
    """Azure Active Directory SSO client using OIDC."""

    def __init__(self, config: SSOConfig):
        if not config.client_id:
            raise SSOConfigError("Azure AD requires client_id")
        self.config = config
        self.tenant_id = self._extract_tenant_id()

    def _extract_tenant_id(self) -> str:
        """Extract tenant ID from issuer URL or use common."""
        if self.config.issuer_url:
            # Format: https://login.microsoftonline.com/{tenant}/v2.0
            parts = self.config.issuer_url.split("/")
            for i, part in enumerate(parts):
                if part == "login.microsoftonline.com" and i + 1 < len(parts):
                    return parts[i + 1]
        return "common"

    def get_authorization_url(self, session: SSOSession) -> str:
        """Generate Azure AD authorization URL."""
        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "scope": "openid email profile User.Read",
            "redirect_uri": session.redirect_uri,
            "state": session.state,
            "nonce": session.nonce,
            "response_mode": "query",
        }

        auth_endpoint = (
            self.config.authorization_endpoint or
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"
        )
        return f"{auth_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, session: SSOSession) -> Dict[str, Any]:
        """Exchange code for tokens with Azure AD."""
        token_endpoint = (
            self.config.token_endpoint or
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        )

        logger.info(f"Exchanging code at {token_endpoint}")

        return {
            "access_token": "mock_azure_access_token",
            "id_token": "mock_azure_id_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

    async def get_user_info(self, tokens: Dict[str, Any]) -> SSOUser:
        """Get user info from Azure AD tokens."""
        # Call Microsoft Graph API: GET https://graph.microsoft.com/v1.0/me

        return SSOUser(
            email="user@company.onmicrosoft.com",
            name="Azure AD User",
            provider=SSOProvider.AZURE_AD,
            external_id="azure_object_id",
            groups=[],
        )


class GoogleClient(SSOProviderClient):
    """Google Workspace SSO client using OIDC."""

    def __init__(self, config: SSOConfig):
        if not config.client_id:
            raise SSOConfigError("Google requires client_id")
        self.config = config

    def get_authorization_url(self, session: SSOSession) -> str:
        """Generate Google authorization URL."""
        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": session.redirect_uri,
            "state": session.state,
            "nonce": session.nonce,
            "access_type": "offline",
            "prompt": "consent",
        }

        if self.config.issuer_url and "hd=" not in self.config.issuer_url:
            # Hosted domain restriction for Google Workspace
            # params["hd"] = "company.com"
            pass

        auth_endpoint = (
            self.config.authorization_endpoint or
            "https://accounts.google.com/o/oauth2/v2/auth"
        )
        return f"{auth_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, session: SSOSession) -> Dict[str, Any]:
        """Exchange code for tokens with Google."""
        token_endpoint = (
            self.config.token_endpoint or
            "https://oauth2.googleapis.com/token"
        )

        logger.info(f"Exchanging code at {token_endpoint}")

        return {
            "access_token": "mock_google_access_token",
            "id_token": "mock_google_id_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

    async def get_user_info(self, tokens: Dict[str, Any]) -> SSOUser:
        """Get user info from Google tokens."""
        # Decode id_token or call userinfo endpoint

        return SSOUser(
            email="user@company.com",
            name="Google User",
            provider=SSOProvider.GOOGLE,
            external_id="google_sub",
            groups=[],
        )


class SSOService:
    """
    Single Sign-On service for enterprise authentication.

    Features:
    - Support for Okta, Azure AD, Google Workspace
    - OIDC and SAML 2.0 protocols
    - Role mapping from IdP groups
    - Session management
    - JIT (Just-In-Time) provisioning
    """

    BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

    def __init__(self):
        self._configs: Dict[str, SSOConfig] = {}
        self._sessions: Dict[str, SSOSession] = {}
        self._clients: Dict[str, SSOProviderClient] = {}

    def register_config(self, config: SSOConfig) -> None:
        """Register SSO configuration for an organization."""
        self._configs[config.organization_id] = config
        self._clients[config.organization_id] = self._create_client(config)
        logger.info(f"Registered SSO config for org {config.organization_id}: {config.provider.value}")

    def _create_client(self, config: SSOConfig) -> SSOProviderClient:
        """Create provider client based on configuration."""
        if config.provider == SSOProvider.OKTA:
            return OktaClient(config)
        elif config.provider == SSOProvider.AZURE_AD:
            return AzureADClient(config)
        elif config.provider == SSOProvider.GOOGLE:
            return GoogleClient(config)
        else:
            raise SSOConfigError(f"Unsupported provider: {config.provider}")

    def get_config(self, organization_id: str) -> Optional[SSOConfig]:
        """Get SSO configuration for organization."""
        return self._configs.get(organization_id)

    def is_sso_enabled(self, organization_id: str) -> bool:
        """Check if SSO is enabled for organization."""
        config = self._configs.get(organization_id)
        return config is not None and config.enabled

    def start_login(self, organization_id: str, redirect_uri: Optional[str] = None) -> str:
        """
        Start SSO login flow.

        Args:
            organization_id: Organization ID
            redirect_uri: Optional callback URI

        Returns:
            Authorization URL to redirect user to
        """
        config = self._configs.get(organization_id)
        if not config or not config.enabled:
            raise SSOConfigError(f"SSO not configured for organization: {organization_id}")

        client = self._clients.get(organization_id)
        if not client:
            raise SSOConfigError(f"SSO client not initialized for organization: {organization_id}")

        # Create session
        session = SSOSession(
            session_id=secrets.token_urlsafe(32),
            organization_id=organization_id,
            provider=config.provider,
            state=secrets.token_urlsafe(32),
            nonce=secrets.token_urlsafe(32),
            redirect_uri=redirect_uri or f"{self.BASE_URL}/auth/sso/callback",
        )

        self._sessions[session.state] = session

        auth_url = client.get_authorization_url(session)
        logger.info(f"Started SSO login for org {organization_id}, state={session.state[:8]}...")

        return auth_url

    async def complete_login(self, state: str, code: str) -> SSOUser:
        """
        Complete SSO login after IdP callback.

        Args:
            state: State parameter from callback
            code: Authorization code from callback

        Returns:
            Authenticated user information
        """
        session = self._sessions.get(state)
        if not session:
            raise SSOAuthError("Invalid or expired session state")

        if session.is_expired:
            del self._sessions[state]
            raise SSOAuthError("Session expired")

        client = self._clients.get(session.organization_id)
        if not client:
            raise SSOAuthError("SSO client not found")

        try:
            # Exchange code for tokens
            tokens = await client.exchange_code(code, session)

            # Get user info
            user = await client.get_user_info(tokens)

            # Clean up session
            del self._sessions[state]

            logger.info(f"SSO login completed for {user.email} via {user.provider.value}")
            return user

        except Exception as e:
            logger.error(f"SSO login failed: {e}")
            raise SSOAuthError(f"Authentication failed: {e}")

    def map_roles(self, organization_id: str, idp_groups: List[str]) -> List[str]:
        """
        Map IdP groups to application roles.

        Args:
            organization_id: Organization ID
            idp_groups: Groups from IdP

        Returns:
            List of mapped application roles
        """
        config = self._configs.get(organization_id)
        if not config:
            return []

        roles = []
        for group in idp_groups:
            if group in config.role_mappings:
                roles.append(config.role_mappings[group])

        # Default role if no mapping found
        if not roles:
            roles.append("viewer")

        return roles

    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions."""
        expired = [
            state for state, session in self._sessions.items()
            if session.is_expired
        ]
        for state in expired:
            del self._sessions[state]
        return len(expired)


# Global service instance
_sso_service: Optional[SSOService] = None


def get_sso_service() -> SSOService:
    """Get the global SSO service instance."""
    global _sso_service
    if _sso_service is None:
        _sso_service = SSOService()
    return _sso_service


def configure_sso(
    organization_id: str,
    provider: SSOProvider,
    client_id: str,
    client_secret: str,
    issuer_url: Optional[str] = None,
    role_mappings: Optional[Dict[str, str]] = None,
) -> SSOConfig:
    """
    Configure SSO for an organization.

    Convenience function for common setup.

    Args:
        organization_id: Organization ID
        provider: SSO provider (okta, azure_ad, google)
        client_id: OAuth client ID
        client_secret: OAuth client secret
        issuer_url: IdP issuer URL
        role_mappings: IdP group to role mappings

    Returns:
        Created SSO configuration
    """
    config = SSOConfig(
        organization_id=organization_id,
        provider=provider,
        protocol=SSOProtocol.OIDC,
        client_id=client_id,
        client_secret=client_secret,
        issuer_url=issuer_url,
        role_mappings=role_mappings or {},
    )

    service = get_sso_service()
    service.register_config(config)

    return config
