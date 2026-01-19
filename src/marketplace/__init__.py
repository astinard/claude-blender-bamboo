"""Marketplace integration module for Claude Fab Lab.

Provides unified access to 3D model marketplaces including:
- Thangs
- Printables (Prusa)
- MyMiniFactory
- Cults3D
- Thingiverse

Features:
- Unified search across marketplaces
- Model publishing
- Analytics tracking
- License management
"""

from src.marketplace.search import (
    UnifiedSearch,
    SearchQuery,
    SearchResults,
    ModelResult,
    ModelFile,
    Marketplace,
    ModelLicense,
    SortOption,
    MarketplaceConnector,
    ThangsConnector,
    PrintablesConnector,
    MyMiniFactoryConnector,
    Cults3DConnector,
    ThingiverseConnector,
    get_unified_search,
    search_models,
)

from src.marketplace.publish import (
    ModelPublisher,
    PublishConfig,
    PublishResult,
    PublishedModel,
    PublishStatus,
    get_model_publisher,
    quick_publish,
)

__all__ = [
    # Search
    "UnifiedSearch",
    "SearchQuery",
    "SearchResults",
    "ModelResult",
    "ModelFile",
    "Marketplace",
    "ModelLicense",
    "SortOption",
    "MarketplaceConnector",
    "ThangsConnector",
    "PrintablesConnector",
    "MyMiniFactoryConnector",
    "Cults3DConnector",
    "ThingiverseConnector",
    "get_unified_search",
    "search_models",
    # Publish
    "ModelPublisher",
    "PublishConfig",
    "PublishResult",
    "PublishedModel",
    "PublishStatus",
    "get_model_publisher",
    "quick_publish",
]
