"""Texture capture module for capturing and applying textures to 3D models.

Provides tools for extracting textures from photographs and
projecting them onto mesh surfaces.
"""

import asyncio
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("capture.texture_capture")


class TextureFormat(str, Enum):
    """Supported texture formats."""
    PNG = "png"
    JPG = "jpg"
    TIFF = "tiff"
    EXR = "exr"


class TextureType(str, Enum):
    """Types of textures that can be captured."""
    DIFFUSE = "diffuse"  # Base color/albedo
    NORMAL = "normal"  # Normal map
    ROUGHNESS = "roughness"  # Roughness map
    METALLIC = "metallic"  # Metallic map
    AO = "ao"  # Ambient occlusion
    HEIGHT = "height"  # Height/displacement map


@dataclass
class TextureConfig:
    """Configuration for texture capture."""
    # Resolution
    width: int = 2048
    height: int = 2048

    # Format
    output_format: TextureFormat = TextureFormat.PNG

    # Types to generate
    texture_types: List[TextureType] = field(
        default_factory=lambda: [TextureType.DIFFUSE]
    )

    # Quality
    quality: int = 95  # JPEG quality

    # UV mapping
    uv_margin: float = 0.01  # Margin for UV islands

    # Processing
    denoise: bool = True
    color_correct: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "width": self.width,
            "height": self.height,
            "output_format": self.output_format.value,
            "texture_types": [t.value for t in self.texture_types],
            "quality": self.quality,
            "uv_margin": self.uv_margin,
            "denoise": self.denoise,
            "color_correct": self.color_correct,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TextureConfig":
        """Create from dictionary."""
        texture_types = data.get("texture_types", ["diffuse"])
        if isinstance(texture_types, list):
            texture_types = [TextureType(t) for t in texture_types]

        return cls(
            width=data.get("width", 2048),
            height=data.get("height", 2048),
            output_format=TextureFormat(data.get("output_format", "png")),
            texture_types=texture_types,
            quality=data.get("quality", 95),
            uv_margin=data.get("uv_margin", 0.01),
            denoise=data.get("denoise", True),
            color_correct=data.get("color_correct", True),
        )


@dataclass
class TextureResult:
    """Result of texture capture operation."""
    success: bool
    texture_paths: Dict[str, str] = field(default_factory=dict)  # type -> path
    mesh_path: Optional[str] = None
    mtl_path: Optional[str] = None  # Material file for OBJ
    resolution: Tuple[int, int] = (0, 0)
    processing_time: float = 0.0
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "texture_paths": self.texture_paths,
            "mesh_path": self.mesh_path,
            "mtl_path": self.mtl_path,
            "resolution": list(self.resolution),
            "processing_time": self.processing_time,
            "error_message": self.error_message,
        }


class TextureCapturer:
    """
    Texture capture and projection system.

    Captures textures from photographs and projects them
    onto 3D mesh surfaces.
    """

    def __init__(
        self,
        config: Optional[TextureConfig] = None,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize texture capturer.

        Args:
            config: Texture capture configuration
            output_dir: Output directory for textures
        """
        self.config = config or TextureConfig()
        settings = get_settings()
        self.output_dir = Path(output_dir or settings.output_dir) / "textures"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def capture_from_images(
        self,
        mesh_path: str,
        image_paths: List[str],
        project_name: Optional[str] = None,
    ) -> TextureResult:
        """
        Capture textures from images and project onto mesh.

        Args:
            mesh_path: Path to the 3D mesh file
            image_paths: List of paths to source images
            project_name: Optional project name

        Returns:
            Texture capture result
        """
        start_time = datetime.now()

        # Validate mesh exists
        mesh = Path(mesh_path)
        if not mesh.exists():
            return TextureResult(
                success=False,
                error_message=f"Mesh file not found: {mesh_path}",
            )

        # Validate images
        valid_images = []
        for img in image_paths:
            p = Path(img)
            if p.exists() and p.suffix.lower() in [".jpg", ".jpeg", ".png", ".tiff", ".tif"]:
                valid_images.append(p)

        if not valid_images:
            return TextureResult(
                success=False,
                error_message="No valid images provided",
            )

        # Create project directory
        project_name = project_name or f"texture_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_dir = self.output_dir / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Generate textures for each type
            texture_paths = {}
            for tex_type in self.config.texture_types:
                texture_path = await self._generate_texture(
                    mesh, valid_images, project_dir, tex_type
                )
                if texture_path:
                    texture_paths[tex_type.value] = str(texture_path)

            # Copy mesh and create MTL file
            mesh_copy = project_dir / f"model{mesh.suffix}"
            shutil.copy2(mesh, mesh_copy)

            mtl_path = None
            if mesh.suffix.lower() == ".obj":
                mtl_path = await self._create_mtl_file(
                    project_dir, texture_paths, mesh_copy.stem
                )

            processing_time = (datetime.now() - start_time).total_seconds()

            return TextureResult(
                success=True,
                texture_paths=texture_paths,
                mesh_path=str(mesh_copy),
                mtl_path=str(mtl_path) if mtl_path else None,
                resolution=(self.config.width, self.config.height),
                processing_time=processing_time,
            )

        except Exception as e:
            logger.error(f"Texture capture error: {e}")
            return TextureResult(
                success=False,
                error_message=str(e),
                processing_time=(datetime.now() - start_time).total_seconds(),
            )

    async def _generate_texture(
        self,
        mesh: Path,
        images: List[Path],
        output_dir: Path,
        texture_type: TextureType,
    ) -> Optional[Path]:
        """Generate a texture of the specified type."""
        ext = self.config.output_format.value
        output_path = output_dir / f"{texture_type.value}.{ext}"

        # Create placeholder texture
        # In production, this would use projection algorithms
        await self._create_placeholder_texture(output_path, texture_type, len(images))

        return output_path

    async def _create_placeholder_texture(
        self,
        output_path: Path,
        texture_type: TextureType,
        image_count: int,
    ) -> None:
        """Create a placeholder texture file."""
        # Create a simple PPM/PGM file that can be converted
        width = self.config.width
        height = self.config.height

        # Generate appropriate color based on texture type
        if texture_type == TextureType.DIFFUSE:
            r, g, b = 200, 200, 200  # Light gray
        elif texture_type == TextureType.NORMAL:
            r, g, b = 128, 128, 255  # Normal map default (pointing up)
        elif texture_type == TextureType.ROUGHNESS:
            r, g, b = 128, 128, 128  # 50% roughness
        elif texture_type == TextureType.METALLIC:
            r, g, b = 0, 0, 0  # Non-metallic
        elif texture_type == TextureType.AO:
            r, g, b = 255, 255, 255  # Full AO
        elif texture_type == TextureType.HEIGHT:
            r, g, b = 128, 128, 128  # Mid-height
        else:
            r, g, b = 128, 128, 128

        # Write PPM and convert or just create a stub
        if output_path.suffix.lower() == ".png":
            # Create minimal PNG stub (valid 1x1 PNG header)
            # This is a simplified placeholder
            png_header = bytes([
                0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
                0x00, 0x00, 0x00, 0x0D,  # IHDR length
                0x49, 0x48, 0x44, 0x52,  # IHDR
                0x00, 0x00, 0x00, 0x01,  # width=1
                0x00, 0x00, 0x00, 0x01,  # height=1
                0x08, 0x02,  # 8-bit RGB
                0x00, 0x00, 0x00,  # compression, filter, interlace
                0x90, 0x77, 0x53, 0xDE,  # CRC
                0x00, 0x00, 0x00, 0x0C,  # IDAT length
                0x49, 0x44, 0x41, 0x54,  # IDAT
                0x08, 0xD7, 0x63, r, g, b, 0x00, 0x00,
                0x00, 0x03, 0x00, 0x01,  # data
                0x00, 0x00, 0x00, 0x00,  # IEND length (placeholder CRC)
                0x49, 0x45, 0x4E, 0x44,  # IEND
                0xAE, 0x42, 0x60, 0x82,  # IEND CRC
            ])
            output_path.write_bytes(png_header)
        else:
            # Write PPM file (simple text format)
            ppm_content = f"P3\n{width} {height}\n255\n"
            ppm_content += f"{r} {g} {b}\n" * (width * height)
            output_path.write_text(ppm_content[:1000])  # Truncated for placeholder

    async def _create_mtl_file(
        self,
        output_dir: Path,
        texture_paths: Dict[str, str],
        material_name: str,
    ) -> Path:
        """Create an MTL material file for OBJ."""
        mtl_path = output_dir / f"{material_name}.mtl"

        mtl_content = f"""# Material file generated by Claude Fab Lab
# Generated: {datetime.now().isoformat()}

newmtl {material_name}
Ns 225.000000
Ka 1.000000 1.000000 1.000000
Ks 0.500000 0.500000 0.500000
Ke 0.000000 0.000000 0.000000
Ni 1.450000
d 1.000000
illum 2
"""

        # Add texture maps
        if "diffuse" in texture_paths:
            mtl_content += f"map_Kd {Path(texture_paths['diffuse']).name}\n"
        if "normal" in texture_paths:
            mtl_content += f"map_Bump {Path(texture_paths['normal']).name}\n"
        if "roughness" in texture_paths:
            mtl_content += f"map_Pr {Path(texture_paths['roughness']).name}\n"
        if "metallic" in texture_paths:
            mtl_content += f"map_Pm {Path(texture_paths['metallic']).name}\n"
        if "ao" in texture_paths:
            mtl_content += f"map_Ka {Path(texture_paths['ao']).name}\n"

        mtl_path.write_text(mtl_content)
        return mtl_path

    async def extract_color_from_image(
        self,
        image_path: str,
        sample_points: Optional[List[Tuple[int, int]]] = None,
    ) -> Dict[str, any]:
        """
        Extract dominant colors from an image.

        Args:
            image_path: Path to the image
            sample_points: Optional specific points to sample

        Returns:
            Dictionary with color information
        """
        img = Path(image_path)
        if not img.exists():
            return {"error": "Image not found"}

        # Placeholder color extraction
        # In production, this would use image processing
        return {
            "dominant_color": [200, 200, 200],
            "palette": [
                [200, 200, 200],
                [180, 180, 180],
                [220, 220, 220],
            ],
            "average_brightness": 0.75,
        }

    def list_projects(self) -> List[dict]:
        """List all texture capture projects."""
        projects = []

        for project_dir in self.output_dir.iterdir():
            if project_dir.is_dir():
                textures = list(project_dir.glob("*.png")) + list(project_dir.glob("*.jpg"))
                projects.append({
                    "name": project_dir.name,
                    "path": str(project_dir),
                    "textures": [t.name for t in textures],
                    "created": datetime.fromtimestamp(project_dir.stat().st_ctime).isoformat(),
                })

        return sorted(projects, key=lambda x: x.get("created", ""), reverse=True)

    def get_project_info(self, project_name: str) -> Optional[dict]:
        """Get information about a texture project."""
        project_dir = self.output_dir / project_name
        if not project_dir.exists():
            return None

        textures = list(project_dir.glob("*.png")) + list(project_dir.glob("*.jpg"))
        meshes = list(project_dir.glob("*.obj")) + list(project_dir.glob("*.stl"))

        return {
            "name": project_name,
            "path": str(project_dir),
            "textures": [str(t) for t in textures],
            "meshes": [str(m) for m in meshes],
            "created": datetime.fromtimestamp(project_dir.stat().st_ctime).isoformat(),
        }

    def delete_project(self, project_name: str) -> bool:
        """Delete a texture project."""
        project_dir = self.output_dir / project_name
        if project_dir.exists():
            shutil.rmtree(project_dir)
            return True
        return False


# Convenience functions
def create_texture_capturer(
    resolution: int = 2048,
    output_format: str = "png",
    output_dir: Optional[str] = None,
) -> TextureCapturer:
    """Create a texture capturer with common settings."""
    config = TextureConfig(
        width=resolution,
        height=resolution,
        output_format=TextureFormat(output_format),
    )
    return TextureCapturer(config=config, output_dir=output_dir)


async def capture_textures(
    mesh_path: str,
    image_paths: List[str],
    texture_types: Optional[List[str]] = None,
    resolution: int = 2048,
    project_name: Optional[str] = None,
) -> TextureResult:
    """
    Convenience function to capture textures.

    Args:
        mesh_path: Path to the mesh file
        image_paths: List of source image paths
        texture_types: Types of textures to generate
        resolution: Texture resolution
        project_name: Optional project name

    Returns:
        Texture capture result
    """
    types = [TextureType(t) for t in (texture_types or ["diffuse"])]
    config = TextureConfig(
        width=resolution,
        height=resolution,
        texture_types=types,
    )
    capturer = TextureCapturer(config=config)
    return await capturer.capture_from_images(mesh_path, image_paths, project_name)
