"""Capture module for photogrammetry and texture capture.

Provides tools for converting photos to 3D models and capturing textures.
"""

from src.capture.photogrammetry import (
    PhotogrammetryPipeline,
    PipelineConfig,
    PipelineResult,
    ProcessingStage,
    create_pipeline,
    run_photogrammetry,
)
from src.capture.texture_capture import (
    TextureCapturer,
    TextureConfig,
    TextureResult,
    TextureFormat,
    TextureType,
    create_texture_capturer,
    capture_textures,
)
from src.capture.scan_importer import (
    ScanImporter,
    ImportedScan,
    PolycamIntegration,
    create_importer,
)

__all__ = [
    # Photogrammetry
    "PhotogrammetryPipeline",
    "PipelineConfig",
    "PipelineResult",
    "ProcessingStage",
    "create_pipeline",
    "run_photogrammetry",
    # Texture capture
    "TextureCapturer",
    "TextureConfig",
    "TextureResult",
    "TextureFormat",
    "TextureType",
    "create_texture_capturer",
    "capture_textures",
    # Scan importer
    "ScanImporter",
    "ImportedScan",
    "PolycamIntegration",
    "create_importer",
]
