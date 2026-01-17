"""
Laser Cutting Module for Bambu Lab H2D.

Provides tools for converting 3D models to 2D laser cutting paths,
including cross-sectioning, projection, and export to SVG/DXF formats.
"""

from .cross_section import (
    CrossSectionTool,
    CrossSectionResult,
    create_cross_section,
    create_multiple_sections,
)
from .projection import (
    ProjectionTool,
    ProjectionResult,
    project_to_2d,
    project_outline,
)
from .svg_export import (
    SVGExporter,
    export_to_svg,
    paths_to_svg,
)
from .dxf_export import (
    DXFExporter,
    export_to_dxf,
    paths_to_dxf,
)
from .presets import (
    LaserPreset,
    LASER_PRESETS,
    get_preset,
    get_preset_for_material,
)

__all__ = [
    # Cross Section
    "CrossSectionTool",
    "CrossSectionResult",
    "create_cross_section",
    "create_multiple_sections",
    # Projection
    "ProjectionTool",
    "ProjectionResult",
    "project_to_2d",
    "project_outline",
    # SVG Export
    "SVGExporter",
    "export_to_svg",
    "paths_to_svg",
    # DXF Export
    "DXFExporter",
    "export_to_dxf",
    "paths_to_dxf",
    # Presets
    "LaserPreset",
    "LASER_PRESETS",
    "get_preset",
    "get_preset_for_material",
]
