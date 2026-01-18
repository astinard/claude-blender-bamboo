"""Tripo AI client for text-to-3D generation.

Tripo AI (https://tripo3d.ai) provides alternative 3D generation:
- Good quality models
- Python SDK available: pip install tripo3d
- Competitive pricing
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

logger = get_logger("ai.tripo")


class TripoClient:
    """
    Client for Tripo AI text-to-3D API.

    API Documentation: https://docs.tripo3d.ai/

    Features:
    - Text-to-3D generation
    - Image-to-3D generation
    - Animation support
    """

    BASE_URL = "https://api.tripo3d.ai/v2/"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Tripo client.

        Args:
            api_key: Tripo API key (or set TRIPO_API_KEY env var)
        """
        self.api_key = api_key or os.environ.get("TRIPO_API_KEY")
        if not self.api_key:
            logger.warning("No Tripo API key configured")

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
            GenerationResult with task ID
        """
        if not self.api_key:
            return GenerationResult(
                request_id=request.request_id,
                status=GenerationStatus.FAILED,
                provider=GenerationProvider.TRIPO,
                error_message="Tripo API key not configured",
                error_code="NO_API_KEY",
            )

        # Build API request
        payload = {
            "type": "text_to_model",
            "prompt": request.prompt,
        }

        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    urljoin(self.BASE_URL, "task"),
                    headers=self._get_headers(),
                    json=payload,
                ) as response:
                    if response.status == 401:
                        return GenerationResult(
                            request_id=request.request_id,
                            status=GenerationStatus.FAILED,
                            provider=GenerationProvider.TRIPO,
                            error_message="Invalid API key",
                            error_code="UNAUTHORIZED",
                        )

                    if response.status == 429:
                        return GenerationResult(
                            request_id=request.request_id,
                            status=GenerationStatus.FAILED,
                            provider=GenerationProvider.TRIPO,
                            error_message="Rate limit exceeded",
                            error_code="RATE_LIMITED",
                        )

                    if response.status not in [200, 201]:
                        text = await response.text()
                        return GenerationResult(
                            request_id=request.request_id,
                            status=GenerationStatus.FAILED,
                            provider=GenerationProvider.TRIPO,
                            error_message=f"API error: {text}",
                            error_code=f"HTTP_{response.status}",
                        )

                    data = await response.json()
                    task_id = data.get("data", {}).get("task_id")

                    if not task_id:
                        return GenerationResult(
                            request_id=request.request_id,
                            status=GenerationStatus.FAILED,
                            provider=GenerationProvider.TRIPO,
                            error_message="No task ID in response",
                        )

                    logger.info(f"Tripo generation started: {task_id}")

                    return GenerationResult(
                        request_id=request.request_id,
                        status=GenerationStatus.PROCESSING,
                        provider=GenerationProvider.TRIPO,
                        provider_task_id=task_id,
                        started_at=datetime.now().isoformat(),
                    )

        except aiohttp.ClientError as e:
            logger.error(f"Tripo API error: {e}")
            return GenerationResult(
                request_id=request.request_id,
                status=GenerationStatus.FAILED,
                provider=GenerationProvider.TRIPO,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    async def check_status(self, task_id: str) -> GenerationResult:
        """
        Check status of a generation task.

        Args:
            task_id: Tripo task ID

        Returns:
            GenerationResult with current status
        """
        if not self.api_key:
            return GenerationResult(
                request_id=task_id,
                status=GenerationStatus.FAILED,
                provider=GenerationProvider.TRIPO,
                error_message="Tripo API key not configured",
            )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    urljoin(self.BASE_URL, f"task/{task_id}"),
                    headers=self._get_headers(),
                ) as response:
                    if response.status != 200:
                        return GenerationResult(
                            request_id=task_id,
                            status=GenerationStatus.FAILED,
                            provider=GenerationProvider.TRIPO,
                            error_message=f"Failed to check status: {response.status}",
                        )

                    data = await response.json()
                    task_data = data.get("data", {})

                    status = task_data.get("status", "").lower()
                    if status == "success":
                        gen_status = GenerationStatus.COMPLETED
                    elif status == "failed":
                        gen_status = GenerationStatus.FAILED
                    elif status in ["running", "queued", "pending"]:
                        gen_status = GenerationStatus.PROCESSING
                    else:
                        gen_status = GenerationStatus.PROCESSING

                    result = GenerationResult(
                        request_id=task_id,
                        status=gen_status,
                        provider=GenerationProvider.TRIPO,
                        provider_task_id=task_id,
                    )

                    if gen_status == GenerationStatus.COMPLETED:
                        output = task_data.get("output", {})
                        result.model_url = output.get("model")
                        result.preview_url = output.get("rendered_image")

                    if gen_status == GenerationStatus.FAILED:
                        result.error_message = task_data.get("message", "Unknown error")

                    return result

        except aiohttp.ClientError as e:
            logger.error(f"Tripo status check error: {e}")
            return GenerationResult(
                request_id=task_id,
                status=GenerationStatus.FAILED,
                provider=GenerationProvider.TRIPO,
                error_message=str(e),
            )

    async def download_model(
        self,
        task_id: str,
        output_path: str,
        format: ModelFormat = ModelFormat.GLB,
    ) -> bool:
        """
        Download a completed model.

        Args:
            task_id: Tripo task ID
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

    async def get_balance(self) -> Optional[dict]:
        """
        Get account balance/credits.

        Returns:
            Balance info dict or None
        """
        if not self.api_key:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    urljoin(self.BASE_URL, "user/balance"),
                    headers=self._get_headers(),
                ) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    return data.get("data")

        except aiohttp.ClientError:
            return None
