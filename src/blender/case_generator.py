"""
Case and mount generator from 3D scans.

Creates enclosures, cases, mounts, and holders based on scanned objects.
Perfect for creating phone cases, device holders, custom mounts, etc.
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


class CaseType(Enum):
    """Type of case/enclosure to generate."""
    FULL_CASE = "full_case"           # Wraps entire object
    BUMPER = "bumper"                  # Edges only, open front/back
    CRADLE = "cradle"                  # Holds object from below
    SLEEVE = "sleeve"                  # Slides in from one end
    MOUNT = "mount"                    # Wall/desk mount
    STAND = "stand"                    # Angled stand


@dataclass
class CaseConfig:
    """Configuration for case generation."""
    case_type: CaseType = CaseType.FULL_CASE
    wall_thickness: float = 1.5       # mm
    clearance: float = 0.3            # mm gap for fit
    lip_height: float = 1.0           # mm lip over edges
    corner_radius: float = 2.0        # mm
    include_cutouts: bool = True      # Auto cutouts for ports
    stand_angle: float = 60.0         # degrees (for stand type)
    mount_hole_diameter: float = 4.0  # mm (for mount type)
    open_top: bool = False            # Leave top open
    open_bottom: bool = False         # Leave bottom open


@dataclass
class GeneratedCase:
    """Result of case generation."""
    case_object: Any  # bpy.types.Object
    scan_object: Any  # Original scan
    dimensions: Tuple[float, float, float]
    volume_mm3: float
    estimated_print_time_min: float
    estimated_material_g: float


def create_case_from_scan(
    scan_obj: "bpy.types.Object",
    config: Optional[CaseConfig] = None
) -> GeneratedCase:
    """
    Create a case/enclosure that fits around a scanned object.

    Args:
        scan_obj: The scanned object to create a case for
        config: Case configuration options

    Returns:
        GeneratedCase with the resulting case object
    """
    check_blender()

    if config is None:
        config = CaseConfig()

    # Get scan dimensions
    scan_dims = scan_obj.dimensions
    scan_bbox = [scan_obj.matrix_world @ Vector(c) for c in scan_obj.bound_box]

    min_corner = Vector((
        min(v.x for v in scan_bbox),
        min(v.y for v in scan_bbox),
        min(v.z for v in scan_bbox)
    ))
    max_corner = Vector((
        max(v.x for v in scan_bbox),
        max(v.y for v in scan_bbox),
        max(v.z for v in scan_bbox)
    ))

    # Calculate case dimensions with clearance
    clearance = config.clearance
    wall = config.wall_thickness

    case_min = min_corner - Vector((clearance + wall, clearance + wall, clearance + wall))
    case_max = max_corner + Vector((clearance + wall, clearance + wall, clearance + wall))

    case_size = case_max - case_min
    case_center = (case_min + case_max) / 2

    if config.case_type == CaseType.FULL_CASE:
        case_obj = _create_full_case(scan_obj, config, case_min, case_max)
    elif config.case_type == CaseType.BUMPER:
        case_obj = _create_bumper(scan_obj, config, case_min, case_max)
    elif config.case_type == CaseType.CRADLE:
        case_obj = _create_cradle(scan_obj, config, case_min, case_max)
    elif config.case_type == CaseType.STAND:
        case_obj = _create_stand(scan_obj, config, case_min, case_max)
    elif config.case_type == CaseType.MOUNT:
        case_obj = _create_mount(scan_obj, config, case_min, case_max)
    else:
        case_obj = _create_full_case(scan_obj, config, case_min, case_max)

    case_obj.name = f"Case_{scan_obj.name}"

    # Calculate volume and estimates
    bm = bmesh.new()
    bm.from_mesh(case_obj.data)
    volume = abs(bm.calc_volume())
    bm.free()

    volume_cm3 = volume / 1000
    print_time = volume / 50  # rough estimate
    material_g = volume_cm3 * 1.24 * 0.2  # 20% infill

    return GeneratedCase(
        case_object=case_obj,
        scan_object=scan_obj,
        dimensions=tuple(case_obj.dimensions),
        volume_mm3=volume,
        estimated_print_time_min=print_time,
        estimated_material_g=material_g
    )


def _create_full_case(
    scan_obj: "bpy.types.Object",
    config: CaseConfig,
    case_min: Vector,
    case_max: Vector
) -> "bpy.types.Object":
    """Create a full enclosure case."""
    check_blender()

    clearance = config.clearance
    wall = config.wall_thickness
    lip = config.lip_height

    case_size = case_max - case_min
    case_center = (case_min + case_max) / 2

    # Create outer shell
    bpy.ops.mesh.primitive_cube_add(size=1, location=case_center)
    outer = bpy.context.active_object
    outer.dimensions = case_size

    # Create inner cavity (to subtract)
    inner_size = case_size - Vector((wall * 2, wall * 2, wall * 2))
    bpy.ops.mesh.primitive_cube_add(size=1, location=case_center)
    inner = bpy.context.active_object
    inner.dimensions = inner_size

    # If open top, extend inner upward
    if config.open_top:
        inner.dimensions.z += wall + lip
        inner.location.z += (wall + lip) / 2

    # Boolean difference
    bpy.ops.object.select_all(action='DESELECT')
    outer.select_set(True)
    bpy.context.view_layer.objects.active = outer

    bool_mod = outer.modifiers.new(name="Boolean", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = inner
    bpy.ops.object.modifier_apply(modifier=bool_mod.name)

    # Delete inner
    bpy.ops.object.select_all(action='DESELECT')
    inner.select_set(True)
    bpy.ops.object.delete()

    # Apply transforms
    bpy.ops.object.select_all(action='DESELECT')
    outer.select_set(True)
    bpy.context.view_layer.objects.active = outer
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    return outer


def _create_bumper(
    scan_obj: "bpy.types.Object",
    config: CaseConfig,
    case_min: Vector,
    case_max: Vector
) -> "bpy.types.Object":
    """Create a bumper-style case (edges only)."""
    check_blender()

    wall = config.wall_thickness
    clearance = config.clearance
    lip = config.lip_height

    case_size = case_max - case_min
    case_center = (case_min + case_max) / 2

    # Create outer frame
    bpy.ops.mesh.primitive_cube_add(size=1, location=case_center)
    outer = bpy.context.active_object
    outer.dimensions = case_size

    # Create inner cutout (larger to leave frame)
    inner_size = Vector((
        case_size.x - wall * 2,
        case_size.y - wall * 2,
        case_size.z + 10  # Extend through top/bottom
    ))
    bpy.ops.mesh.primitive_cube_add(size=1, location=case_center)
    inner = bpy.context.active_object
    inner.dimensions = inner_size

    # Boolean difference
    bpy.ops.object.select_all(action='DESELECT')
    outer.select_set(True)
    bpy.context.view_layer.objects.active = outer

    bool_mod = outer.modifiers.new(name="Boolean", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = inner
    bpy.ops.object.modifier_apply(modifier=bool_mod.name)

    # Delete inner
    bpy.ops.object.select_all(action='DESELECT')
    inner.select_set(True)
    bpy.ops.object.delete()

    return outer


def _create_cradle(
    scan_obj: "bpy.types.Object",
    config: CaseConfig,
    case_min: Vector,
    case_max: Vector
) -> "bpy.types.Object":
    """Create a cradle that holds the object from below."""
    check_blender()

    wall = config.wall_thickness
    clearance = config.clearance

    case_size = case_max - case_min
    case_center = (case_min + case_max) / 2

    # Cradle is bottom half + walls
    cradle_height = case_size.z * 0.4 + wall  # 40% of object height

    # Create base box
    bpy.ops.mesh.primitive_cube_add(size=1, location=(
        case_center.x,
        case_center.y,
        case_min.z + cradle_height / 2
    ))
    cradle = bpy.context.active_object
    cradle.dimensions = (case_size.x, case_size.y, cradle_height)

    # Create cavity
    cavity_size = Vector((
        case_size.x - wall * 2,
        case_size.y - wall * 2,
        cradle_height + 10
    ))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(
        case_center.x,
        case_center.y,
        case_min.z + cradle_height / 2 + wall
    ))
    cavity = bpy.context.active_object
    cavity.dimensions = cavity_size

    # Boolean
    bpy.ops.object.select_all(action='DESELECT')
    cradle.select_set(True)
    bpy.context.view_layer.objects.active = cradle

    bool_mod = cradle.modifiers.new(name="Boolean", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = cavity
    bpy.ops.object.modifier_apply(modifier=bool_mod.name)

    bpy.ops.object.select_all(action='DESELECT')
    cavity.select_set(True)
    bpy.ops.object.delete()

    return cradle


def _create_stand(
    scan_obj: "bpy.types.Object",
    config: CaseConfig,
    case_min: Vector,
    case_max: Vector
) -> "bpy.types.Object":
    """Create an angled stand for the object."""
    check_blender()
    import math

    wall = config.wall_thickness
    clearance = config.clearance
    angle = config.stand_angle

    case_size = case_max - case_min
    case_center = (case_min + case_max) / 2

    # Calculate stand dimensions based on angle
    angle_rad = math.radians(angle)
    stand_depth = case_size.y + wall * 2
    stand_height = case_size.z * 0.3 + wall  # Support 30% of height
    stand_width = case_size.x + wall * 2

    # Create base
    bpy.ops.mesh.primitive_cube_add(size=1)
    base = bpy.context.active_object
    base.dimensions = (stand_width, stand_depth, wall)
    base.location = (0, 0, wall / 2)

    # Create back support
    bpy.ops.mesh.primitive_cube_add(size=1)
    back = bpy.context.active_object
    back.dimensions = (stand_width, wall, stand_height)
    back.location = (0, -stand_depth / 2 + wall / 2, stand_height / 2)

    # Create front lip
    lip_height = wall * 2
    bpy.ops.mesh.primitive_cube_add(size=1)
    lip = bpy.context.active_object
    lip.dimensions = (stand_width, wall, lip_height)
    lip.location = (0, stand_depth / 2 - wall / 2, lip_height / 2 + wall)

    # Join all parts
    bpy.ops.object.select_all(action='DESELECT')
    base.select_set(True)
    back.select_set(True)
    lip.select_set(True)
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.join()

    stand = bpy.context.active_object

    # Rotate to angle
    stand.rotation_euler.x = math.radians(90 - angle)

    # Apply transforms
    bpy.ops.object.transform_apply(rotation=True)

    # Place on ground
    min_z = min((stand.matrix_world @ v.co).z for v in stand.data.vertices)
    stand.location.z -= min_z

    return stand


def _create_mount(
    scan_obj: "bpy.types.Object",
    config: CaseConfig,
    case_min: Vector,
    case_max: Vector
) -> "bpy.types.Object":
    """Create a wall/desk mount."""
    check_blender()

    wall = config.wall_thickness
    clearance = config.clearance
    hole_dia = config.mount_hole_diameter

    case_size = case_max - case_min
    case_center = (case_min + case_max) / 2

    # Create back plate
    plate_width = case_size.x + wall * 4
    plate_height = case_size.z + wall * 4

    bpy.ops.mesh.primitive_cube_add(size=1)
    plate = bpy.context.active_object
    plate.dimensions = (plate_width, wall, plate_height)
    plate.location = (0, -case_size.y / 2 - wall, case_size.z / 2)

    # Create cradle part
    cradle_depth = case_size.y * 0.5
    bpy.ops.mesh.primitive_cube_add(size=1)
    cradle_base = bpy.context.active_object
    cradle_base.dimensions = (case_size.x + wall * 2, cradle_depth, wall)
    cradle_base.location = (0, cradle_depth / 2 - case_size.y / 2, wall / 2)

    # Join
    bpy.ops.object.select_all(action='DESELECT')
    plate.select_set(True)
    cradle_base.select_set(True)
    bpy.context.view_layer.objects.active = plate
    bpy.ops.object.join()

    mount = bpy.context.active_object

    # Add mounting holes
    for x_offset in [-plate_width / 3, plate_width / 3]:
        for z_offset in [-plate_height / 3, plate_height / 3]:
            bpy.ops.mesh.primitive_cylinder_add(
                radius=hole_dia / 2,
                depth=wall * 2,
                location=(x_offset, -case_size.y / 2 - wall, case_size.z / 2 + z_offset)
            )
            hole = bpy.context.active_object
            hole.rotation_euler.x = 1.5708  # 90 degrees

            bpy.ops.object.select_all(action='DESELECT')
            mount.select_set(True)
            bpy.context.view_layer.objects.active = mount

            bool_mod = mount.modifiers.new(name="Boolean", type='BOOLEAN')
            bool_mod.operation = 'DIFFERENCE'
            bool_mod.object = hole
            bpy.ops.object.modifier_apply(modifier=bool_mod.name)

            bpy.ops.object.select_all(action='DESELECT')
            hole.select_set(True)
            bpy.ops.object.delete()

    # Place on ground
    bpy.ops.object.select_all(action='DESELECT')
    mount.select_set(True)
    bpy.context.view_layer.objects.active = mount

    min_z = min((mount.matrix_world @ v.co).z for v in mount.data.vertices)
    mount.location.z -= min_z

    return mount


def add_cutout(
    case_obj: "bpy.types.Object",
    position: Tuple[float, float, float],
    size: Tuple[float, float, float],
    shape: str = "rectangle"
) -> None:
    """
    Add a cutout to a case for ports, buttons, etc.

    Args:
        case_obj: The case object
        position: Center position of cutout (x, y, z)
        size: Size of cutout (width, depth, height)
        shape: "rectangle" or "circle"
    """
    check_blender()

    if shape == "circle":
        bpy.ops.mesh.primitive_cylinder_add(
            radius=size[0] / 2,
            depth=size[1] * 2,
            location=position
        )
    else:
        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=position
        )
        cutout = bpy.context.active_object
        cutout.dimensions = (size[0], size[1] * 2, size[2])

    cutout = bpy.context.active_object

    # Boolean subtract
    bpy.ops.object.select_all(action='DESELECT')
    case_obj.select_set(True)
    bpy.context.view_layer.objects.active = case_obj

    bool_mod = case_obj.modifiers.new(name="Cutout", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = cutout
    bpy.ops.object.modifier_apply(modifier=bool_mod.name)

    # Delete cutout object
    bpy.ops.object.select_all(action='DESELECT')
    cutout.select_set(True)
    bpy.ops.object.delete()
