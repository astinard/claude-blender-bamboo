"""
Blender model exporter for 3D printing.

Exports Blender scenes/objects to STL and 3MF formats suitable for 3D printing.
"""

from pathlib import Path
from typing import Optional, List, Union

try:
    import bpy
    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False
    bpy = None


def check_blender():
    """Check if running inside Blender."""
    if not BLENDER_AVAILABLE:
        raise RuntimeError(
            "This module must be run inside Blender. "
            "Use: blender --background --python script.py"
        )


def export_stl(
    filepath: Union[str, Path],
    objects: Optional[List] = None,
    scale: float = 1.0,
    apply_modifiers: bool = True,
    ascii_format: bool = False
) -> Path:
    """
    Export selected or all objects to STL format.

    Args:
        filepath: Output file path (.stl)
        objects: List of objects to export (None = all mesh objects)
        scale: Scale factor for export
        apply_modifiers: Whether to apply modifiers before export
        ascii_format: Export as ASCII STL (larger file, human readable)

    Returns:
        Path to the exported file
    """
    check_blender()

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Ensure .stl extension
    if filepath.suffix.lower() != '.stl':
        filepath = filepath.with_suffix('.stl')

    # Select objects to export
    bpy.ops.object.select_all(action='DESELECT')

    if objects is None:
        # Export all mesh objects
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                obj.select_set(True)
    else:
        for obj in objects:
            if obj.type == 'MESH':
                obj.select_set(True)

    # Export
    bpy.ops.wm.stl_export(
        filepath=str(filepath),
        export_selected_objects=True,
        global_scale=scale,
        apply_modifiers=apply_modifiers,
        ascii_format=ascii_format
    )

    return filepath


def export_obj(
    filepath: Union[str, Path],
    objects: Optional[List] = None,
    scale: float = 1.0,
    apply_modifiers: bool = True
) -> Path:
    """
    Export selected or all objects to OBJ format.

    Args:
        filepath: Output file path (.obj)
        objects: List of objects to export (None = all mesh objects)
        scale: Scale factor for export
        apply_modifiers: Whether to apply modifiers before export

    Returns:
        Path to the exported file
    """
    check_blender()

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if filepath.suffix.lower() != '.obj':
        filepath = filepath.with_suffix('.obj')

    bpy.ops.object.select_all(action='DESELECT')

    if objects is None:
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                obj.select_set(True)
    else:
        for obj in objects:
            if obj.type == 'MESH':
                obj.select_set(True)

    bpy.ops.wm.obj_export(
        filepath=str(filepath),
        export_selected_objects=True,
        global_scale=scale,
        apply_modifiers=apply_modifiers
    )

    return filepath


def export_ply(
    filepath: Union[str, Path],
    objects: Optional[List] = None,
    scale: float = 1.0,
    apply_modifiers: bool = True,
    ascii_format: bool = False
) -> Path:
    """
    Export selected or all objects to PLY format.

    Args:
        filepath: Output file path (.ply)
        objects: List of objects to export (None = all mesh objects)
        scale: Scale factor for export
        apply_modifiers: Whether to apply modifiers before export
        ascii_format: Export as ASCII PLY

    Returns:
        Path to the exported file
    """
    check_blender()

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if filepath.suffix.lower() != '.ply':
        filepath = filepath.with_suffix('.ply')

    bpy.ops.object.select_all(action='DESELECT')

    if objects is None:
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                obj.select_set(True)
    else:
        for obj in objects:
            if obj.type == 'MESH':
                obj.select_set(True)

    bpy.ops.wm.ply_export(
        filepath=str(filepath),
        export_selected_objects=True,
        global_scale=scale,
        apply_modifiers=apply_modifiers,
        ascii_format=ascii_format
    )

    return filepath


def export_for_printing(
    filepath: Union[str, Path],
    format: str = "stl",
    objects: Optional[List] = None,
    scale: float = 1.0,
    apply_modifiers: bool = True
) -> Path:
    """
    High-level export function for 3D printing.

    Automatically handles format selection and common settings.

    Args:
        filepath: Output file path
        format: Export format ("stl", "obj", "ply")
        objects: Objects to export (None = all mesh objects)
        scale: Scale factor (1.0 = millimeters if modeling in mm)
        apply_modifiers: Apply modifiers before export

    Returns:
        Path to exported file
    """
    check_blender()

    format = format.lower()

    if format == "stl":
        return export_stl(
            filepath=filepath,
            objects=objects,
            scale=scale,
            apply_modifiers=apply_modifiers,
            ascii_format=False  # Binary is more compact
        )
    elif format == "obj":
        return export_obj(
            filepath=filepath,
            objects=objects,
            scale=scale,
            apply_modifiers=apply_modifiers
        )
    elif format == "ply":
        return export_ply(
            filepath=filepath,
            objects=objects,
            scale=scale,
            apply_modifiers=apply_modifiers,
            ascii_format=False
        )
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'stl', 'obj', or 'ply'.")


def get_export_stats(filepath: Union[str, Path]) -> dict:
    """
    Get statistics about an exported file.

    Args:
        filepath: Path to the exported file

    Returns:
        Dictionary with file statistics
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    stats = {
        "path": str(filepath),
        "name": filepath.name,
        "format": filepath.suffix.lower().lstrip('.'),
        "size_bytes": filepath.stat().st_size,
        "size_mb": filepath.stat().st_size / (1024 * 1024),
    }

    return stats
