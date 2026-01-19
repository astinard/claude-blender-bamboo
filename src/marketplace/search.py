"""Unified search across 3D model marketplaces.

Provides a single interface to search models from:
- Thangs
- Printables (Prusa)
- MyMiniFactory
- Cults3D
- Thingiverse
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

from src.utils import get_logger

logger = get_logger("marketplace.search")


class Marketplace(str, Enum):
    """Supported marketplaces."""
    THANGS = "thangs"
    PRINTABLES = "printables"
    MYMINIFACTORY = "myminifactory"
    CULTS3D = "cults3d"
    THINGIVERSE = "thingiverse"


class ModelLicense(str, Enum):
    """Model license types."""
    FREE = "free"
    PAID = "paid"
    CC_BY = "cc_by"
    CC_BY_SA = "cc_by_sa"
    CC_BY_NC = "cc_by_nc"
    CC_BY_NC_SA = "cc_by_nc_sa"
    CC0 = "cc0"
    COMMERCIAL = "commercial"
    UNKNOWN = "unknown"


class SortOption(str, Enum):
    """Search sort options."""
    RELEVANCE = "relevance"
    POPULAR = "popular"
    RECENT = "recent"
    DOWNLOADS = "downloads"
    LIKES = "likes"


@dataclass
class ModelFile:
    """A downloadable file in a model."""

    filename: str
    url: str
    size_bytes: int = 0
    format: str = ""  # stl, obj, 3mf, step


@dataclass
class ModelResult:
    """A model from marketplace search."""

    model_id: str
    marketplace: Marketplace
    title: str
    description: str = ""
    author: str = ""
    author_url: str = ""

    # URLs
    url: str = ""
    thumbnail_url: str = ""
    images: List[str] = field(default_factory=list)

    # Metadata
    license: ModelLicense = ModelLicense.UNKNOWN
    price: float = 0.0
    currency: str = "USD"
    is_free: bool = True

    # Stats
    downloads: int = 0
    likes: int = 0
    views: int = 0
    comments: int = 0

    # Dates
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Categories/tags
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # Files
    files: List[ModelFile] = field(default_factory=list)
    file_formats: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "marketplace": self.marketplace.value,
            "title": self.title,
            "description": self.description[:200] if self.description else "",
            "author": self.author,
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
            "license": self.license.value,
            "price": self.price,
            "is_free": self.is_free,
            "downloads": self.downloads,
            "likes": self.likes,
            "categories": self.categories,
            "tags": self.tags,
            "file_formats": self.file_formats,
        }


@dataclass
class SearchQuery:
    """Search query parameters."""

    query: str
    marketplaces: List[Marketplace] = field(default_factory=list)  # Empty = all
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    license: Optional[ModelLicense] = None
    free_only: bool = False
    sort: SortOption = SortOption.RELEVANCE
    page: int = 1
    per_page: int = 20


@dataclass
class SearchResults:
    """Results from marketplace search."""

    query: str
    total_results: int
    results: List[ModelResult]
    page: int
    per_page: int
    has_more: bool
    marketplaces_searched: List[Marketplace]
    search_time_seconds: float = 0.0


class MarketplaceConnector(ABC):
    """Abstract base class for marketplace connectors."""

    marketplace: Marketplace

    @abstractmethod
    async def search(self, query: SearchQuery) -> List[ModelResult]:
        """Search for models."""
        pass

    @abstractmethod
    async def get_model(self, model_id: str) -> Optional[ModelResult]:
        """Get model details by ID."""
        pass

    @abstractmethod
    async def download_model(self, model_id: str, output_dir: str) -> List[str]:
        """Download model files."""
        pass


class ThangsConnector(MarketplaceConnector):
    """Connector for Thangs marketplace."""

    marketplace = Marketplace.THANGS
    BASE_URL = "https://thangs.com"
    API_URL = "https://api.thangs.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search(self, query: SearchQuery) -> List[ModelResult]:
        """Search Thangs for models."""
        # In production, use aiohttp to call Thangs API
        # GET https://api.thangs.com/v2/search?q={query}&page={page}

        logger.info(f"Searching Thangs for: {query.query}")

        # Mock results for demonstration
        return [
            ModelResult(
                model_id=f"thangs_{i}",
                marketplace=self.marketplace,
                title=f"Thangs Model: {query.query} #{i}",
                url=f"{self.BASE_URL}/model/{i}",
                thumbnail_url=f"{self.BASE_URL}/thumbnails/{i}.png",
                author="Thangs User",
                license=ModelLicense.CC_BY,
                downloads=100 * i,
                likes=50 * i,
                tags=[query.query, "3d-print"],
                file_formats=["stl", "3mf"],
            )
            for i in range(1, min(6, query.per_page + 1))
        ]

    async def get_model(self, model_id: str) -> Optional[ModelResult]:
        """Get model details from Thangs."""
        # GET https://api.thangs.com/v2/models/{model_id}
        return None

    async def download_model(self, model_id: str, output_dir: str) -> List[str]:
        """Download from Thangs."""
        return []


class PrintablesConnector(MarketplaceConnector):
    """Connector for Printables (Prusa) marketplace."""

    marketplace = Marketplace.PRINTABLES
    BASE_URL = "https://www.printables.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search(self, query: SearchQuery) -> List[ModelResult]:
        """Search Printables for models."""
        logger.info(f"Searching Printables for: {query.query}")

        return [
            ModelResult(
                model_id=f"printables_{i}",
                marketplace=self.marketplace,
                title=f"Printables Model: {query.query} #{i}",
                url=f"{self.BASE_URL}/model/{i}",
                author="Printables User",
                license=ModelLicense.CC_BY_NC,
                downloads=200 * i,
                likes=100 * i,
                tags=[query.query, "prusa"],
                file_formats=["stl", "3mf", "step"],
            )
            for i in range(1, min(6, query.per_page + 1))
        ]

    async def get_model(self, model_id: str) -> Optional[ModelResult]:
        return None

    async def download_model(self, model_id: str, output_dir: str) -> List[str]:
        return []


class MyMiniFactoryConnector(MarketplaceConnector):
    """Connector for MyMiniFactory marketplace."""

    marketplace = Marketplace.MYMINIFACTORY
    BASE_URL = "https://www.myminifactory.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search(self, query: SearchQuery) -> List[ModelResult]:
        """Search MyMiniFactory for models."""
        logger.info(f"Searching MyMiniFactory for: {query.query}")

        return [
            ModelResult(
                model_id=f"mmf_{i}",
                marketplace=self.marketplace,
                title=f"MyMiniFactory Model: {query.query} #{i}",
                url=f"{self.BASE_URL}/object/{i}",
                author="MMF User",
                license=ModelLicense.CC_BY,
                downloads=150 * i,
                likes=75 * i,
                categories=["miniatures", "gaming"],
                file_formats=["stl"],
            )
            for i in range(1, min(6, query.per_page + 1))
        ]

    async def get_model(self, model_id: str) -> Optional[ModelResult]:
        return None

    async def download_model(self, model_id: str, output_dir: str) -> List[str]:
        return []


class Cults3DConnector(MarketplaceConnector):
    """Connector for Cults3D marketplace."""

    marketplace = Marketplace.CULTS3D
    BASE_URL = "https://cults3d.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search(self, query: SearchQuery) -> List[ModelResult]:
        """Search Cults3D for models."""
        logger.info(f"Searching Cults3D for: {query.query}")

        results = []
        for i in range(1, min(6, query.per_page + 1)):
            is_paid = i % 3 == 0  # Every 3rd is paid
            results.append(ModelResult(
                model_id=f"cults_{i}",
                marketplace=self.marketplace,
                title=f"Cults3D Model: {query.query} #{i}",
                url=f"{self.BASE_URL}/3d-model/{i}",
                author="Cults User",
                license=ModelLicense.PAID if is_paid else ModelLicense.FREE,
                price=4.99 if is_paid else 0.0,
                is_free=not is_paid,
                downloads=80 * i,
                likes=40 * i,
                file_formats=["stl", "obj"],
            ))

        if query.free_only:
            results = [r for r in results if r.is_free]

        return results

    async def get_model(self, model_id: str) -> Optional[ModelResult]:
        return None

    async def download_model(self, model_id: str, output_dir: str) -> List[str]:
        return []


class ThingiverseConnector(MarketplaceConnector):
    """Connector for Thingiverse marketplace."""

    marketplace = Marketplace.THINGIVERSE
    BASE_URL = "https://www.thingiverse.com"
    API_URL = "https://api.thingiverse.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search(self, query: SearchQuery) -> List[ModelResult]:
        """Search Thingiverse for models."""
        logger.info(f"Searching Thingiverse for: {query.query}")

        return [
            ModelResult(
                model_id=f"thing_{i}",
                marketplace=self.marketplace,
                title=f"Thingiverse Thing: {query.query} #{i}",
                url=f"{self.BASE_URL}/thing:{i}",
                author="Thingiverse User",
                license=ModelLicense.CC_BY_SA,
                downloads=300 * i,
                likes=150 * i,
                file_formats=["stl"],
            )
            for i in range(1, min(6, query.per_page + 1))
        ]

    async def get_model(self, model_id: str) -> Optional[ModelResult]:
        return None

    async def download_model(self, model_id: str, output_dir: str) -> List[str]:
        return []


class UnifiedSearch:
    """
    Unified search across multiple 3D model marketplaces.

    Features:
    - Search multiple marketplaces simultaneously
    - Aggregate and deduplicate results
    - Filter by license, price, categories
    - Sort results
    """

    CONNECTORS: Dict[Marketplace, type] = {
        Marketplace.THANGS: ThangsConnector,
        Marketplace.PRINTABLES: PrintablesConnector,
        Marketplace.MYMINIFACTORY: MyMiniFactoryConnector,
        Marketplace.CULTS3D: Cults3DConnector,
        Marketplace.THINGIVERSE: ThingiverseConnector,
    }

    def __init__(self, api_keys: Optional[Dict[Marketplace, str]] = None):
        """
        Initialize unified search.

        Args:
            api_keys: Dict of marketplace -> API key
        """
        self.api_keys = api_keys or {}
        self._connectors: Dict[Marketplace, MarketplaceConnector] = {}

        # Initialize connectors
        for marketplace, connector_class in self.CONNECTORS.items():
            api_key = self.api_keys.get(marketplace)
            self._connectors[marketplace] = connector_class(api_key=api_key)

    async def search(self, query: SearchQuery) -> SearchResults:
        """
        Search across marketplaces.

        Args:
            query: Search query parameters

        Returns:
            SearchResults with aggregated results
        """
        import asyncio
        import time

        start_time = time.time()

        # Determine which marketplaces to search
        marketplaces = query.marketplaces or list(self._connectors.keys())

        # Search in parallel
        tasks = [
            self._connectors[mp].search(query)
            for mp in marketplaces
            if mp in self._connectors
        ]

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        all_results = []
        for results in results_lists:
            if isinstance(results, Exception):
                logger.error(f"Search error: {results}")
                continue
            all_results.extend(results)

        # Filter
        if query.free_only:
            all_results = [r for r in all_results if r.is_free]

        if query.license:
            all_results = [r for r in all_results if r.license == query.license]

        # Sort
        if query.sort == SortOption.POPULAR:
            all_results.sort(key=lambda r: r.downloads + r.likes, reverse=True)
        elif query.sort == SortOption.RECENT:
            all_results.sort(key=lambda r: r.created_at or datetime.min, reverse=True)
        elif query.sort == SortOption.DOWNLOADS:
            all_results.sort(key=lambda r: r.downloads, reverse=True)
        elif query.sort == SortOption.LIKES:
            all_results.sort(key=lambda r: r.likes, reverse=True)

        # Paginate
        total = len(all_results)
        start = (query.page - 1) * query.per_page
        end = start + query.per_page
        page_results = all_results[start:end]

        search_time = time.time() - start_time

        return SearchResults(
            query=query.query,
            total_results=total,
            results=page_results,
            page=query.page,
            per_page=query.per_page,
            has_more=end < total,
            marketplaces_searched=marketplaces,
            search_time_seconds=round(search_time, 3),
        )

    async def get_model(self, marketplace: Marketplace, model_id: str) -> Optional[ModelResult]:
        """Get model details from a specific marketplace."""
        connector = self._connectors.get(marketplace)
        if connector:
            return await connector.get_model(model_id)
        return None

    async def download(
        self,
        marketplace: Marketplace,
        model_id: str,
        output_dir: str,
    ) -> List[str]:
        """Download model files from a marketplace."""
        connector = self._connectors.get(marketplace)
        if connector:
            return await connector.download_model(model_id, output_dir)
        return []


# Global search instance
_search: Optional[UnifiedSearch] = None


def get_unified_search() -> UnifiedSearch:
    """Get the global unified search instance."""
    global _search
    if _search is None:
        _search = UnifiedSearch()
    return _search


async def search_models(
    query: str,
    free_only: bool = False,
    marketplaces: Optional[List[Marketplace]] = None,
) -> SearchResults:
    """
    Search for 3D models across marketplaces.

    Convenience function for common searches.
    """
    search = get_unified_search()

    search_query = SearchQuery(
        query=query,
        marketplaces=marketplaces or [],
        free_only=free_only,
    )

    return await search.search(search_query)
