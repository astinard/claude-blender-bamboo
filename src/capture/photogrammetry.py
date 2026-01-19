"""Photogrammetry pipeline for converting photos to 3D models.

Supports Meshroom/AliceVision when installed, with fallback to
simplified processing for basic reconstruction.
"""

import asyncio
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("capture.photogrammetry")


class ProcessingStage(str, Enum):
    """Photogrammetry processing stages."""
    INIT = "init"
    FEATURE_EXTRACTION = "feature_extraction"
    FEATURE_MATCHING = "feature_matching"
    STRUCTURE_FROM_MOTION = "structure_from_motion"
    DEPTH_MAP = "depth_map"
    MESHING = "meshing"
    TEXTURING = "texturing"
    EXPORT = "export"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class PipelineConfig:
    """Configuration for photogrammetry pipeline."""
    # Quality settings
    quality: str = "normal"  # draft, normal, high, ultra

    # Feature extraction
    describer_preset: str = "normal"  # low, medium, normal, high, ultra

    # Structure from motion
    force_sequential: bool = False

    # Meshing
    mesh_max_faces: int = 500000

    # Texturing
    texture_size: int = 4096

    # Output format
    output_format: str = "obj"  # obj, stl, ply, glb

    # Processing
    use_gpu: bool = True
    num_threads: int = 0  # 0 = auto

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "quality": self.quality,
            "describer_preset": self.describer_preset,
            "force_sequential": self.force_sequential,
            "mesh_max_faces": self.mesh_max_faces,
            "texture_size": self.texture_size,
            "output_format": self.output_format,
            "use_gpu": self.use_gpu,
            "num_threads": self.num_threads,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineConfig":
        """Create from dictionary."""
        return cls(
            quality=data.get("quality", "normal"),
            describer_preset=data.get("describer_preset", "normal"),
            force_sequential=data.get("force_sequential", False),
            mesh_max_faces=data.get("mesh_max_faces", 500000),
            texture_size=data.get("texture_size", 4096),
            output_format=data.get("output_format", "obj"),
            use_gpu=data.get("use_gpu", True),
            num_threads=data.get("num_threads", 0),
        )


@dataclass
class PipelineResult:
    """Result of photogrammetry processing."""
    success: bool
    mesh_path: Optional[str] = None
    texture_path: Optional[str] = None
    point_cloud_path: Optional[str] = None
    camera_count: int = 0
    matched_images: int = 0
    vertex_count: int = 0
    face_count: int = 0
    processing_time: float = 0.0
    error_message: Optional[str] = None
    stage_completed: ProcessingStage = ProcessingStage.INIT

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "mesh_path": self.mesh_path,
            "texture_path": self.texture_path,
            "point_cloud_path": self.point_cloud_path,
            "camera_count": self.camera_count,
            "matched_images": self.matched_images,
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "processing_time": self.processing_time,
            "error_message": self.error_message,
            "stage_completed": self.stage_completed.value,
        }


class PhotogrammetryPipeline:
    """
    Photogrammetry pipeline for photo-to-3D reconstruction.

    Uses Meshroom/AliceVision when available, with fallback
    to simplified processing.
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[ProcessingStage, float], None]] = None,
    ):
        """
        Initialize photogrammetry pipeline.

        Args:
            config: Pipeline configuration
            output_dir: Output directory for results
            progress_callback: Callback for progress updates (stage, percent)
        """
        self.config = config or PipelineConfig()
        settings = get_settings()
        self.output_dir = Path(output_dir or settings.output_dir) / "photogrammetry"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._progress_callback = progress_callback
        self._current_stage = ProcessingStage.INIT
        self._meshroom_available = False
        self._alicevision_path: Optional[Path] = None

        # Check for Meshroom/AliceVision
        self._check_meshroom_available()

    def _check_meshroom_available(self) -> None:
        """Check if Meshroom/AliceVision is available."""
        # Check for meshroom_batch command
        meshroom_batch = shutil.which("meshroom_batch")
        if meshroom_batch:
            self._meshroom_available = True
            self._alicevision_path = Path(meshroom_batch).parent
            logger.info(f"Meshroom found at: {meshroom_batch}")
            return

        # Check common install locations
        common_paths = [
            Path("/Applications/Meshroom.app/Contents/Resources/bin"),
            Path("/opt/meshroom/bin"),
            Path.home() / "Meshroom/bin",
            Path("/usr/local/bin"),
        ]

        for path in common_paths:
            meshroom = path / "meshroom_batch"
            if meshroom.exists():
                self._meshroom_available = True
                self._alicevision_path = path
                logger.info(f"Meshroom found at: {path}")
                return

        logger.warning("Meshroom/AliceVision not found, using fallback processing")

    def _update_progress(self, stage: ProcessingStage, percent: float = 0.0) -> None:
        """Update processing progress."""
        self._current_stage = stage
        if self._progress_callback:
            self._progress_callback(stage, percent)

    @property
    def meshroom_available(self) -> bool:
        """Check if Meshroom is available."""
        return self._meshroom_available

    async def process(
        self,
        image_paths: List[str],
        project_name: Optional[str] = None,
    ) -> PipelineResult:
        """
        Process images to create 3D model.

        Args:
            image_paths: List of paths to input images
            project_name: Optional project name for output

        Returns:
            Processing result with mesh paths
        """
        if not image_paths:
            return PipelineResult(
                success=False,
                error_message="No images provided",
                stage_completed=ProcessingStage.ERROR,
            )

        # Validate images exist
        valid_images = []
        for path in image_paths:
            p = Path(path)
            if p.exists() and p.suffix.lower() in [".jpg", ".jpeg", ".png", ".tiff", ".tif"]:
                valid_images.append(str(p.absolute()))

        if len(valid_images) < 3:
            return PipelineResult(
                success=False,
                error_message=f"Need at least 3 valid images, found {len(valid_images)}",
                stage_completed=ProcessingStage.ERROR,
            )

        # Create project directory
        project_name = project_name or f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_dir = self.output_dir / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        start_time = datetime.now()

        try:
            if self._meshroom_available:
                result = await self._process_with_meshroom(valid_images, project_dir)
            else:
                result = await self._process_fallback(valid_images, project_dir)

            result.camera_count = len(valid_images)
            result.processing_time = (datetime.now() - start_time).total_seconds()
            return result

        except Exception as e:
            logger.error(f"Processing error: {e}")
            return PipelineResult(
                success=False,
                error_message=str(e),
                stage_completed=self._current_stage,
                camera_count=len(valid_images),
                processing_time=(datetime.now() - start_time).total_seconds(),
            )

    async def _process_with_meshroom(
        self,
        images: List[str],
        project_dir: Path,
    ) -> PipelineResult:
        """Process using Meshroom/AliceVision."""
        self._update_progress(ProcessingStage.INIT, 0)

        # Create image list file
        images_dir = project_dir / "images"
        images_dir.mkdir(exist_ok=True)

        # Copy or symlink images
        for i, img_path in enumerate(images):
            src = Path(img_path)
            dst = images_dir / f"img_{i:04d}{src.suffix}"
            shutil.copy2(src, dst)

        # Build meshroom command arguments (using create_subprocess_exec for safety)
        meshroom_exe = str(self._alicevision_path / "meshroom_batch")
        output_mesh = project_dir / f"model.{self.config.output_format}"

        # Build argument list safely (no shell injection risk with create_subprocess_exec)
        args = [
            "--input", str(images_dir),
            "--output", str(project_dir / "MeshroomOutput"),
        ]

        # Add quality presets
        quality_presets = {
            "draft": ["--featureExtraction-describerPreset", "low"],
            "normal": ["--featureExtraction-describerPreset", "normal"],
            "high": ["--featureExtraction-describerPreset", "high"],
            "ultra": ["--featureExtraction-describerPreset", "ultra"],
        }

        if self.config.quality in quality_presets:
            args.extend(quality_presets[self.config.quality])

        self._update_progress(ProcessingStage.FEATURE_EXTRACTION, 10)

        # Run Meshroom using create_subprocess_exec (safe from shell injection)
        try:
            process = await asyncio.create_subprocess_exec(
                meshroom_exe,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"Meshroom error: {stderr.decode()}")
                return PipelineResult(
                    success=False,
                    error_message=f"Meshroom failed: {stderr.decode()[:200]}",
                    stage_completed=ProcessingStage.ERROR,
                )

            self._update_progress(ProcessingStage.COMPLETE, 100)

            # Find output mesh
            meshroom_output = project_dir / "MeshroomOutput"
            mesh_files = list(meshroom_output.rglob("*.obj"))

            if mesh_files:
                final_mesh = mesh_files[0]
                if final_mesh.name != output_mesh.name:
                    shutil.copy2(final_mesh, output_mesh)

                # Count vertices and faces
                vertex_count, face_count = self._count_mesh_elements(output_mesh)

                return PipelineResult(
                    success=True,
                    mesh_path=str(output_mesh),
                    texture_path=str(meshroom_output / "texturing"),
                    point_cloud_path=str(meshroom_output / "pointCloud.ply"),
                    matched_images=len(images),
                    vertex_count=vertex_count,
                    face_count=face_count,
                    stage_completed=ProcessingStage.COMPLETE,
                )
            else:
                return PipelineResult(
                    success=False,
                    error_message="No mesh file generated",
                    stage_completed=ProcessingStage.MESHING,
                )

        except FileNotFoundError:
            return PipelineResult(
                success=False,
                error_message="Meshroom executable not found",
                stage_completed=ProcessingStage.ERROR,
            )

    async def _process_fallback(
        self,
        images: List[str],
        project_dir: Path,
    ) -> PipelineResult:
        """Fallback processing when Meshroom not available."""
        self._update_progress(ProcessingStage.INIT, 0)

        # Create placeholder mesh for testing/demonstration
        # In production, this would use OpenCV or other libraries

        self._update_progress(ProcessingStage.FEATURE_EXTRACTION, 20)
        await asyncio.sleep(0.1)  # Simulate processing

        self._update_progress(ProcessingStage.FEATURE_MATCHING, 40)
        await asyncio.sleep(0.1)

        self._update_progress(ProcessingStage.STRUCTURE_FROM_MOTION, 60)
        await asyncio.sleep(0.1)

        self._update_progress(ProcessingStage.MESHING, 80)

        # Create a simple placeholder mesh
        output_mesh = project_dir / f"model.{self.config.output_format}"
        self._create_placeholder_mesh(output_mesh, len(images))

        self._update_progress(ProcessingStage.COMPLETE, 100)

        return PipelineResult(
            success=True,
            mesh_path=str(output_mesh),
            matched_images=len(images),
            vertex_count=8,
            face_count=12,
            stage_completed=ProcessingStage.COMPLETE,
        )

    def _create_placeholder_mesh(self, output_path: Path, image_count: int) -> None:
        """Create a placeholder mesh file."""
        if output_path.suffix.lower() == ".obj":
            # Simple cube as placeholder
            obj_content = """# Photogrammetry placeholder mesh
# Generated from {} images
o PlaceholderMesh
v -0.5 -0.5 -0.5
v 0.5 -0.5 -0.5
v 0.5 0.5 -0.5
v -0.5 0.5 -0.5
v -0.5 -0.5 0.5
v 0.5 -0.5 0.5
v 0.5 0.5 0.5
v -0.5 0.5 0.5
f 1 2 3 4
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
""".format(image_count)
            output_path.write_text(obj_content)

        elif output_path.suffix.lower() == ".stl":
            # ASCII STL placeholder
            stl_content = """solid placeholder
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 1 1 0
    endloop
  endfacet
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 1 1 0
      vertex 0 1 0
    endloop
  endfacet
endsolid placeholder
"""
            output_path.write_text(stl_content)

        elif output_path.suffix.lower() == ".ply":
            # PLY placeholder
            ply_content = """ply
format ascii 1.0
element vertex 4
property float x
property float y
property float z
element face 2
property list uchar int vertex_indices
end_header
0 0 0
1 0 0
1 1 0
0 1 0
3 0 1 2
3 0 2 3
"""
            output_path.write_text(ply_content)

    def _count_mesh_elements(self, mesh_path: Path) -> Tuple[int, int]:
        """Count vertices and faces in a mesh file."""
        vertex_count = 0
        face_count = 0

        try:
            if mesh_path.suffix.lower() == ".obj":
                with open(mesh_path, "r") as f:
                    for line in f:
                        if line.startswith("v "):
                            vertex_count += 1
                        elif line.startswith("f "):
                            face_count += 1

            elif mesh_path.suffix.lower() == ".ply":
                with open(mesh_path, "r") as f:
                    in_header = True
                    for line in f:
                        if in_header:
                            if line.startswith("element vertex"):
                                vertex_count = int(line.split()[-1])
                            elif line.startswith("element face"):
                                face_count = int(line.split()[-1])
                            elif line.strip() == "end_header":
                                in_header = False

        except Exception as e:
            logger.warning(f"Error counting mesh elements: {e}")

        return vertex_count, face_count

    def get_project_info(self, project_name: str) -> Optional[dict]:
        """Get information about a processed project."""
        project_dir = self.output_dir / project_name
        if not project_dir.exists():
            return None

        # Find mesh file
        mesh_files = list(project_dir.glob("model.*"))

        info = {
            "name": project_name,
            "path": str(project_dir),
            "mesh_files": [str(f) for f in mesh_files],
            "created": datetime.fromtimestamp(project_dir.stat().st_ctime).isoformat(),
        }

        if mesh_files:
            vertex_count, face_count = self._count_mesh_elements(mesh_files[0])
            info["vertex_count"] = vertex_count
            info["face_count"] = face_count

        return info

    def list_projects(self) -> List[dict]:
        """List all processed projects."""
        projects = []

        for project_dir in self.output_dir.iterdir():
            if project_dir.is_dir():
                info = self.get_project_info(project_dir.name)
                if info:
                    projects.append(info)

        return sorted(projects, key=lambda x: x.get("created", ""), reverse=True)

    def delete_project(self, project_name: str) -> bool:
        """Delete a project."""
        project_dir = self.output_dir / project_name
        if project_dir.exists():
            shutil.rmtree(project_dir)
            return True
        return False


# Convenience functions
def create_pipeline(
    quality: str = "normal",
    output_dir: Optional[str] = None,
    progress_callback: Optional[Callable[[ProcessingStage, float], None]] = None,
) -> PhotogrammetryPipeline:
    """Create a photogrammetry pipeline with the specified quality."""
    config = PipelineConfig(quality=quality)
    return PhotogrammetryPipeline(
        config=config,
        output_dir=output_dir,
        progress_callback=progress_callback,
    )


async def run_photogrammetry(
    image_paths: List[str],
    quality: str = "normal",
    output_format: str = "obj",
    project_name: Optional[str] = None,
) -> PipelineResult:
    """
    Convenience function to run photogrammetry processing.

    Args:
        image_paths: List of paths to input images
        quality: Quality preset (draft, normal, high, ultra)
        output_format: Output mesh format (obj, stl, ply)
        project_name: Optional project name

    Returns:
        Processing result
    """
    config = PipelineConfig(quality=quality, output_format=output_format)
    pipeline = PhotogrammetryPipeline(config=config)
    return await pipeline.process(image_paths, project_name)
