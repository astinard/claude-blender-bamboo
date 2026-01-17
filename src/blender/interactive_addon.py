"""
Blender Interactive Addon for Claude Code.

This addon enables real-time communication between Claude Code and Blender,
allowing natural language design iteration with visual feedback.

Install: Edit > Preferences > Add-ons > Install > Select this file
Or run Blender with: blender --python src/blender/interactive_addon.py
"""

import bpy
import bmesh
import json
import os
import threading
import time
from pathlib import Path
from mathutils import Vector, Euler
import math
from typing import Dict, List, Tuple, Optional

# Command file for communication
COMMAND_FILE = Path.home() / ".claude" / "blender_commands.json"
RESPONSE_FILE = Path.home() / ".claude" / "blender_response.json"

# Color name to RGBA mapping (sRGB, 0-1)
COLOR_MAP: Dict[str, Tuple[float, float, float, float]] = {
    # Primary colors
    'red': (1.0, 0.0, 0.0, 1.0),
    'green': (0.0, 0.8, 0.0, 1.0),
    'blue': (0.0, 0.0, 1.0, 1.0),
    'yellow': (1.0, 1.0, 0.0, 1.0),
    'orange': (1.0, 0.5, 0.0, 1.0),
    'purple': (0.5, 0.0, 1.0, 1.0),
    'pink': (1.0, 0.4, 0.7, 1.0),
    'cyan': (0.0, 1.0, 1.0, 1.0),
    'magenta': (1.0, 0.0, 1.0, 1.0),
    # Neutrals
    'white': (1.0, 1.0, 1.0, 1.0),
    'black': (0.0, 0.0, 0.0, 1.0),
    'gray': (0.5, 0.5, 0.5, 1.0),
    'grey': (0.5, 0.5, 0.5, 1.0),
    'dark gray': (0.25, 0.25, 0.25, 1.0),
    'light gray': (0.75, 0.75, 0.75, 1.0),
    # Earth tones
    'brown': (0.6, 0.3, 0.0, 1.0),
    'tan': (0.82, 0.71, 0.55, 1.0),
    'beige': (0.96, 0.96, 0.86, 1.0),
    # Metallics
    'gold': (1.0, 0.84, 0.0, 1.0),
    'silver': (0.75, 0.75, 0.75, 1.0),
    'copper': (0.72, 0.45, 0.2, 1.0),
    'bronze': (0.8, 0.5, 0.2, 1.0),
}

# Region aliases for natural language
REGION_ALIASES: Dict[str, str] = {
    'upper': 'top',
    'lower': 'bottom',
    'base': 'bottom',
    'head': 'top',
    'front face': 'front',
    'back face': 'back',
    'rear': 'back',
    'side': 'left',  # Default side
    'sides': 'sides',
    'everywhere': 'all',
    'whole': 'all',
    'entire': 'all',
}

# Ensure directory exists
COMMAND_FILE.parent.mkdir(parents=True, exist_ok=True)


class InteractiveState:
    """Global state for interactive session."""
    running = False
    last_command_time = 0
    scan_object = None
    case_object = None


def write_response(success: bool, message: str, data: dict = None):
    """Write response for Claude Code to read."""
    response = {
        "success": success,
        "message": message,
        "timestamp": time.time(),
        "data": data or {}
    }
    with open(RESPONSE_FILE, 'w') as f:
        json.dump(response, f, indent=2)


def get_active_object():
    """Get the active mesh object."""
    obj = bpy.context.active_object
    if obj and obj.type == 'MESH':
        return obj
    # Find first mesh object
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            return obj
    return None


def parse_measurement(value_str: str) -> float:
    """Parse measurement string to mm. Supports inches, cm, mm."""
    value_str = value_str.lower().strip()

    # Extract number
    import re
    match = re.search(r'([\d.]+)\s*(inch|inches|in|"|cm|centimeter|centimeters|mm|millimeter|millimeters)?', value_str)
    if not match:
        try:
            return float(value_str)
        except:
            return 0

    value = float(match.group(1))
    unit = match.group(2) or 'mm'

    # Convert to mm
    if unit in ('inch', 'inches', 'in', '"'):
        return value * 25.4
    elif unit in ('cm', 'centimeter', 'centimeters'):
        return value * 10
    else:  # mm
        return value


def parse_color(color_str: str) -> Optional[Tuple[float, float, float, float]]:
    """Parse color string to RGBA tuple."""
    color_str = color_str.lower().strip()

    # Direct name match
    if color_str in COLOR_MAP:
        return COLOR_MAP[color_str]

    # Try hex color (#RRGGBB or #RGB)
    if color_str.startswith('#'):
        hex_str = color_str[1:]
        if len(hex_str) == 3:
            hex_str = ''.join(c * 2 for c in hex_str)
        if len(hex_str) == 6:
            r = int(hex_str[0:2], 16) / 255.0
            g = int(hex_str[2:4], 16) / 255.0
            b = int(hex_str[4:6], 16) / 255.0
            return (r, g, b, 1.0)

    # Try RGB tuple (r,g,b)
    import re
    rgb_match = re.match(r'(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', color_str)
    if rgb_match:
        r = int(rgb_match.group(1)) / 255.0
        g = int(rgb_match.group(2)) / 255.0
        b = int(rgb_match.group(3)) / 255.0
        return (min(r, 1.0), min(g, 1.0), min(b, 1.0), 1.0)

    return None


def parse_region(region_str: str) -> str:
    """Parse region string to normalized form."""
    region = region_str.lower().strip()
    return REGION_ALIASES.get(region, region)


def ensure_vertex_color_layer(obj) -> bpy.types.Attribute:
    """Ensure object has a vertex color layer, create if needed."""
    mesh = obj.data

    # Check for existing color attribute
    color_attr = mesh.color_attributes.get('Col')
    if color_attr is None:
        # Create new vertex color attribute (per-face-corner for best quality)
        color_attr = mesh.color_attributes.new(
            name='Col',
            type='FLOAT_COLOR',
            domain='CORNER'
        )
        # Initialize to white
        for i in range(len(color_attr.data)):
            color_attr.data[i].color = (1.0, 1.0, 1.0, 1.0)

    # Set as active for rendering
    mesh.color_attributes.active = color_attr
    mesh.color_attributes.render_color_index = mesh.color_attributes.find('Col')

    return color_attr


def get_faces_in_region(obj, region: str) -> List[int]:
    """
    Get face indices in the specified region.

    Regions:
        - top: faces with normal pointing up (Z > 0.5)
        - bottom: faces with normal pointing down (Z < -0.5)
        - front: faces with normal pointing -Y
        - back: faces with normal pointing +Y
        - left: faces with normal pointing -X
        - right: faces with normal pointing +X
        - sides: all faces not top or bottom
        - all: all faces
    """
    mesh = obj.data
    world_matrix = obj.matrix_world
    face_indices = []

    # Calculate bounding box to determine position-based regions
    verts_world = [world_matrix @ v.co for v in mesh.vertices]
    min_z = min(v.z for v in verts_world)
    max_z = max(v.z for v in verts_world)
    mid_z = (min_z + max_z) / 2
    height = max_z - min_z

    for i, poly in enumerate(mesh.polygons):
        # Transform normal to world space
        normal = world_matrix.to_3x3() @ poly.normal
        normal.normalize()

        # Calculate face center in world space
        center = world_matrix @ poly.center

        if region == 'all':
            face_indices.append(i)
        elif region == 'top':
            # Faces pointing up OR in the upper region
            if normal.z > 0.5 or center.z > mid_z + height * 0.3:
                face_indices.append(i)
        elif region == 'bottom':
            # Faces pointing down OR in the lower region
            if normal.z < -0.5 or center.z < mid_z - height * 0.3:
                face_indices.append(i)
        elif region == 'front':
            if normal.y < -0.5:
                face_indices.append(i)
        elif region == 'back':
            if normal.y > 0.5:
                face_indices.append(i)
        elif region == 'left':
            if normal.x < -0.5:
                face_indices.append(i)
        elif region == 'right':
            if normal.x > 0.5:
                face_indices.append(i)
        elif region == 'sides':
            # Not pointing primarily up or down
            if abs(normal.z) < 0.5:
                face_indices.append(i)

    return face_indices


def apply_color_to_faces(obj, face_indices: List[int], color: Tuple[float, float, float, float]):
    """Apply color to specific faces using vertex colors."""
    color_attr = ensure_vertex_color_layer(obj)
    mesh = obj.data

    # Vertex color data is per face corner (loop)
    # We need to map face indices to loop indices
    for face_idx in face_indices:
        poly = mesh.polygons[face_idx]
        for loop_idx in poly.loop_indices:
            color_attr.data[loop_idx].color = color

    # Update mesh
    mesh.update()


def setup_vertex_color_material(obj):
    """Setup a material that displays vertex colors."""
    # Check if object already has a vertex color material
    for mat in obj.data.materials:
        if mat and mat.name == 'VertexColorMaterial':
            return mat

    # Create new material
    mat = bpy.data.materials.new(name='VertexColorMaterial')
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear default nodes
    nodes.clear()

    # Create nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (300, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)

    vertex_color = nodes.new('ShaderNodeVertexColor')
    vertex_color.location = (-300, 0)
    vertex_color.layer_name = 'Col'

    # Link nodes
    links.new(vertex_color.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Assign to object
    if len(obj.data.materials) == 0:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat

    return mat


def execute_command(cmd: dict) -> dict:
    """Execute a design command and return result."""
    action = cmd.get('action', '').lower()
    params = cmd.get('params', {})

    obj = get_active_object()
    if not obj and action not in ('load', 'open', 'status', 'help'):
        return {"success": False, "message": "No mesh object found. Load a scan first."}

    result = {"success": True, "message": "", "data": {}}

    try:
        if action in ('load', 'open'):
            # Load a scan file
            filepath = params.get('file', '')
            if not filepath or not os.path.exists(filepath):
                return {"success": False, "message": f"File not found: {filepath}"}

            # Clear existing objects
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete()

            # Import based on extension
            ext = Path(filepath).suffix.lower()
            if ext == '.stl':
                bpy.ops.wm.stl_import(filepath=filepath)
            elif ext == '.obj':
                bpy.ops.wm.obj_import(filepath=filepath)
            elif ext == '.ply':
                bpy.ops.wm.ply_import(filepath=filepath)
            else:
                return {"success": False, "message": f"Unsupported format: {ext}"}

            obj = get_active_object()
            if obj:
                # Center and place on ground
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
                min_z = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
                obj.location.z -= min_z
                obj.location.x = 0
                obj.location.y = 0

                InteractiveState.scan_object = obj
                dims = obj.dimensions
                result["message"] = f"Loaded: {Path(filepath).name}"
                result["data"] = {
                    "dimensions": {
                        "width": round(dims.x, 1),
                        "depth": round(dims.y, 1),
                        "height": round(dims.z, 1)
                    }
                }

        elif action in ('add', 'import', 'add_object'):
            # Import additional object WITHOUT clearing scene
            filepath = params.get('file', '')
            if not filepath or not os.path.exists(filepath):
                return {"success": False, "message": f"File not found: {filepath}"}

            ext = Path(filepath).suffix.lower()
            if ext == '.stl':
                bpy.ops.wm.stl_import(filepath=filepath)
            elif ext == '.obj':
                bpy.ops.wm.obj_import(filepath=filepath)
            elif ext == '.ply':
                bpy.ops.wm.ply_import(filepath=filepath)
            else:
                return {"success": False, "message": f"Unsupported format: {ext}"}

            new_obj = bpy.context.active_object
            if new_obj:
                new_obj.name = Path(filepath).stem
                dims = new_obj.dimensions
                result["message"] = f"Added: {Path(filepath).name} (not replacing existing)"
                result["data"] = {
                    "name": new_obj.name,
                    "dimensions": {
                        "width": round(dims.x, 1),
                        "depth": round(dims.y, 1),
                        "height": round(dims.z, 1)
                    }
                }

        elif action in ('combine', 'join', 'merge'):
            # Join all mesh objects into one
            mesh_objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
            if len(mesh_objects) < 2:
                return {"success": False, "message": "Need at least 2 objects to combine"}

            bpy.ops.object.select_all(action='DESELECT')
            for o in mesh_objects:
                o.select_set(True)
            bpy.context.view_layer.objects.active = mesh_objects[0]
            bpy.ops.object.join()

            combined = bpy.context.active_object
            combined.name = "Combined"
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
            dims = combined.dimensions
            result["message"] = f"Combined {len(mesh_objects)} objects into one"
            result["data"]["dimensions"] = {
                "width": round(dims.x, 1),
                "depth": round(dims.y, 1),
                "height": round(dims.z, 1)
            }

        elif action in ('scale', 'resize'):
            # Scale the object
            factor = params.get('factor', 1.0)
            axis = params.get('axis', 'all').lower()

            if axis == 'all':
                obj.scale = (obj.scale.x * factor, obj.scale.y * factor, obj.scale.z * factor)
            elif axis in ('x', 'width'):
                obj.scale.x *= factor
            elif axis in ('y', 'depth'):
                obj.scale.y *= factor
            elif axis in ('z', 'height'):
                obj.scale.z *= factor

            bpy.ops.object.transform_apply(scale=True)
            dims = obj.dimensions
            result["message"] = f"Scaled by {factor}x"
            result["data"]["dimensions"] = {
                "width": round(dims.x, 1),
                "depth": round(dims.y, 1),
                "height": round(dims.z, 1)
            }

        elif action in ('height', 'taller', 'shorter', 'set_height'):
            # Change height
            target = parse_measurement(str(params.get('value', params.get('target', 0))))
            relative = params.get('relative', False)

            current_height = obj.dimensions.z

            if relative:
                # Add/subtract from current
                new_height = current_height + target
            else:
                new_height = target

            if new_height > 0:
                scale_factor = new_height / current_height
                obj.scale.z *= scale_factor
                bpy.ops.object.transform_apply(scale=True)

                # Reposition on ground
                min_z = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
                obj.location.z -= min_z

                dims = obj.dimensions
                result["message"] = f"Height changed to {dims.z:.1f}mm ({dims.z/25.4:.2f} inches)"
                result["data"]["dimensions"] = {
                    "width": round(dims.x, 1),
                    "depth": round(dims.y, 1),
                    "height": round(dims.z, 1)
                }

        elif action in ('width', 'wider', 'narrower', 'set_width'):
            target = parse_measurement(str(params.get('value', params.get('target', 0))))
            relative = params.get('relative', False)

            current = obj.dimensions.x
            if relative:
                new_val = current + target
            else:
                new_val = target

            if new_val > 0:
                obj.scale.x *= new_val / current
                bpy.ops.object.transform_apply(scale=True)
                dims = obj.dimensions
                result["message"] = f"Width changed to {dims.x:.1f}mm"
                result["data"]["dimensions"] = {
                    "width": round(dims.x, 1),
                    "depth": round(dims.y, 1),
                    "height": round(dims.z, 1)
                }

        elif action in ('rotate', 'angle', 'tilt'):
            # Rotate the object
            angle_deg = float(params.get('angle', params.get('value', 0)))
            axis = params.get('axis', 'x').lower()

            angle_rad = math.radians(angle_deg)

            if axis == 'x':
                obj.rotation_euler.x += angle_rad
            elif axis == 'y':
                obj.rotation_euler.y += angle_rad
            elif axis == 'z':
                obj.rotation_euler.z += angle_rad

            bpy.ops.object.transform_apply(rotation=True)

            # Reposition on ground
            min_z = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
            obj.location.z -= min_z

            result["message"] = f"Rotated {angle_deg}° around {axis.upper()} axis"

        elif action in ('move', 'position', 'translate'):
            x = parse_measurement(str(params.get('x', 0)))
            y = parse_measurement(str(params.get('y', 0)))
            z = parse_measurement(str(params.get('z', 0)))

            obj.location.x += x
            obj.location.y += y
            obj.location.z += z

            result["message"] = f"Moved by ({x}, {y}, {z})mm"

        elif action in ('thicken', 'wall', 'solidify'):
            # Add wall thickness
            thickness = parse_measurement(str(params.get('thickness', params.get('value', 2))))

            # Remove existing solidify modifier
            for mod in obj.modifiers:
                if mod.type == 'SOLIDIFY':
                    obj.modifiers.remove(mod)

            mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
            mod.thickness = thickness
            mod.offset = 0

            result["message"] = f"Added {thickness}mm wall thickness"

        elif action in ('hollow', 'shell'):
            thickness = parse_measurement(str(params.get('thickness', params.get('value', 2))))

            mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
            mod.thickness = -thickness
            mod.offset = 1.0
            mod.use_rim = True

            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)

            result["message"] = f"Made hollow with {thickness}mm walls"

        elif action in ('smooth', 'subdivide'):
            iterations = int(params.get('iterations', params.get('value', 1)))

            mod = obj.modifiers.new(name="Subdivision", type='SUBSURF')
            mod.levels = iterations
            mod.render_levels = iterations

            result["message"] = f"Applied {iterations} subdivision levels"

        elif action in ('bevel', 'round_edges'):
            amount = parse_measurement(str(params.get('amount', params.get('value', 1))))

            mod = obj.modifiers.new(name="Bevel", type='BEVEL')
            mod.width = amount
            mod.segments = 3

            result["message"] = f"Added {amount}mm bevel to edges"

        elif action == 'undo':
            bpy.ops.ed.undo()
            result["message"] = "Undid last action"

        elif action == 'redo':
            bpy.ops.ed.redo()
            result["message"] = "Redid last action"

        elif action in ('reset', 'revert'):
            bpy.ops.ed.undo_history(item=0)
            result["message"] = "Reset to original"

        elif action in ('status', 'info', 'dimensions'):
            if obj:
                dims = obj.dimensions
                loc = obj.location
                rot = obj.rotation_euler
                result["message"] = "Current object status"
                result["data"] = {
                    "name": obj.name,
                    "dimensions": {
                        "width": round(dims.x, 1),
                        "depth": round(dims.y, 1),
                        "height": round(dims.z, 1),
                        "width_inches": round(dims.x / 25.4, 2),
                        "depth_inches": round(dims.y / 25.4, 2),
                        "height_inches": round(dims.z / 25.4, 2)
                    },
                    "location": {
                        "x": round(loc.x, 1),
                        "y": round(loc.y, 1),
                        "z": round(loc.z, 1)
                    },
                    "rotation_degrees": {
                        "x": round(math.degrees(rot.x), 1),
                        "y": round(math.degrees(rot.y), 1),
                        "z": round(math.degrees(rot.z), 1)
                    },
                    "vertices": len(obj.data.vertices),
                    "faces": len(obj.data.polygons)
                }
            else:
                result["message"] = "No object loaded"

        elif action in ('export', 'save'):
            filepath = params.get('file', 'output/modified.stl')
            filepath = str(Path(filepath).resolve())

            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            ext = Path(filepath).suffix.lower()

            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)

            if ext == '.stl':
                bpy.ops.wm.stl_export(filepath=filepath, export_selected_objects=True)
            elif ext == '.obj':
                bpy.ops.wm.obj_export(filepath=filepath, export_selected_objects=True)

            result["message"] = f"Exported to {filepath}"
            result["data"]["filepath"] = filepath

        elif action in ('view', 'camera', 'look'):
            view = params.get('direction', 'front').lower()

            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            override = {'area': area, 'region': region}
                            if view == 'front':
                                bpy.ops.view3d.view_axis(override, type='FRONT')
                            elif view == 'back':
                                bpy.ops.view3d.view_axis(override, type='BACK')
                            elif view == 'left':
                                bpy.ops.view3d.view_axis(override, type='LEFT')
                            elif view == 'right':
                                bpy.ops.view3d.view_axis(override, type='RIGHT')
                            elif view == 'top':
                                bpy.ops.view3d.view_axis(override, type='TOP')
                            elif view == 'bottom':
                                bpy.ops.view3d.view_axis(override, type='BOTTOM')
                            bpy.ops.view3d.view_selected(override)
                            break

            result["message"] = f"Changed view to {view}"

        elif action == 'fit':
            # Fit view to object
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            override = {'area': area, 'region': region}
                            bpy.ops.view3d.view_selected(override)
                            break
            result["message"] = "Fitted view to object"

        elif action in ('add_spikes', 'spikes', 'horns'):
            # Add spikes/horns to the top of the object
            count = int(params.get('count', 5))
            height_factor = float(params.get('height_factor', 0.15))

            dims = obj.dimensions
            top_z = obj.location.z + dims.z
            center_x = obj.location.x
            center_y = obj.location.y
            spike_height = dims.z * height_factor

            # Spike configurations: (x, y, height_mult, tilt_degrees)
            if count >= 5:
                configs = [
                    (center_x - dims.x * 0.3, center_y, 1.2, 15),
                    (center_x + dims.x * 0.3, center_y, 1.2, -15),
                    (center_x, center_y, 1.5, 0),
                    (center_x - dims.x * 0.15, center_y, 0.8, 8),
                    (center_x + dims.x * 0.15, center_y, 0.8, -8),
                ]
            elif count >= 3:
                configs = [
                    (center_x - dims.x * 0.25, center_y, 1.0, 12),
                    (center_x + dims.x * 0.25, center_y, 1.0, -12),
                    (center_x, center_y, 1.3, 0),
                ]
            else:
                configs = [
                    (center_x - dims.x * 0.2, center_y, 1.0, 10),
                    (center_x + dims.x * 0.2, center_y, 1.0, -10),
                ]

            spikes = []
            for i, (x, y, h_mult, tilt) in enumerate(configs[:count]):
                h = spike_height * h_mult
                r = dims.x * 0.08
                bpy.ops.mesh.primitive_cone_add(
                    radius1=r, radius2=0, depth=h,
                    location=(x, y, top_z + h/2)
                )
                spike = bpy.context.active_object
                spike.name = f'Spike_{i}'
                spike.rotation_euler.y = math.radians(tilt)
                spikes.append(spike)

            # Join all with main object
            bpy.ops.object.select_all(action='DESELECT')
            for spike in spikes:
                spike.select_set(True)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.join()

            dims = obj.dimensions
            result["message"] = f"Added {len(spikes)} spikes/horns to the top!"
            result["data"]["dimensions"] = {
                "width": round(dims.x, 1),
                "depth": round(dims.y, 1),
                "height": round(dims.z, 1)
            }

        elif action in ('set_color', 'color', 'paint', 'colorize'):
            # Set vertex color on a region
            color_str = params.get('color', params.get('value', 'red'))
            region_str = params.get('region', params.get('area', 'all'))

            color = parse_color(color_str)
            if color is None:
                return {"success": False, "message": f"Unknown color: {color_str}. Use names like red, blue, green or hex #RRGGBB"}

            region = parse_region(region_str)
            valid_regions = ['all', 'top', 'bottom', 'front', 'back', 'left', 'right', 'sides']
            if region not in valid_regions:
                return {"success": False, "message": f"Unknown region: {region_str}. Use: {', '.join(valid_regions)}"}

            # Get faces in region
            face_indices = get_faces_in_region(obj, region)
            if not face_indices:
                return {"success": False, "message": f"No faces found in region '{region}'"}

            # Apply color
            apply_color_to_faces(obj, face_indices, color)

            # Setup material to show vertex colors
            setup_vertex_color_material(obj)

            # Switch to rendered view to see colors
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.shading.type = 'MATERIAL'

            result["message"] = f"Set {color_str} color on {region} ({len(face_indices)} faces)"
            result["data"]["color"] = color_str
            result["data"]["region"] = region
            result["data"]["faces_colored"] = len(face_indices)

        elif action in ('set_material', 'material', 'assign_material'):
            # Assign a material type to a region (for multi-material printing)
            material_name = params.get('material', params.get('value', 'pla'))
            region_str = params.get('region', params.get('area', 'all'))

            region = parse_region(region_str)

            # Use predefined colors for materials
            material_colors = {
                'pla': (0.9, 0.9, 0.9, 1.0),  # White-ish
                'petg': (0.7, 0.85, 1.0, 1.0),  # Light blue
                'tpu': (0.3, 0.3, 0.3, 1.0),  # Dark gray
                'abs': (0.8, 0.7, 0.5, 1.0),  # Beige
                'pa': (0.5, 0.5, 0.6, 1.0),  # Gray-blue
                'pc': (0.9, 0.95, 1.0, 1.0),  # Clear-ish
            }

            mat_lower = material_name.lower()
            color = material_colors.get(mat_lower, (0.8, 0.8, 0.8, 1.0))

            face_indices = get_faces_in_region(obj, region)
            if not face_indices:
                return {"success": False, "message": f"No faces found in region '{region}'"}

            apply_color_to_faces(obj, face_indices, color)
            setup_vertex_color_material(obj)

            # Store material assignment as custom property
            if 'material_regions' not in obj:
                obj['material_regions'] = {}
            obj['material_regions'][region] = material_name

            result["message"] = f"Assigned {material_name.upper()} to {region} ({len(face_indices)} faces)"
            result["data"]["material"] = material_name
            result["data"]["region"] = region
            result["data"]["faces_assigned"] = len(face_indices)

        elif action in ('list_colors', 'colors', 'show_colors'):
            # Show available colors
            result["message"] = "Available colors"
            result["data"]["colors"] = list(COLOR_MAP.keys())

        elif action in ('list_regions', 'regions', 'show_regions'):
            # Show available regions
            result["message"] = "Available regions"
            result["data"]["regions"] = ['all', 'top', 'bottom', 'front', 'back', 'left', 'right', 'sides']
            result["data"]["aliases"] = REGION_ALIASES

        elif action == 'execute_script':
            # Execute custom Python script in Blender
            script = params.get('script', '')
            if script:
                try:
                    exec(script)
                    result["message"] = "Script executed successfully"
                except Exception as e:
                    result["success"] = False
                    result["message"] = f"Script error: {str(e)}"
            else:
                result["success"] = False
                result["message"] = "No script provided"

        elif action == 'help':
            result["message"] = "Available commands"
            result["data"]["commands"] = [
                "load <file> - Load a scan file (replaces current)",
                "add <file> - Add another object (keeps current)",
                "combine - Join all objects into one",
                "status - Show current dimensions",
                "height <value> - Set height (e.g., '2 inches', '50mm')",
                "width <value> - Set width",
                "scale <factor> - Scale uniformly",
                "rotate <angle> [axis] - Rotate (default X axis)",
                "tilt <angle> - Same as rotate",
                "hollow <thickness> - Make hollow",
                "thicken <amount> - Add wall thickness",
                "smooth [iterations] - Smooth mesh",
                "bevel <amount> - Round edges",
                "undo - Undo last change",
                "export <file> - Save to file",
                "view <direction> - Change view (front/back/left/right/top)",
                "fit - Fit view to object",
                "--- Multi-Color Commands ---",
                "set_color <color> [region] - Set color (red, blue, #FF0000, etc.)",
                "set_material <material> [region] - Assign material (pla, tpu, etc.)",
                "list_colors - Show available color names",
                "list_regions - Show available regions (top, bottom, etc.)",
                "--- Regions: all, top, bottom, front, back, left, right, sides ---",
            ]

        else:
            result["success"] = False
            result["message"] = f"Unknown command: {action}"

    except Exception as e:
        result["success"] = False
        result["message"] = f"Error: {str(e)}"

    return result


def check_commands():
    """Check for new commands from Claude Code."""
    if not COMMAND_FILE.exists():
        return None

    try:
        mtime = COMMAND_FILE.stat().st_mtime
        if mtime <= InteractiveState.last_command_time:
            return None

        InteractiveState.last_command_time = mtime

        with open(COMMAND_FILE, 'r') as f:
            cmd = json.load(f)

        return cmd
    except:
        return None


def command_loop():
    """Background thread to check for commands."""
    while InteractiveState.running:
        cmd = check_commands()
        if cmd:
            # Execute in main thread
            result = execute_command(cmd)
            write_response(result["success"], result["message"], result.get("data"))
        time.sleep(0.1)


class CLAUDE_OT_StartInteractive(bpy.types.Operator):
    """Start interactive mode for Claude Code"""
    bl_idname = "claude.start_interactive"
    bl_label = "Start Claude Interactive"

    def execute(self, context):
        if not InteractiveState.running:
            InteractiveState.running = True
            InteractiveState.last_command_time = 0

            # Clear command file
            if COMMAND_FILE.exists():
                COMMAND_FILE.unlink()

            # Start background thread
            thread = threading.Thread(target=command_loop, daemon=True)
            thread.start()

            write_response(True, "Interactive mode started. Ready for commands.")
            self.report({'INFO'}, "Claude Interactive mode started")
        return {'FINISHED'}


class CLAUDE_OT_StopInteractive(bpy.types.Operator):
    """Stop interactive mode"""
    bl_idname = "claude.stop_interactive"
    bl_label = "Stop Claude Interactive"

    def execute(self, context):
        InteractiveState.running = False
        write_response(True, "Interactive mode stopped.")
        self.report({'INFO'}, "Claude Interactive mode stopped")
        return {'FINISHED'}


class CLAUDE_PT_InteractivePanel(bpy.types.Panel):
    """Panel for Claude Code Interactive Mode"""
    bl_label = "Claude Code"
    bl_idname = "CLAUDE_PT_interactive"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Claude'

    def draw(self, context):
        layout = self.layout

        if InteractiveState.running:
            layout.label(text="Status: Connected", icon='CHECKMARK')
            layout.operator("claude.stop_interactive", text="Stop", icon='CANCEL')
        else:
            layout.label(text="Status: Disconnected", icon='ERROR')
            layout.operator("claude.start_interactive", text="Start", icon='PLAY')

        layout.separator()

        obj = get_active_object()
        if obj:
            layout.label(text=f"Object: {obj.name}")
            dims = obj.dimensions
            layout.label(text=f"Size: {dims.x:.1f} x {dims.y:.1f} x {dims.z:.1f} mm")
            layout.label(text=f"      {dims.x/25.4:.2f} x {dims.y/25.4:.2f} x {dims.z/25.4:.2f} in")


# Timer for checking commands in main thread (more reliable than threading)
def timer_check_commands():
    """Timer callback to check commands."""
    if InteractiveState.running:
        cmd = check_commands()
        if cmd:
            result = execute_command(cmd)
            write_response(result["success"], result["message"], result.get("data"))
            # Force viewport update
            for area in bpy.context.screen.areas:
                area.tag_redraw()
    return 0.1  # Check every 100ms


classes = [
    CLAUDE_OT_StartInteractive,
    CLAUDE_OT_StopInteractive,
    CLAUDE_PT_InteractivePanel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.timers.register(timer_check_commands, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(timer_check_commands):
        bpy.app.timers.unregister(timer_check_commands)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


# Auto-start when run as script
if __name__ == "__main__":
    register()

    # Auto-start interactive mode
    InteractiveState.running = True
    InteractiveState.last_command_time = 0

    # Clear old command file
    if COMMAND_FILE.exists():
        COMMAND_FILE.unlink()

    write_response(True, "Blender interactive mode ready. Waiting for commands...")
    print("\n" + "="*50)
    print("Claude Code Interactive Mode Active")
    print(f"Command file: {COMMAND_FILE}")
    print(f"Response file: {RESPONSE_FILE}")
    print("="*50 + "\n")
