"""Unified interface for text-to-3D model generation.

Supports multiple AI providers:
- Meshy AI (recommended): Native Blender plugin, direct STL export
- Tripo AI: Alternative provider with good quality

P4.1: AI Text-to-3D Generation
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Protocol, runtime_checkable
from uuid import uuid4

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("ai.text_to_3d")


class GenerationProvider(str, Enum):
    """Available AI generation providers."""
    MESHY = "meshy"
    TRIPO = "tripo"
    MOCK = "mock"  # For testing


class GenerationStatus(str, Enum):
    """Status of a generation request."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModelFormat(str, Enum):
    """Output model formats."""
    STL = "stl"
    OBJ = "obj"
    GLB = "glb"
    GLTF = "gltf"
    FBX = "fbx"
    THREEMF = "3mf"


class ArtStyle(str, Enum):
    """Art style presets."""
    REALISTIC = "realistic"
    CARTOON = "cartoon"
    LOW_POLY = "low_poly"
    SCULPTURE = "sculpture"
    GAME_ASSET = "game_asset"
    PRINTABLE = "printable"  # Optimized for 3D printing


@dataclass
class GenerationRequest:
    """Request for 3D model generation."""

    prompt: str
    provider: GenerationProvider = GenerationProvider.MESHY
    output_format: ModelFormat = ModelFormat.STL
    art_style: ArtStyle = ArtStyle.PRINTABLE

    # Generation options
    negative_prompt: Optional[str] = None  # What to avoid
    seed: Optional[int] = None  # For reproducibility
    resolution: str = "medium"  # low, medium, high

    # Output options
    output_dir: Optional[str] = None
    output_name: Optional[str] = None

    # Request tracking
    request_id: str = field(default_factory=lambda: str(uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        """Validate request parameters."""
        if not self.prompt or len(self.prompt.strip()) < 3:
            raise ValueError("Prompt must be at least 3 characters")

        if len(self.prompt) > 500:
            raise ValueError("Prompt must be under 500 characters")


@dataclass
class GenerationResult:
    """Result of a 3D generation request."""

    request_id: str
    status: GenerationStatus
    provider: GenerationProvider

    # Output file info (if completed)
    output_path: Optional[str] = None
    output_format: Optional[ModelFormat] = None
    file_size_bytes: int = 0

    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0

    # Provider-specific info
    provider_task_id: Optional[str] = None
    preview_url: Optional[str] = None
    model_url: Optional[str] = None

    # Error info (if failed)
    error_message: Optional[str] = None
    error_code: Optional[str] = None

    # Quality metrics (if available)
    vertex_count: int = 0
    face_count: int = 0
    is_watertight: bool = False  # Important for 3D printing

    @property
    def is_successful(self) -> bool:
        """Check if generation was successful."""
        return self.status == GenerationStatus.COMPLETED and self.output_path is not None


@runtime_checkable
class GenerationClient(Protocol):
    """Protocol for generation provider clients."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate a 3D model from text."""
        ...

    async def check_status(self, task_id: str) -> GenerationResult:
        """Check status of an ongoing generation."""
        ...

    async def download_model(self, task_id: str, output_path: str) -> bool:
        """Download a completed model."""
        ...


class TextTo3DGenerator:
    """
    Unified interface for text-to-3D model generation.

    Supports multiple providers with a consistent API.

    Example:
        generator = TextTo3DGenerator()
        result = await generator.generate(
            "a dragon phone stand",
            provider=GenerationProvider.MESHY,
        )
        print(f"Model saved to: {result.output_path}")
    """

    def __init__(self, default_provider: GenerationProvider = GenerationProvider.MESHY):
        """
        Initialize the generator.

        Args:
            default_provider: Default provider to use if not specified
        """
        self.default_provider = default_provider
        self._clients: Dict[GenerationProvider, GenerationClient] = {}
        self._initialize_clients()

    def _initialize_clients(self) -> None:
        """Initialize provider clients based on available API keys."""
        settings = get_settings()

        # Import clients here to avoid circular imports
        from src.ai.meshy_client import MeshyClient
        from src.ai.tripo_client import TripoClient

        if settings.meshy_api_key:
            self._clients[GenerationProvider.MESHY] = MeshyClient(settings.meshy_api_key)
            logger.info("Meshy client initialized")

        if settings.tripo_api_key:
            self._clients[GenerationProvider.TRIPO] = TripoClient(settings.tripo_api_key)
            logger.info("Tripo client initialized")

        # Always available mock client for testing
        from src.ai.mock_client import MockClient
        self._clients[GenerationProvider.MOCK] = MockClient()

    def get_available_providers(self) -> List[GenerationProvider]:
        """Get list of available providers with configured API keys."""
        return list(self._clients.keys())

    def is_provider_available(self, provider: GenerationProvider) -> bool:
        """Check if a provider is available."""
        return provider in self._clients

    async def generate(
        self,
        prompt: str,
        provider: Optional[GenerationProvider] = None,
        output_format: ModelFormat = ModelFormat.STL,
        art_style: ArtStyle = ArtStyle.PRINTABLE,
        output_dir: Optional[str] = None,
        output_name: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        wait_for_completion: bool = True,
        progress_callback: Optional[callable] = None,
    ) -> GenerationResult:
        """
        Generate a 3D model from a text prompt.

        Args:
            prompt: Text description of the model to generate
            provider: AI provider to use (defaults to configured default)
            output_format: Desired output format (STL recommended for printing)
            art_style: Art style preset
            output_dir: Directory to save the model
            output_name: Name for the output file (without extension)
            negative_prompt: What to avoid in the generation
            seed: Seed for reproducibility
            wait_for_completion: Wait for generation to complete
            progress_callback: Callback for progress updates

        Returns:
            GenerationResult with output path and metadata
        """
        provider = provider or self.default_provider

        if provider not in self._clients:
            available = ", ".join(p.value for p in self.get_available_providers())
            raise ValueError(
                f"Provider '{provider.value}' not available. "
                f"Available: {available}. Check API key configuration."
            )

        # Create request
        request = GenerationRequest(
            prompt=prompt,
            provider=provider,
            output_format=output_format,
            art_style=art_style,
            output_dir=output_dir,
            output_name=output_name,
            negative_prompt=negative_prompt,
            seed=seed,
        )

        logger.info(f"Starting generation: '{prompt[:50]}...' with {provider.value}")

        client = self._clients[provider]
        start_time = time.time()

        # Start generation
        result = await client.generate(request)

        if wait_for_completion and result.status == GenerationStatus.PROCESSING:
            # Poll for completion
            result = await self._wait_for_completion(
                client,
                result.provider_task_id,
                progress_callback,
            )

        # Update timing
        result.duration_seconds = time.time() - start_time
        result.completed_at = datetime.now().isoformat()

        if result.is_successful:
            logger.info(f"Generation complete: {result.output_path}")
        else:
            logger.error(f"Generation failed: {result.error_message}")

        return result

    async def _wait_for_completion(
        self,
        client: GenerationClient,
        task_id: str,
        progress_callback: Optional[callable],
        timeout_seconds: int = 300,
        poll_interval: float = 5.0,
    ) -> GenerationResult:
        """Wait for a generation task to complete."""
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            result = await client.check_status(task_id)

            if progress_callback:
                progress_callback(result)

            if result.status in [GenerationStatus.COMPLETED, GenerationStatus.FAILED]:
                return result

            await asyncio.sleep(poll_interval)

        # Timeout
        return GenerationResult(
            request_id=task_id,
            status=GenerationStatus.FAILED,
            provider=GenerationProvider.MOCK,
            error_message=f"Generation timed out after {timeout_seconds}s",
            error_code="TIMEOUT",
        )

    def generate_sync(
        self,
        prompt: str,
        provider: Optional[GenerationProvider] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        Synchronous wrapper for generate().

        For use in non-async contexts.
        """
        return asyncio.run(self.generate(prompt, provider, **kwargs))


def generate_model(
    prompt: str,
    provider: str = "meshy",
    output_dir: Optional[str] = None,
    output_name: Optional[str] = None,
    wait: bool = True,
) -> GenerationResult:
    """
    Convenience function for generating a 3D model.

    Args:
        prompt: Text description
        provider: Provider name (meshy, tripo, mock)
        output_dir: Output directory
        output_name: Output filename
        wait: Wait for completion

    Returns:
        GenerationResult

    Example:
        result = generate_model("a cute robot figurine")
        if result.is_successful:
            print(f"Model at: {result.output_path}")
    """
    generator = TextTo3DGenerator()

    try:
        provider_enum = GenerationProvider(provider.lower())
    except ValueError:
        raise ValueError(f"Unknown provider: {provider}")

    return generator.generate_sync(
        prompt,
        provider=provider_enum,
        output_dir=output_dir,
        output_name=output_name,
        wait_for_completion=wait,
    )
