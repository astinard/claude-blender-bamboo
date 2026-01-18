"""Meshy AI client for text-to-3D generation.

Meshy AI (https://meshy.ai) is the recommended provider:
- Native Blender plugin available
- Direct STL/OBJ/3MF export
- Good quality for 3D printing
- $20/month Pro plan
- 20 req/sec rate limit
"""

import asyncio
import aiohttp
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from src.utils import get_logger
from src.config import get_settings
from src.ai.text_to_3d import (
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
    GenerationProvider,
    ModelFormat,
    ArtStyle,
)

logger = get_logger("ai.meshy")


class MeshyClient:
    """
    Client for Meshy AI text-to-3D API.

    API Documentation: https://docs.meshy.ai/

    Features:
    - Text-to-3D generation
    - Image-to-3D generation
    - Multiple output formats
    - Style presets
    """

    BASE_URL = "https://api.meshy.ai/v2/"

    # Map our art styles to Meshy's
    STYLE_MAP = {
        ArtStyle.REALISTIC: "realistic",
        ArtStyle.CARTOON: "cartoon",
        ArtStyle.LOW_POLY: "low-poly",
        ArtStyle.SCULPTURE: "sculpture",
        ArtStyle.GAME_ASSET: "game-asset",
        ArtStyle.PRINTABLE: "realistic",  # Use realistic for best print quality
    }

    # Map our formats to Meshy's
    FORMAT_MAP = {
        ModelFormat.STL: "stl",
        ModelFormat.OBJ: "obj",
        ModelFormat.GLB: "glb",
        ModelFormat.GLTF: "gltf",
        ModelFormat.FBX: "fbx",
        ModelFormat.THREEMF: "3mf",
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Meshy client.

        Args:
            api_key: Meshy API key (or set MESHY_API_KEY env var)
        """
        self.api_key = api_key or os.environ.get("MESHY_API_KEY")
        if not self.api_key:
            logger.warning("No Meshy API key configured")

        settings = get_settings()
        self.output_dir = Path(settings.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_headers(self) -> dict:
        """Get API request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate a 3D model from text.

        Args:
            request: Generation request parameters

        Returns:
            GenerationResult with task ID (generation is async)
        """
        if not self.api_key:
            return GenerationResult(
                request_id=request.request_id,
                status=GenerationStatus.FAILED,
                provider=GenerationProvider.MESHY,
                error_message="Meshy API key not configured",
                error_code="NO_API_KEY",
            )

        # Build API request
        payload = {
            "mode": "preview",  # preview or refine
            "prompt": request.prompt,
            "art_style": self.STYLE_MAP.get(request.art_style, "realistic"),
            "topology": "quad",  # quad for better printability
        }

        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    urljoin(self.BASE_URL, "text-to-3d"),
                    headers=self._get_headers(),
                    json=payload,
                ) as response:
                    if response.status == 401:
                        return GenerationResult(
                            request_id=request.request_id,
                            status=GenerationStatus.FAILED,
                            provider=GenerationProvider.MESHY,
                            error_message="Invalid API key",
                            error_code="UNAUTHORIZED",
                        )

                    if response.status == 429:
                        return GenerationResult(
                            request_id=request.request_id,
                            status=GenerationStatus.FAILED,
                            provider=GenerationProvider.MESHY,
                            error_message="Rate limit exceeded",
                            error_code="RATE_LIMITED",
                        )

                    if response.status != 200:
                        text = await response.text()
                        return GenerationResult(
                            request_id=request.request_id,
                            status=GenerationStatus.FAILED,
                            provider=GenerationProvider.MESHY,
                            error_message=f"API error: {text}",
                            error_code=f"HTTP_{response.status}",
                        )

                    data = await response.json()
                    task_id = data.get("result")

                    logger.info(f"Meshy generation started: {task_id}")

                    return GenerationResult(
                        request_id=request.request_id,
                        status=GenerationStatus.PROCESSING,
                        provider=GenerationProvider.MESHY,
                        provider_task_id=task_id,
                        started_at=datetime.now().isoformat(),
                    )

        except aiohttp.ClientError as e:
            logger.error(f"Meshy API error: {e}")
            return GenerationResult(
                request_id=request.request_id,
                status=GenerationStatus.FAILED,
                provider=GenerationProvider.MESHY,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    async def check_status(self, task_id: str) -> GenerationResult:
        """
        Check status of a generation task.

        Args:
            task_id: Meshy task ID

        Returns:
            GenerationResult with current status
        """
        if not self.api_key:
            return GenerationResult(
                request_id=task_id,
                status=GenerationStatus.FAILED,
                provider=GenerationProvider.MESHY,
                error_message="Meshy API key not configured",
            )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    urljoin(self.BASE_URL, f"text-to-3d/{task_id}"),
                    headers=self._get_headers(),
                ) as response:
                    if response.status != 200:
                        return GenerationResult(
                            request_id=task_id,
                            status=GenerationStatus.FAILED,
                            provider=GenerationProvider.MESHY,
                            error_message=f"Failed to check status: {response.status}",
                        )

                    data = await response.json()

                    status = data.get("status", "").upper()
                    if status == "SUCCEEDED":
                        gen_status = GenerationStatus.COMPLETED
                    elif status == "FAILED":
                        gen_status = GenerationStatus.FAILED
                    elif status == "PENDING" or status == "IN_PROGRESS":
                        gen_status = GenerationStatus.PROCESSING
                    else:
                        gen_status = GenerationStatus.PROCESSING

                    result = GenerationResult(
                        request_id=task_id,
                        status=gen_status,
                        provider=GenerationProvider.MESHY,
                        provider_task_id=task_id,
                    )

                    if gen_status == GenerationStatus.COMPLETED:
                        # Extract model URLs
                        model_urls = data.get("model_urls", {})
                        result.model_url = model_urls.get("stl") or model_urls.get("obj")
                        result.preview_url = data.get("thumbnail_url")

                    if gen_status == GenerationStatus.FAILED:
                        result.error_message = data.get("message", "Unknown error")

                    return result

        except aiohttp.ClientError as e:
            logger.error(f"Meshy status check error: {e}")
            return GenerationResult(
                request_id=task_id,
                status=GenerationStatus.FAILED,
                provider=GenerationProvider.MESHY,
                error_message=str(e),
            )

    async def download_model(
        self,
        task_id: str,
        output_path: str,
        format: ModelFormat = ModelFormat.STL,
    ) -> bool:
        """
        Download a completed model.

        Args:
            task_id: Meshy task ID
            output_path: Path to save the model
            format: Desired format

        Returns:
            True if download successful
        """
        # First get the model URL
        result = await self.check_status(task_id)

        if result.status != GenerationStatus.COMPLETED:
            logger.error(f"Model not ready for download: {result.status}")
            return False

        if not result.model_url:
            logger.error("No model URL available")
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(result.model_url) as response:
                    if response.status != 200:
                        logger.error(f"Download failed: {response.status}")
                        return False

                    content = await response.read()

                    output = Path(output_path)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(content)

                    logger.info(f"Model downloaded to: {output_path}")
                    return True

        except aiohttp.ClientError as e:
            logger.error(f"Download error: {e}")
            return False

    async def list_generations(self, limit: int = 10) -> list:
        """
        List recent generations.

        Args:
            limit: Maximum number to return

        Returns:
            List of generation info dicts
        """
        if not self.api_key:
            return []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    urljoin(self.BASE_URL, "text-to-3d"),
                    headers=self._get_headers(),
                    params={"pageSize": limit},
                ) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    return data.get("result", [])

        except aiohttp.ClientError:
            return []
