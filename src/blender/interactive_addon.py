"""
Blender Interactive Addon for Claude Code.

This addon enables real-time communication between Claude Code and Blender,
allowing natural language design iteration with visual feedback.

Install: Edit > Preferences > Add-ons > Install > Select this file
Or run Blender with: blender --python src/blender/interactive_addon.py
"""

import bpy
import json
import os
import threading
import time
from pathlib import Path
from mathutils import Vector, Euler
import math

# Command file for communication
COMMAND_FILE = Path.home() / ".claude" / "blender_commands.json"
RESPONSE_FILE = Path.home() / ".claude" / "blender_response.json"

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

        elif action == 'help':
            result["message"] = "Available commands"
            result["data"]["commands"] = [
                "load <file> - Load a scan file",
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
