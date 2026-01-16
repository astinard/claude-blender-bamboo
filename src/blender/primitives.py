"""
Blender primitive shape generators.

This module provides functions to create basic 3D shapes in Blender.
Designed to work in headless mode (blender --background).

Usage:
    blender --background --python -c "from src.blender.primitives import create_cube; create_cube()"
"""

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


def clear_scene():
    """Remove all objects from the current scene."""
    check_blender()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def create_cube(
    size: float = 2.0,
    location: tuple = (0, 0, 0),
    name: str = "Cube"
) -> "bpy.types.Object":
    """
    Create a cube mesh.

    Args:
        size: Size of the cube (edge length)
        location: (x, y, z) position
        name: Object name

    Returns:
        The created Blender object
    """
    check_blender()
    bpy.ops.mesh.primitive_cube_add(
        size=size,
        location=location
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def create_cylinder(
    radius: float = 1.0,
    depth: float = 2.0,
    location: tuple = (0, 0, 0),
    vertices: int = 32,
    name: str = "Cylinder"
) -> "bpy.types.Object":
    """
    Create a cylinder mesh.

    Args:
        radius: Radius of the cylinder
        depth: Height of the cylinder
        location: (x, y, z) position
        vertices: Number of vertices around the circumference
        name: Object name

    Returns:
        The created Blender object
    """
    check_blender()
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=depth,
        vertices=vertices,
        location=location
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def create_sphere(
    radius: float = 1.0,
    location: tuple = (0, 0, 0),
    segments: int = 32,
    ring_count: int = 16,
    name: str = "Sphere"
) -> "bpy.types.Object":
    """
    Create a UV sphere mesh.

    Args:
        radius: Radius of the sphere
        location: (x, y, z) position
        segments: Number of horizontal segments
        ring_count: Number of vertical rings
        name: Object name

    Returns:
        The created Blender object
    """
    check_blender()
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius,
        segments=segments,
        ring_count=ring_count,
        location=location
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def create_cone(
    radius1: float = 1.0,
    radius2: float = 0.0,
    depth: float = 2.0,
    location: tuple = (0, 0, 0),
    vertices: int = 32,
    name: str = "Cone"
) -> "bpy.types.Object":
    """
    Create a cone mesh.

    Args:
        radius1: Bottom radius
        radius2: Top radius (0 for pointed cone)
        depth: Height of the cone
        location: (x, y, z) position
        vertices: Number of vertices around the circumference
        name: Object name

    Returns:
        The created Blender object
    """
    check_blender()
    bpy.ops.mesh.primitive_cone_add(
        radius1=radius1,
        radius2=radius2,
        depth=depth,
        vertices=vertices,
        location=location
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def create_torus(
    major_radius: float = 1.0,
    minor_radius: float = 0.25,
    location: tuple = (0, 0, 0),
    major_segments: int = 48,
    minor_segments: int = 12,
    name: str = "Torus"
) -> "bpy.types.Object":
    """
    Create a torus (donut) mesh.

    Args:
        major_radius: Distance from center to tube center
        minor_radius: Radius of the tube
        location: (x, y, z) position
        major_segments: Segments around the major circle
        minor_segments: Segments around the tube
        name: Object name

    Returns:
        The created Blender object
    """
    check_blender()
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=major_segments,
        minor_segments=minor_segments,
        location=location
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def create_plane(
    size: float = 2.0,
    location: tuple = (0, 0, 0),
    name: str = "Plane"
) -> "bpy.types.Object":
    """
    Create a plane mesh (for bases, platforms).

    Args:
        size: Size of the plane
        location: (x, y, z) position
        name: Object name

    Returns:
        The created Blender object
    """
    check_blender()
    bpy.ops.mesh.primitive_plane_add(
        size=size,
        location=location
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def boolean_union(obj1, obj2, name: str = "Union") -> "bpy.types.Object":
    """
    Combine two objects using boolean union.

    Args:
        obj1: First object (will be modified)
        obj2: Second object (will be removed)
        name: Name for the resulting object

    Returns:
        The combined object
    """
    check_blender()

    # Select and activate obj1
    bpy.ops.object.select_all(action='DESELECT')
    obj1.select_set(True)
    bpy.context.view_layer.objects.active = obj1

    # Add boolean modifier
    modifier = obj1.modifiers.new(name="Boolean", type='BOOLEAN')
    modifier.operation = 'UNION'
    modifier.object = obj2

    # Apply modifier
    bpy.ops.object.modifier_apply(modifier=modifier.name)

    # Delete obj2
    bpy.ops.object.select_all(action='DESELECT')
    obj2.select_set(True)
    bpy.ops.object.delete()

    obj1.name = name
    return obj1


def boolean_difference(obj1, obj2, name: str = "Difference") -> "bpy.types.Object":
    """
    Subtract obj2 from obj1 using boolean difference.

    Args:
        obj1: Object to cut from (will be modified)
        obj2: Object to cut with (will be removed)
        name: Name for the resulting object

    Returns:
        The result object
    """
    check_blender()

    bpy.ops.object.select_all(action='DESELECT')
    obj1.select_set(True)
    bpy.context.view_layer.objects.active = obj1

    modifier = obj1.modifiers.new(name="Boolean", type='BOOLEAN')
    modifier.operation = 'DIFFERENCE'
    modifier.object = obj2

    bpy.ops.object.modifier_apply(modifier=modifier.name)

    bpy.ops.object.select_all(action='DESELECT')
    obj2.select_set(True)
    bpy.ops.object.delete()

    obj1.name = name
    return obj1


# Convenience function for testing
def create_test_scene():
    """Create a test scene with various primitives."""
    check_blender()
    clear_scene()

    # Create some test objects
    create_cube(size=1.0, location=(0, 0, 0.5), name="TestCube")
    create_cylinder(radius=0.5, depth=2.0, location=(3, 0, 1), name="TestCylinder")
    create_sphere(radius=0.75, location=(-3, 0, 0.75), name="TestSphere")

    return list(bpy.context.scene.objects)
