"""Model publishing to 3D marketplaces.

Enables publishing models to multiple marketplaces with:
- Multi-platform publishing
- License management
- Pricing configuration
- Analytics tracking
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.utils import get_logger
from src.marketplace.search import Marketplace, ModelLicense

logger = get_logger("marketplace.publish")


class PublishStatus(str, Enum):
    """Status of a publish operation."""
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"
    REMOVED = "removed"


@dataclass
class PublishConfig:
    """Configuration for publishing a model."""

    # Basic info
    title: str
    description: str
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)

    # Licensing
    license: ModelLicense = ModelLicense.CC_BY
    allow_commercial: bool = False
    allow_derivatives: bool = True
    require_attribution: bool = True

    # Pricing
    is_free: bool = True
    price: float = 0.0
    currency: str = "USD"

    # Files
    model_files: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    thumbnail: Optional[str] = None

    # Print settings (optional)
    print_settings: Optional[Dict[str, Any]] = None

    # Target marketplaces
    marketplaces: List[Marketplace] = field(default_factory=list)


@dataclass
class PublishResult:
    """Result of a publish operation."""

    marketplace: Marketplace
    status: PublishStatus
    model_id: Optional[str] = None
    model_url: Optional[str] = None
    published_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "marketplace": self.marketplace.value,
            "status": self.status.value,
            "model_id": self.model_id,
            "model_url": self.model_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "error_message": self.error_message,
        }


@dataclass
class PublishedModel:
    """A model published to marketplaces."""

    local_id: str  # Internal ID
    title: str
    config: PublishConfig
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Results per marketplace
    publish_results: Dict[Marketplace, PublishResult] = field(default_factory=dict)

    # Analytics (aggregated)
    total_downloads: int = 0
    total_likes: int = 0
    total_views: int = 0
    total_revenue: float = 0.0

    def to_dict(self) -> dict:
        return {
            "local_id": self.local_id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "marketplaces": list(self.publish_results.keys()),
            "publish_results": {
                mp.value: result.to_dict()
                for mp, result in self.publish_results.items()
            },
            "total_downloads": self.total_downloads,
            "total_likes": self.total_likes,
            "total_revenue": self.total_revenue,
        }


class ModelPublisher:
    """
    Publishes models to 3D marketplaces.

    Features:
    - Multi-marketplace publishing
    - Draft and scheduled publishing
    - Update/delete published models
    - Analytics tracking
    """

    def __init__(self, credentials: Optional[Dict[Marketplace, Dict[str, str]]] = None):
        """
        Initialize publisher.

        Args:
            credentials: Dict of marketplace -> {api_key, username, etc.}
        """
        self.credentials = credentials or {}
        self._published: Dict[str, PublishedModel] = {}
        self._publish_counter = 0

    def set_credentials(self, marketplace: Marketplace, **creds) -> None:
        """Set credentials for a marketplace."""
        self.credentials[marketplace] = creds
        logger.info(f"Set credentials for {marketplace.value}")

    def has_credentials(self, marketplace: Marketplace) -> bool:
        """Check if credentials are set for a marketplace."""
        return marketplace in self.credentials

    async def publish(self, config: PublishConfig) -> Dict[Marketplace, PublishResult]:
        """
        Publish a model to configured marketplaces.

        Args:
            config: Publish configuration

        Returns:
            Dict of marketplace -> PublishResult
        """
        # Validate files exist
        for file_path in config.model_files:
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Model file not found: {file_path}")

        results: Dict[Marketplace, PublishResult] = {}
        marketplaces = config.marketplaces or [
            mp for mp in Marketplace if self.has_credentials(mp)
        ]

        for marketplace in marketplaces:
            try:
                result = await self._publish_to_marketplace(marketplace, config)
                results[marketplace] = result
            except Exception as e:
                logger.error(f"Failed to publish to {marketplace.value}: {e}")
                results[marketplace] = PublishResult(
                    marketplace=marketplace,
                    status=PublishStatus.REJECTED,
                    error_message=str(e),
                )

        # Track published model
        self._publish_counter += 1
        local_id = f"PUB-{self._publish_counter:06d}"

        published = PublishedModel(
            local_id=local_id,
            title=config.title,
            config=config,
            publish_results=results,
        )
        self._published[local_id] = published

        logger.info(f"Published {config.title} to {len(results)} marketplaces")
        return results

    async def _publish_to_marketplace(
        self,
        marketplace: Marketplace,
        config: PublishConfig,
    ) -> PublishResult:
        """Publish to a specific marketplace."""
        if not self.has_credentials(marketplace):
            return PublishResult(
                marketplace=marketplace,
                status=PublishStatus.REJECTED,
                error_message="No credentials configured",
            )

        # In production, each marketplace has its own API
        # Here we simulate the publish process

        logger.info(f"Publishing to {marketplace.value}: {config.title}")

        # Simulate API call
        model_id = f"{marketplace.value}_{self._publish_counter}"

        return PublishResult(
            marketplace=marketplace,
            status=PublishStatus.PUBLISHED,
            model_id=model_id,
            model_url=f"https://{marketplace.value}.com/model/{model_id}",
            published_at=datetime.utcnow(),
        )

    async def update(
        self,
        local_id: str,
        marketplace: Marketplace,
        **updates,
    ) -> PublishResult:
        """Update a published model."""
        published = self._published.get(local_id)
        if not published:
            raise ValueError(f"Published model not found: {local_id}")

        result = published.publish_results.get(marketplace)
        if not result or result.status != PublishStatus.PUBLISHED:
            raise ValueError(f"Model not published to {marketplace.value}")

        # In production, call marketplace API to update

        logger.info(f"Updated {local_id} on {marketplace.value}")

        published.updated_at = datetime.utcnow()
        return result

    async def unpublish(
        self,
        local_id: str,
        marketplace: Optional[Marketplace] = None,
    ) -> int:
        """
        Unpublish a model from marketplaces.

        Args:
            local_id: Local model ID
            marketplace: Specific marketplace (None = all)

        Returns:
            Number of marketplaces unpublished from
        """
        published = self._published.get(local_id)
        if not published:
            raise ValueError(f"Published model not found: {local_id}")

        count = 0
        marketplaces = [marketplace] if marketplace else list(published.publish_results.keys())

        for mp in marketplaces:
            result = published.publish_results.get(mp)
            if result and result.status == PublishStatus.PUBLISHED:
                # In production, call marketplace API to remove
                result.status = PublishStatus.REMOVED
                count += 1
                logger.info(f"Unpublished {local_id} from {mp.value}")

        return count

    def get_published(self, local_id: str) -> Optional[PublishedModel]:
        """Get a published model by local ID."""
        return self._published.get(local_id)

    def get_all_published(self) -> List[PublishedModel]:
        """Get all published models."""
        return list(self._published.values())

    async def sync_analytics(self, local_id: str) -> Dict[Marketplace, Dict[str, int]]:
        """
        Sync analytics from marketplaces.

        Returns updated stats per marketplace.
        """
        published = self._published.get(local_id)
        if not published:
            raise ValueError(f"Published model not found: {local_id}")

        stats: Dict[Marketplace, Dict[str, int]] = {}

        for marketplace, result in published.publish_results.items():
            if result.status != PublishStatus.PUBLISHED:
                continue

            # In production, fetch from marketplace API
            # Simulated stats
            mp_stats = {
                "downloads": 100,
                "likes": 50,
                "views": 500,
            }
            stats[marketplace] = mp_stats

        # Update totals
        published.total_downloads = sum(s.get("downloads", 0) for s in stats.values())
        published.total_likes = sum(s.get("likes", 0) for s in stats.values())
        published.total_views = sum(s.get("views", 0) for s in stats.values())

        return stats

    def get_revenue_report(self) -> Dict[str, Any]:
        """Get revenue report across all published models."""
        total_revenue = 0.0
        by_marketplace: Dict[str, float] = {}
        paid_models = 0

        for published in self._published.values():
            if not published.config.is_free:
                paid_models += 1
                total_revenue += published.total_revenue

                for mp in published.publish_results.keys():
                    by_marketplace[mp.value] = by_marketplace.get(mp.value, 0) + published.total_revenue

        return {
            "total_models": len(self._published),
            "paid_models": paid_models,
            "total_revenue": total_revenue,
            "by_marketplace": by_marketplace,
            "currency": "USD",
        }


# Global publisher instance
_publisher: Optional[ModelPublisher] = None


def get_model_publisher() -> ModelPublisher:
    """Get the global model publisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = ModelPublisher()
    return _publisher


async def quick_publish(
    title: str,
    model_files: List[str],
    description: str = "",
    tags: Optional[List[str]] = None,
    marketplaces: Optional[List[Marketplace]] = None,
) -> Dict[Marketplace, PublishResult]:
    """
    Quick publish a model with defaults.

    Convenience function for simple publishing.
    """
    publisher = get_model_publisher()

    config = PublishConfig(
        title=title,
        description=description,
        model_files=model_files,
        tags=tags or [],
        marketplaces=marketplaces or [],
        license=ModelLicense.CC_BY,
        is_free=True,
    )

    return await publisher.publish(config)
