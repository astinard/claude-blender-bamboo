"""Materials management for Claude Fab Lab."""

from src.materials.material_db import (
    Material,
    MaterialType,
    MaterialProperties,
    get_material,
    get_materials_by_type,
    MATERIAL_DATABASE,
)
from src.materials.compatibility import (
    CompatibilityResult,
    CompatibilityLevel,
    check_compatibility,
    check_multi_material_compatibility,
    get_ams_recommendations,
)
from src.materials.inventory import (
    Spool,
    InventoryManager,
)

__all__ = [
    "Material",
    "MaterialType",
    "MaterialProperties",
    "get_material",
    "get_materials_by_type",
    "MATERIAL_DATABASE",
    "CompatibilityResult",
    "CompatibilityLevel",
    "check_compatibility",
    "check_multi_material_compatibility",
    "get_ams_recommendations",
    "Spool",
    "InventoryManager",
]
