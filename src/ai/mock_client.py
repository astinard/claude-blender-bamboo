"""Mock AI client for testing without API calls."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.utils import get_logger
from src.config import get_settings
from src.ai.text_to_3d import (
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
    GenerationProvider,
    ModelFormat,
)

logger = get_logger("ai.mock")


class MockClient:
    """
    Mock client for testing 3D generation without API calls.

    Simulates the generation process and creates placeholder output files.
    """

    def __init__(self):
        """Initialize mock client."""
        settings = get_settings()
        self.output_dir = Path(settings.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track tasks for status checks
        self._tasks = {}

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Simulate 3D model generation.

        Creates a placeholder STL file immediately.

        Args:
            request: Generation request

        Returns:
            Completed GenerationResult with mock output
        """
        logger.info(f"Mock generation: {request.prompt}")

        task_id = str(uuid4())[:8]

        # Determine output path
        output_dir = Path(request.output_dir) if request.output_dir else self.output_dir
        output_name = request.output_name or f"generated_{task_id}"
        extension = request.output_format.value

        output_path = output_dir / f"{output_name}.{extension}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create a minimal valid STL file
        stl_content = self._generate_mock_stl(request.prompt)
        output_path.write_text(stl_content)

        logger.info(f"Mock model created: {output_path}")

        result = GenerationResult(
            request_id=request.request_id,
            status=GenerationStatus.COMPLETED,
            provider=GenerationProvider.MOCK,
            provider_task_id=task_id,
            output_path=str(output_path),
            output_format=request.output_format,
            file_size_bytes=len(stl_content),
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            duration_seconds=0.1,
            vertex_count=24,
            face_count=12,
            is_watertight=True,
        )

        self._tasks[task_id] = result
        return result

    async def check_status(self, task_id: str) -> GenerationResult:
        """
        Check status of a mock task.

        Args:
            task_id: Task ID

        Returns:
            GenerationResult
        """
        if task_id in self._tasks:
            return self._tasks[task_id]

        return GenerationResult(
            request_id=task_id,
            status=GenerationStatus.FAILED,
            provider=GenerationProvider.MOCK,
            error_message="Task not found",
        )

    async def download_model(
        self,
        task_id: str,
        output_path: str,
        format: ModelFormat = ModelFormat.STL,
    ) -> bool:
        """
        Mock download - model is already created.

        Args:
            task_id: Task ID
            output_path: Requested output path

        Returns:
            True if task exists
        """
        if task_id in self._tasks:
            result = self._tasks[task_id]
            if result.output_path:
                # Copy to requested location if different
                src = Path(result.output_path)
                dst = Path(output_path)

                if src != dst and src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(src.read_bytes())

                return True

        return False

    def _generate_mock_stl(self, prompt: str) -> str:
        """
        Generate a mock STL file content.

        Creates a simple cube as placeholder.

        Args:
            prompt: The generation prompt (for comments)

        Returns:
            ASCII STL content
        """
        # Simple cube vertices
        vertices = [
            # Bottom face
            ((0, 0, 0), (10, 0, 0), (10, 10, 0)),
            ((0, 0, 0), (10, 10, 0), (0, 10, 0)),
            # Top face
            ((0, 0, 10), (10, 10, 10), (10, 0, 10)),
            ((0, 0, 10), (0, 10, 10), (10, 10, 10)),
            # Front face
            ((0, 0, 0), (10, 0, 10), (10, 0, 0)),
            ((0, 0, 0), (0, 0, 10), (10, 0, 10)),
            # Back face
            ((0, 10, 0), (10, 10, 0), (10, 10, 10)),
            ((0, 10, 0), (10, 10, 10), (0, 10, 10)),
            # Left face
            ((0, 0, 0), (0, 10, 0), (0, 10, 10)),
            ((0, 0, 0), (0, 10, 10), (0, 0, 10)),
            # Right face
            ((10, 0, 0), (10, 10, 10), (10, 10, 0)),
            ((10, 0, 0), (10, 0, 10), (10, 10, 10)),
        ]

        # Calculate normals for each face
        normals = [
            (0, 0, -1),  # Bottom
            (0, 0, -1),
            (0, 0, 1),   # Top
            (0, 0, 1),
            (0, -1, 0),  # Front
            (0, -1, 0),
            (0, 1, 0),   # Back
            (0, 1, 0),
            (-1, 0, 0),  # Left
            (-1, 0, 0),
            (1, 0, 0),   # Right
            (1, 0, 0),
        ]

        # Generate clean prompt name for solid name
        solid_name = "".join(c if c.isalnum() else "_" for c in prompt[:30])

        lines = [f"solid {solid_name}_mock"]

        for (v1, v2, v3), (nx, ny, nz) in zip(vertices, normals):
            lines.append(f"  facet normal {nx} {ny} {nz}")
            lines.append("    outer loop")
            lines.append(f"      vertex {v1[0]} {v1[1]} {v1[2]}")
            lines.append(f"      vertex {v2[0]} {v2[1]} {v2[2]}")
            lines.append(f"      vertex {v3[0]} {v3[1]} {v3[2]}")
            lines.append("    endloop")
            lines.append("  endfacet")

        lines.append(f"endsolid {solid_name}_mock")

        return "\n".join(lines)
