"""
Materials module for Claude Fab Lab.

Provides comprehensive material database for 3D printing filaments
and laser-cuttable sheet materials.
"""

from .library import (
    # Types
    MaterialType,
    MaterialProperty,
    FilamentMaterial,
    SheetMaterial,
    # Databases
    FILAMENTS,
    SHEETS,
    MATERIAL_ALIASES,
    COLOR_ALIASES,
    # Functions
    get_material,
    find_material,
    get_color,
    list_filaments,
    list_sheets,
    get_materials_by_property,
    suggest_material,
)

__all__ = [
    # Types
    "MaterialType",
    "MaterialProperty",
    "FilamentMaterial",
    "SheetMaterial",
    # Databases
    "FILAMENTS",
    "SHEETS",
    "MATERIAL_ALIASES",
    "COLOR_ALIASES",
    # Functions
    "get_material",
    "find_material",
    "get_color",
    "list_filaments",
    "list_sheets",
    "get_materials_by_property",
    "suggest_material",
]
