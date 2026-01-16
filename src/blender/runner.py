#!/usr/bin/env python3
"""
Blender headless runner script.

This script is designed to be run from the command line via Blender:
    blender --background --python src/blender/runner.py -- --action create_cube --output model.stl

Or imported and used programmatically to generate Blender commands.
"""

import argparse
import json
import sys
from pathlib import Path

# Check if running inside Blender
try:
    import bpy
    INSIDE_BLENDER = True
except ImportError:
    INSIDE_BLENDER = False


def get_blender_command(
    script_path: str,
    action: str,
    output_path: str,
    **kwargs
) -> str:
    """
    Generate a Blender command line string.

    Args:
        script_path: Path to this runner script
        action: Action to perform
        output_path: Path for output file
        **kwargs: Additional action-specific arguments

    Returns:
        Command string to execute
    """
    cmd_parts = [
        "blender",
        "--background",
        "--python", str(script_path),
        "--",
        "--action", action,
        "--output", str(output_path),
    ]

    for key, value in kwargs.items():
        if value is not None:
            cmd_parts.extend([f"--{key.replace('_', '-')}", str(value)])

    return " ".join(cmd_parts)


def run_in_blender():
    """Main function when running inside Blender."""
    if not INSIDE_BLENDER:
        print("Error: This function must be run inside Blender")
        sys.exit(1)

    # Import Blender-specific modules
    from src.blender.primitives import (
        clear_scene, create_cube, create_cylinder, create_sphere,
        create_cone, create_torus, create_test_scene
    )
    from src.blender.exporter import export_for_printing, get_export_stats
    from src.blender.mesh_utils import analyze_mesh, make_manifold, center_object

    # Parse arguments after "--"
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Blender headless model creator")
    parser.add_argument("--action", required=True,
                        choices=["create_cube", "create_cylinder", "create_sphere",
                                 "create_cone", "create_torus", "create_test_scene",
                                 "analyze", "export"],
                        help="Action to perform")
    parser.add_argument("--output", "-o", type=str, default="output/model.stl",
                        help="Output file path")
    parser.add_argument("--format", "-f", type=str, default="stl",
                        choices=["stl", "obj", "ply"],
                        help="Export format")
    parser.add_argument("--size", type=float, default=20.0,
                        help="Size of primitive (mm)")
    parser.add_argument("--radius", type=float, default=10.0,
                        help="Radius for cylinder/sphere/cone")
    parser.add_argument("--height", type=float, default=20.0,
                        help="Height for cylinder/cone")
    parser.add_argument("--input", "-i", type=str,
                        help="Input .blend file")
    parser.add_argument("--json-output", action="store_true",
                        help="Output results as JSON")

    args = parser.parse_args(argv)

    result = {"success": False, "action": args.action}

    try:
        # Clear scene for new models
        if args.action.startswith("create_"):
            clear_scene()

        # Perform action
        if args.action == "create_cube":
            obj = create_cube(size=args.size, name="Cube")
            center_object(obj, center_z=False)

        elif args.action == "create_cylinder":
            obj = create_cylinder(
                radius=args.radius,
                depth=args.height,
                name="Cylinder"
            )
            center_object(obj, center_z=False)

        elif args.action == "create_sphere":
            obj = create_sphere(radius=args.radius, name="Sphere")
            center_object(obj, center_z=False)

        elif args.action == "create_cone":
            obj = create_cone(
                radius1=args.radius,
                depth=args.height,
                name="Cone"
            )
            center_object(obj, center_z=False)

        elif args.action == "create_torus":
            obj = create_torus(
                major_radius=args.radius,
                minor_radius=args.radius * 0.25,
                name="Torus"
            )
            center_object(obj, center_z=False)

        elif args.action == "create_test_scene":
            create_test_scene()
            obj = None

        elif args.action == "analyze":
            if not args.input:
                raise ValueError("--input required for analyze action")
            bpy.ops.wm.open_mainfile(filepath=args.input)
            analysis_results = []
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH':
                    analysis = analyze_mesh(obj)
                    analysis_results.append(analysis.to_dict())
            result["analysis"] = analysis_results

        elif args.action == "export":
            if args.input:
                bpy.ops.wm.open_mainfile(filepath=args.input)

        # Export if we created something
        if args.action.startswith("create_") and args.output:
            output_path = export_for_printing(
                filepath=args.output,
                format=args.format
            )
            stats = get_export_stats(output_path)
            result["output_path"] = str(output_path)
            result["file_stats"] = stats

            # Analyze the created object
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH':
                    analysis = analyze_mesh(obj)
                    result["mesh_analysis"] = analysis.to_dict()
                    break

        result["success"] = True

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    # Output results
    if args.json_output:
        print("JSON_RESULT:" + json.dumps(result))
    else:
        if result["success"]:
            print(f"✓ Action '{args.action}' completed successfully")
            if "output_path" in result:
                print(f"  Output: {result['output_path']}")
            if "file_stats" in result:
                print(f"  Size: {result['file_stats']['size_mb']:.2f} MB")
        else:
            print(f"✗ Action '{args.action}' failed: {result.get('error', 'Unknown error')}")


# Standalone helper functions (can be used without Blender)
def create_cube_stl(output_path: str, size: float = 20.0) -> str:
    """Generate command to create a cube and export to STL."""
    script_path = Path(__file__).resolve()
    return get_blender_command(
        script_path=script_path,
        action="create_cube",
        output_path=output_path,
        size=size,
        format="stl"
    )


def create_cylinder_stl(output_path: str, radius: float = 10.0, height: float = 20.0) -> str:
    """Generate command to create a cylinder and export to STL."""
    script_path = Path(__file__).resolve()
    return get_blender_command(
        script_path=script_path,
        action="create_cylinder",
        output_path=output_path,
        radius=radius,
        height=height,
        format="stl"
    )


def create_sphere_stl(output_path: str, radius: float = 10.0) -> str:
    """Generate command to create a sphere and export to STL."""
    script_path = Path(__file__).resolve()
    return get_blender_command(
        script_path=script_path,
        action="create_sphere",
        output_path=output_path,
        radius=radius,
        format="stl"
    )


if __name__ == "__main__":
    if INSIDE_BLENDER:
        run_in_blender()
    else:
        print("This script must be run inside Blender:")
        print("  blender --background --python src/blender/runner.py -- --action create_cube --output cube.stl")
        print("")
        print("Or use the helper functions to generate commands:")
        print(f"  {create_cube_stl('cube.stl', size=25)}")
