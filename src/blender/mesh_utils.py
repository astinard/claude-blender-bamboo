"""
Blender mesh utilities for 3D printing preparation.

Provides mesh analysis, validation, and repair functions
to ensure models are printable.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    import bpy
    import bmesh
    from mathutils import Vector
    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False
    bpy = None
    bmesh = None
    Vector = None


def check_blender():
    """Check if running inside Blender."""
    if not BLENDER_AVAILABLE:
        raise RuntimeError(
            "This module must be run inside Blender. "
            "Use: blender --background --python script.py"
        )


@dataclass
class MeshAnalysis:
    """Results of mesh analysis for 3D printing."""
    object_name: str
    vertex_count: int
    face_count: int
    edge_count: int
    is_manifold: bool
    is_watertight: bool
    has_non_manifold_edges: bool
    has_loose_geometry: bool
    volume: float  # in Blender units cubed
    surface_area: float  # in Blender units squared
    bounding_box: Tuple[Vector, Vector]  # min, max corners
    dimensions: Tuple[float, float, float]  # x, y, z
    issues: List[str]

    def is_printable(self) -> bool:
        """Check if mesh is suitable for 3D printing."""
        return self.is_manifold and self.is_watertight and not self.has_loose_geometry

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "object_name": self.object_name,
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "edge_count": self.edge_count,
            "is_manifold": self.is_manifold,
            "is_watertight": self.is_watertight,
            "has_non_manifold_edges": self.has_non_manifold_edges,
            "has_loose_geometry": self.has_loose_geometry,
            "volume": self.volume,
            "surface_area": self.surface_area,
            "dimensions": self.dimensions,
            "is_printable": self.is_printable(),
            "issues": self.issues,
        }


def analyze_mesh(obj) -> MeshAnalysis:
    """
    Analyze a mesh object for 3D printing suitability.

    Args:
        obj: Blender mesh object

    Returns:
        MeshAnalysis with detailed information
    """
    check_blender()

    if obj.type != 'MESH':
        raise ValueError(f"Object '{obj.name}' is not a mesh (type: {obj.type})")

    mesh = obj.data
    issues = []

    # Create BMesh for analysis
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Basic counts
    vertex_count = len(bm.verts)
    face_count = len(bm.faces)
    edge_count = len(bm.edges)

    # Check for non-manifold edges
    non_manifold_edges = [e for e in bm.edges if not e.is_manifold]
    has_non_manifold_edges = len(non_manifold_edges) > 0

    if has_non_manifold_edges:
        issues.append(f"Found {len(non_manifold_edges)} non-manifold edges")

    # Check for loose geometry
    loose_verts = [v for v in bm.verts if not v.link_edges]
    loose_edges = [e for e in bm.edges if not e.link_faces]
    has_loose_geometry = len(loose_verts) > 0 or len(loose_edges) > 0

    if loose_verts:
        issues.append(f"Found {len(loose_verts)} loose vertices")
    if loose_edges:
        issues.append(f"Found {len(loose_edges)} loose edges")

    # Check manifold status
    is_manifold = not has_non_manifold_edges and not has_loose_geometry

    # Check watertight (all edges have exactly 2 faces)
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    is_watertight = len(boundary_edges) == 0

    if boundary_edges:
        issues.append(f"Found {len(boundary_edges)} boundary edges (mesh has holes)")

    # Calculate volume and surface area
    volume = bm.calc_volume()
    surface_area = sum(f.calc_area() for f in bm.faces)

    # Get bounding box
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_corner = Vector((
        min(v.x for v in bbox_corners),
        min(v.y for v in bbox_corners),
        min(v.z for v in bbox_corners)
    ))
    max_corner = Vector((
        max(v.x for v in bbox_corners),
        max(v.y for v in bbox_corners),
        max(v.z for v in bbox_corners)
    ))

    dimensions = tuple(obj.dimensions)

    bm.free()

    return MeshAnalysis(
        object_name=obj.name,
        vertex_count=vertex_count,
        face_count=face_count,
        edge_count=edge_count,
        is_manifold=is_manifold,
        is_watertight=is_watertight,
        has_non_manifold_edges=has_non_manifold_edges,
        has_loose_geometry=has_loose_geometry,
        volume=volume,
        surface_area=surface_area,
        bounding_box=(min_corner, max_corner),
        dimensions=dimensions,
        issues=issues
    )


def make_manifold(obj, fill_holes: bool = True, merge_distance: float = 0.0001) -> bool:
    """
    Attempt to make a mesh manifold (printable).

    Args:
        obj: Blender mesh object
        fill_holes: Whether to fill holes in the mesh
        merge_distance: Distance threshold for merging vertices

    Returns:
        True if mesh is now manifold, False otherwise
    """
    check_blender()

    if obj.type != 'MESH':
        raise ValueError(f"Object '{obj.name}' is not a mesh")

    # Select the object
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Enter edit mode
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')

    # Remove doubles (merge close vertices)
    bpy.ops.mesh.remove_doubles(threshold=merge_distance)

    # Fill holes if requested
    if fill_holes:
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_non_manifold()
        try:
            bpy.ops.mesh.fill_holes(sides=0)  # 0 = no limit on hole size
        except RuntimeError:
            pass  # Some holes may not be fillable

    # Recalculate normals
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)

    bpy.ops.object.mode_set(mode='OBJECT')

    # Check if manifold now
    analysis = analyze_mesh(obj)
    return analysis.is_manifold


def scale_to_size(obj, target_size: float, axis: str = 'max') -> Tuple[float, float, float]:
    """
    Scale object to a target size while maintaining proportions.

    Args:
        obj: Blender object to scale
        target_size: Target size in Blender units
        axis: Which axis to use for scaling ('x', 'y', 'z', 'max', 'min')

    Returns:
        New dimensions (x, y, z)
    """
    check_blender()

    dims = obj.dimensions

    if axis == 'max':
        current = max(dims)
    elif axis == 'min':
        current = min(dims)
    elif axis in ('x', 'X'):
        current = dims[0]
    elif axis in ('y', 'Y'):
        current = dims[1]
    elif axis in ('z', 'Z'):
        current = dims[2]
    else:
        raise ValueError(f"Invalid axis: {axis}")

    if current == 0:
        raise ValueError("Object has zero dimension on specified axis")

    scale_factor = target_size / current

    obj.scale = (
        obj.scale[0] * scale_factor,
        obj.scale[1] * scale_factor,
        obj.scale[2] * scale_factor
    )

    # Apply scale
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    return tuple(obj.dimensions)


def center_object(obj, center_z: bool = False) -> None:
    """
    Center object at origin.

    Args:
        obj: Blender object
        center_z: If True, center on Z axis; if False, place bottom at Z=0
    """
    check_blender()

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Set origin to geometry center
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

    # Move to origin
    if center_z:
        obj.location = (0, 0, 0)
    else:
        # Place bottom at Z=0
        z_offset = obj.dimensions[2] / 2
        obj.location = (0, 0, z_offset)


def apply_all_transforms(obj) -> None:
    """Apply all transforms (location, rotation, scale) to mesh data."""
    check_blender()

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def triangulate_mesh(obj) -> int:
    """
    Convert all faces to triangles (required for STL export).

    Args:
        obj: Blender mesh object

    Returns:
        Number of triangles in the resulting mesh
    """
    check_blender()

    if obj.type != 'MESH':
        raise ValueError(f"Object '{obj.name}' is not a mesh")

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
    bpy.ops.object.mode_set(mode='OBJECT')

    return len(obj.data.polygons)


def get_print_info(obj) -> Dict:
    """
    Get comprehensive print information for an object.

    Args:
        obj: Blender mesh object

    Returns:
        Dictionary with print-relevant information
    """
    check_blender()

    analysis = analyze_mesh(obj)

    # Estimate print time and material (very rough estimates)
    # Assuming 100mm³/hour print speed and PLA density
    volume_mm3 = analysis.volume * 1000  # Assuming Blender units are mm
    pla_density = 1.24  # g/cm³
    volume_cm3 = volume_mm3 / 1000

    return {
        "object_name": analysis.object_name,
        "is_printable": analysis.is_printable(),
        "issues": analysis.issues,
        "dimensions_mm": {
            "x": analysis.dimensions[0],
            "y": analysis.dimensions[1],
            "z": analysis.dimensions[2],
        },
        "volume_mm3": volume_mm3,
        "volume_cm3": volume_cm3,
        "surface_area_mm2": analysis.surface_area,
        "estimated_weight_g": volume_cm3 * pla_density,
        "face_count": analysis.face_count,
        "vertex_count": analysis.vertex_count,
    }
