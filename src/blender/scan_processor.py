"""
LiDAR scan processor for importing and processing 3D scans.

Handles STL/OBJ imports from iOS LiDAR apps like Polycam, 3D Scanner App,
KIRI Engine, Scaniverse, and Heges.

Features:
- Import scanned meshes
- Analyze dimensions and measurements
- Repair common scan issues (holes, non-manifold edges)
- Scale to real-world dimensions
- Prepare for 3D printing
"""

from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

try:
    import bpy
    import bmesh
    from mathutils import Vector, Matrix
    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False
    bpy = None
    bmesh = None
    Vector = None
    Matrix = None


def check_blender():
    """Check if running inside Blender."""
    if not BLENDER_AVAILABLE:
        raise RuntimeError(
            "This module must be run inside Blender. "
            "Use: blender --background --python script.py"
        )


class ScanSource(Enum):
    """Source app for the scan."""
    POLYCAM = "polycam"
    SCANNER_APP = "3d_scanner_app"
    KIRI_ENGINE = "kiri_engine"
    SCANIVERSE = "scaniverse"
    HEGES = "heges"
    UNKNOWN = "unknown"


@dataclass
class ScanDimensions:
    """Dimensions of a scanned object."""
    width: float   # X axis (mm)
    height: float  # Z axis (mm)
    depth: float   # Y axis (mm)
    volume: float  # mm³
    surface_area: float  # mm²
    bounding_box_min: Tuple[float, float, float]
    bounding_box_max: Tuple[float, float, float]
    center: Tuple[float, float, float]

    def to_dict(self) -> Dict:
        return {
            "width_mm": self.width,
            "height_mm": self.height,
            "depth_mm": self.depth,
            "volume_mm3": self.volume,
            "surface_area_mm2": self.surface_area,
            "bounding_box_min": self.bounding_box_min,
            "bounding_box_max": self.bounding_box_max,
            "center": self.center,
        }


@dataclass
class ScanAnalysis:
    """Complete analysis of a scanned mesh."""
    filename: str
    dimensions: ScanDimensions
    vertex_count: int
    face_count: int
    is_manifold: bool
    is_watertight: bool
    has_holes: bool
    hole_count: int
    non_manifold_edges: int
    loose_vertices: int
    needs_repair: bool
    estimated_print_time_min: float  # Very rough estimate
    estimated_material_g: float
    issues: List[str]

    def to_dict(self) -> Dict:
        return {
            "filename": self.filename,
            "dimensions": self.dimensions.to_dict(),
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "is_manifold": self.is_manifold,
            "is_watertight": self.is_watertight,
            "has_holes": self.has_holes,
            "hole_count": self.hole_count,
            "non_manifold_edges": self.non_manifold_edges,
            "loose_vertices": self.loose_vertices,
            "needs_repair": self.needs_repair,
            "estimated_print_time_min": self.estimated_print_time_min,
            "estimated_material_g": self.estimated_material_g,
            "issues": self.issues,
        }


def import_scan(
    filepath: Path,
    scale: float = 1.0,
    center_origin: bool = True,
    place_on_ground: bool = True
) -> "bpy.types.Object":
    """
    Import a scanned mesh file (STL, OBJ, PLY).

    Args:
        filepath: Path to scan file
        scale: Scale factor (1.0 = assume millimeters)
        center_origin: Center the object at origin
        place_on_ground: Place bottom of object at Z=0

    Returns:
        Imported Blender object
    """
    check_blender()

    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Scan file not found: {filepath}")

    suffix = filepath.suffix.lower()

    # Clear selection
    bpy.ops.object.select_all(action='DESELECT')

    # Import based on format
    if suffix == '.stl':
        bpy.ops.wm.stl_import(filepath=str(filepath))
    elif suffix == '.obj':
        bpy.ops.wm.obj_import(filepath=str(filepath))
    elif suffix == '.ply':
        bpy.ops.wm.ply_import(filepath=str(filepath))
    elif suffix == '.fbx':
        bpy.ops.import_scene.fbx(filepath=str(filepath))
    elif suffix == '.gltf' or suffix == '.glb':
        bpy.ops.import_scene.gltf(filepath=str(filepath))
    else:
        raise ValueError(f"Unsupported format: {suffix}")

    # Get imported object
    obj = bpy.context.selected_objects[0] if bpy.context.selected_objects else bpy.context.active_object

    if obj is None:
        raise RuntimeError("Failed to import scan")

    obj.name = f"Scan_{filepath.stem}"

    # Apply scale
    if scale != 1.0:
        obj.scale = (scale, scale, scale)
        bpy.ops.object.transform_apply(scale=True)

    # Center origin
    if center_origin:
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

    # Place on ground
    if place_on_ground:
        # Get lowest point
        min_z = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
        obj.location.z -= min_z
        obj.location.x = 0
        obj.location.y = 0

    return obj


def analyze_scan(obj: "bpy.types.Object") -> ScanAnalysis:
    """
    Analyze a scanned mesh for dimensions and printability.

    Args:
        obj: Blender mesh object

    Returns:
        ScanAnalysis with detailed information
    """
    check_blender()

    if obj.type != 'MESH':
        raise ValueError(f"Object is not a mesh: {obj.type}")

    mesh = obj.data
    issues = []

    # Create BMesh for analysis
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Counts
    vertex_count = len(bm.verts)
    face_count = len(bm.faces)

    # Check for issues
    non_manifold_edges = [e for e in bm.edges if not e.is_manifold]
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    loose_verts = [v for v in bm.verts if not v.link_edges]

    non_manifold_count = len(non_manifold_edges)
    hole_count = len(boundary_edges) // 2  # Rough estimate
    loose_count = len(loose_verts)

    is_manifold = non_manifold_count == 0
    is_watertight = len(boundary_edges) == 0
    has_holes = not is_watertight

    if non_manifold_count > 0:
        issues.append(f"{non_manifold_count} non-manifold edges")
    if has_holes:
        issues.append(f"~{hole_count} holes in mesh")
    if loose_count > 0:
        issues.append(f"{loose_count} loose vertices")

    needs_repair = len(issues) > 0

    # Calculate volume and surface area
    volume = abs(bm.calc_volume())
    surface_area = sum(f.calc_area() for f in bm.faces)

    bm.free()

    # Get dimensions
    dims = obj.dimensions
    bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]

    min_corner = (
        min(v.x for v in bbox),
        min(v.y for v in bbox),
        min(v.z for v in bbox)
    )
    max_corner = (
        max(v.x for v in bbox),
        max(v.y for v in bbox),
        max(v.z for v in bbox)
    )
    center = (
        (min_corner[0] + max_corner[0]) / 2,
        (min_corner[1] + max_corner[1]) / 2,
        (min_corner[2] + max_corner[2]) / 2
    )

    dimensions = ScanDimensions(
        width=dims.x,
        height=dims.z,
        depth=dims.y,
        volume=volume,
        surface_area=surface_area,
        bounding_box_min=min_corner,
        bounding_box_max=max_corner,
        center=center
    )

    # Rough print estimates (assuming 50mm³/min print speed, PLA density 1.24g/cm³)
    volume_cm3 = volume / 1000
    print_time = volume / 50  # minutes
    material_g = volume_cm3 * 1.24 * 1.2  # 20% infill factor

    return ScanAnalysis(
        filename=obj.name,
        dimensions=dimensions,
        vertex_count=vertex_count,
        face_count=face_count,
        is_manifold=is_manifold,
        is_watertight=is_watertight,
        has_holes=has_holes,
        hole_count=hole_count,
        non_manifold_edges=non_manifold_count,
        loose_vertices=loose_count,
        needs_repair=needs_repair,
        estimated_print_time_min=print_time,
        estimated_material_g=material_g,
        issues=issues
    )


def repair_scan(
    obj: "bpy.types.Object",
    fill_holes: bool = True,
    remove_doubles: bool = True,
    merge_distance: float = 0.001,
    recalc_normals: bool = True,
    smooth_iterations: int = 0
) -> Dict[str, Any]:
    """
    Repair common issues in scanned meshes.

    Args:
        obj: Blender mesh object
        fill_holes: Fill holes in the mesh
        remove_doubles: Merge duplicate vertices
        merge_distance: Distance threshold for merging
        recalc_normals: Recalculate face normals
        smooth_iterations: Smoothing passes (0 = none)

    Returns:
        Dictionary with repair statistics
    """
    check_blender()

    stats = {
        "vertices_removed": 0,
        "holes_filled": 0,
        "normals_fixed": False,
        "smoothing_applied": smooth_iterations > 0
    }

    # Select and activate object
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Enter edit mode
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')

    # Count initial vertices
    initial_verts = len(obj.data.vertices)

    # Remove doubles
    if remove_doubles:
        bpy.ops.mesh.remove_doubles(threshold=merge_distance)

    # Fill holes
    if fill_holes:
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_non_manifold(extend=False)

        # Count boundary edges before filling
        bpy.ops.object.mode_set(mode='OBJECT')
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        holes_before = len([e for e in bm.edges if e.is_boundary])
        bm.free()
        bpy.ops.object.mode_set(mode='EDIT')

        try:
            bpy.ops.mesh.fill_holes(sides=100)
        except RuntimeError:
            pass  # Some holes may not be fillable

        # Count after
        bpy.ops.object.mode_set(mode='OBJECT')
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        holes_after = len([e for e in bm.edges if e.is_boundary])
        bm.free()
        bpy.ops.object.mode_set(mode='EDIT')

        stats["holes_filled"] = (holes_before - holes_after) // 2

    # Recalculate normals
    if recalc_normals:
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        stats["normals_fixed"] = True

    # Smoothing
    if smooth_iterations > 0:
        bpy.ops.mesh.select_all(action='SELECT')
        for _ in range(smooth_iterations):
            bpy.ops.mesh.vertices_smooth(factor=0.5)

    bpy.ops.object.mode_set(mode='OBJECT')

    # Count final vertices
    final_verts = len(obj.data.vertices)
    stats["vertices_removed"] = initial_verts - final_verts

    return stats


def scale_to_real_dimensions(
    obj: "bpy.types.Object",
    target_width: Optional[float] = None,
    target_height: Optional[float] = None,
    target_depth: Optional[float] = None,
    uniform: bool = True
) -> Tuple[float, float, float]:
    """
    Scale scan to match real-world dimensions.

    If uniform=True, scales uniformly based on whichever dimension is specified.
    If multiple dimensions are given with uniform=True, uses the average scale.

    Args:
        obj: Blender mesh object
        target_width: Desired X dimension (mm)
        target_height: Desired Z dimension (mm)
        target_depth: Desired Y dimension (mm)
        uniform: Scale uniformly to maintain proportions

    Returns:
        Final dimensions (width, height, depth)
    """
    check_blender()

    current_dims = obj.dimensions

    scales = []
    if target_width is not None and current_dims.x > 0:
        scales.append(('x', target_width / current_dims.x))
    if target_height is not None and current_dims.z > 0:
        scales.append(('z', target_height / current_dims.z))
    if target_depth is not None and current_dims.y > 0:
        scales.append(('y', target_depth / current_dims.y))

    if not scales:
        return tuple(current_dims)

    if uniform:
        # Use average scale factor
        avg_scale = sum(s[1] for s in scales) / len(scales)
        obj.scale = (avg_scale, avg_scale, avg_scale)
    else:
        # Scale each axis independently
        scale_x = next((s[1] for s in scales if s[0] == 'x'), 1.0)
        scale_y = next((s[1] for s in scales if s[0] == 'y'), 1.0)
        scale_z = next((s[1] for s in scales if s[0] == 'z'), 1.0)
        obj.scale = (scale_x, scale_y, scale_z)

    # Apply scale
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(scale=True)

    return tuple(obj.dimensions)


def decimate_scan(
    obj: "bpy.types.Object",
    target_faces: Optional[int] = None,
    ratio: Optional[float] = None
) -> int:
    """
    Reduce polygon count of scan for faster processing.

    Args:
        obj: Blender mesh object
        target_faces: Target number of faces
        ratio: Decimation ratio (0.5 = half the faces)

    Returns:
        Final face count
    """
    check_blender()

    initial_faces = len(obj.data.polygons)

    if target_faces is not None:
        ratio = target_faces / initial_faces
    elif ratio is None:
        ratio = 0.5

    ratio = max(0.01, min(1.0, ratio))

    # Add decimate modifier
    modifier = obj.modifiers.new(name="Decimate", type='DECIMATE')
    modifier.ratio = ratio
    modifier.use_collapse_triangulate = True

    # Apply modifier
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)

    return len(obj.data.polygons)


def hollow_scan(
    obj: "bpy.types.Object",
    wall_thickness: float = 2.0
) -> "bpy.types.Object":
    """
    Create a hollow version of the scan (for reducing material usage).

    Args:
        obj: Blender mesh object
        wall_thickness: Wall thickness in mm

    Returns:
        Hollowed object
    """
    check_blender()

    # Add solidify modifier for uniform wall thickness
    modifier = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
    modifier.thickness = -wall_thickness  # Inward
    modifier.offset = 1.0  # Keep outer surface
    modifier.use_rim = True
    modifier.use_rim_only = False

    # Apply
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)

    return obj
