#!/usr/bin/env python3
"""
Blender headless runner for scan processing.

Usage:
    blender --background --python src/blender/scan_runner.py -- --action analyze --input scan.stl
    blender --background --python src/blender/scan_runner.py -- --action repair --input scan.stl --output repaired.stl
    blender --background --python src/blender/scan_runner.py -- --action case --input scan.stl --case-type full_case
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


def run_in_blender():
    """Main function when running inside Blender."""
    if not INSIDE_BLENDER:
        print("Error: This script must be run inside Blender")
        sys.exit(1)

    # Add project root to path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    from src.blender.scan_processor import (
        import_scan, analyze_scan, repair_scan,
        scale_to_real_dimensions, decimate_scan, hollow_scan
    )
    from src.blender.case_generator import (
        create_case_from_scan, CaseConfig, CaseType, add_cutout
    )
    from src.blender.exporter import export_for_printing, get_export_stats

    # Parse arguments after "--"
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Blender scan processor")
    parser.add_argument("--action", required=True,
                        choices=["analyze", "repair", "scale", "decimate",
                                 "hollow", "case", "mount", "stand", "cradle"],
                        help="Action to perform")
    parser.add_argument("--input", "-i", required=True,
                        help="Input scan file (STL, OBJ, PLY)")
    parser.add_argument("--output", "-o",
                        help="Output file path")
    parser.add_argument("--format", "-f", default="stl",
                        choices=["stl", "obj", "ply"],
                        help="Export format")

    # Scale options
    parser.add_argument("--target-width", type=float, help="Target width in mm")
    parser.add_argument("--target-height", type=float, help="Target height in mm")
    parser.add_argument("--target-depth", type=float, help="Target depth in mm")

    # Repair options
    parser.add_argument("--fill-holes", action="store_true", default=True,
                        help="Fill holes in mesh")
    parser.add_argument("--smooth", type=int, default=0,
                        help="Smoothing iterations")

    # Decimate options
    parser.add_argument("--target-faces", type=int,
                        help="Target face count for decimation")
    parser.add_argument("--decimate-ratio", type=float,
                        help="Decimation ratio (0.5 = half)")

    # Hollow options
    parser.add_argument("--wall-thickness", type=float, default=2.0,
                        help="Wall thickness for hollow/case (mm)")

    # Case options
    parser.add_argument("--case-type", default="full_case",
                        choices=["full_case", "bumper", "cradle", "stand", "mount"],
                        help="Type of case to generate")
    parser.add_argument("--clearance", type=float, default=0.3,
                        help="Clearance gap for fit (mm)")
    parser.add_argument("--stand-angle", type=float, default=60.0,
                        help="Stand angle in degrees")

    # Output options
    parser.add_argument("--json-output", action="store_true",
                        help="Output results as JSON")

    args = parser.parse_args(argv)

    result = {"success": False, "action": args.action}

    try:
        # Clear scene
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)

        # Import scan
        input_path = Path(args.input)
        scan_obj = import_scan(input_path)
        result["input_file"] = str(input_path)

        # Perform action
        if args.action == "analyze":
            analysis = analyze_scan(scan_obj)
            result["analysis"] = analysis.to_dict()
            result["success"] = True

        elif args.action == "repair":
            repair_stats = repair_scan(
                scan_obj,
                fill_holes=args.fill_holes,
                smooth_iterations=args.smooth
            )
            result["repair_stats"] = repair_stats

            # Export if output specified
            if args.output:
                output_path = export_for_printing(args.output, args.format)
                result["output_path"] = str(output_path)
                result["file_stats"] = get_export_stats(output_path)

            result["success"] = True

        elif args.action == "scale":
            new_dims = scale_to_real_dimensions(
                scan_obj,
                target_width=args.target_width,
                target_height=args.target_height,
                target_depth=args.target_depth
            )
            result["new_dimensions"] = {
                "width": new_dims[0],
                "depth": new_dims[1],
                "height": new_dims[2]
            }

            if args.output:
                output_path = export_for_printing(args.output, args.format)
                result["output_path"] = str(output_path)

            result["success"] = True

        elif args.action == "decimate":
            final_faces = decimate_scan(
                scan_obj,
                target_faces=args.target_faces,
                ratio=args.decimate_ratio
            )
            result["final_face_count"] = final_faces

            if args.output:
                output_path = export_for_printing(args.output, args.format)
                result["output_path"] = str(output_path)

            result["success"] = True

        elif args.action == "hollow":
            hollow_scan(scan_obj, wall_thickness=args.wall_thickness)
            result["wall_thickness"] = args.wall_thickness

            if args.output:
                output_path = export_for_printing(args.output, args.format)
                result["output_path"] = str(output_path)

            result["success"] = True

        elif args.action in ["case", "mount", "stand", "cradle"]:
            # Map action to case type
            type_map = {
                "case": CaseType.FULL_CASE,
                "mount": CaseType.MOUNT,
                "stand": CaseType.STAND,
                "cradle": CaseType.CRADLE,
            }

            if args.action == "case":
                case_type_str = args.case_type.upper()
                case_type = CaseType[case_type_str] if case_type_str in CaseType.__members__ else CaseType.FULL_CASE
            else:
                case_type = type_map[args.action]

            config = CaseConfig(
                case_type=case_type,
                wall_thickness=args.wall_thickness,
                clearance=args.clearance,
                stand_angle=args.stand_angle,
            )

            generated = create_case_from_scan(scan_obj, config)

            result["case_type"] = case_type.value
            result["case_dimensions"] = {
                "width": generated.dimensions[0],
                "depth": generated.dimensions[1],
                "height": generated.dimensions[2]
            }
            result["estimated_print_time_min"] = generated.estimated_print_time_min
            result["estimated_material_g"] = generated.estimated_material_g

            # Export case
            if args.output:
                # Select only the case for export
                bpy.ops.object.select_all(action='DESELECT')
                generated.case_object.select_set(True)
                bpy.context.view_layer.objects.active = generated.case_object

                output_path = export_for_printing(
                    args.output, args.format,
                    objects=[generated.case_object]
                )
                result["output_path"] = str(output_path)
                result["file_stats"] = get_export_stats(output_path)

            result["success"] = True

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        import traceback
        result["traceback"] = traceback.format_exc()

    # Output results
    if args.json_output:
        print("JSON_RESULT:" + json.dumps(result))
    else:
        if result["success"]:
            print(f"✓ Action '{args.action}' completed successfully")
            if "output_path" in result:
                print(f"  Output: {result['output_path']}")
            if "analysis" in result:
                analysis = result["analysis"]
                print(f"  Dimensions: {analysis['dimensions']['width_mm']:.1f} x "
                      f"{analysis['dimensions']['depth_mm']:.1f} x "
                      f"{analysis['dimensions']['height_mm']:.1f} mm")
                print(f"  Faces: {analysis['face_count']}")
                print(f"  Printable: {not analysis['needs_repair']}")
                if analysis['issues']:
                    print(f"  Issues: {', '.join(analysis['issues'])}")
            if "case_dimensions" in result:
                dims = result["case_dimensions"]
                print(f"  Case size: {dims['width']:.1f} x {dims['depth']:.1f} x {dims['height']:.1f} mm")
                print(f"  Est. print time: {result['estimated_print_time_min']:.0f} min")
                print(f"  Est. material: {result['estimated_material_g']:.1f} g")
        else:
            print(f"✗ Action '{args.action}' failed: {result.get('error', 'Unknown error')}")


def get_scan_command(action: str, input_file: str, **kwargs) -> str:
    """Generate Blender command for scan processing."""
    script_path = Path(__file__).resolve()

    cmd_parts = [
        "blender",
        "--background",
        "--python", str(script_path),
        "--",
        "--action", action,
        "--input", input_file,
        "--json-output"
    ]

    for key, value in kwargs.items():
        if value is not None:
            flag = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:
                    cmd_parts.append(flag)
            else:
                cmd_parts.extend([flag, str(value)])

    return " ".join(cmd_parts)


if __name__ == "__main__":
    if INSIDE_BLENDER:
        run_in_blender()
    else:
        print("This script must be run inside Blender:")
        print("  blender --background --python src/blender/scan_runner.py -- --action analyze --input scan.stl")
        print("")
        print("Available actions:")
        print("  analyze  - Analyze scan dimensions and printability")
        print("  repair   - Repair mesh issues (holes, non-manifold edges)")
        print("  scale    - Scale to real-world dimensions")
        print("  decimate - Reduce polygon count")
        print("  hollow   - Make hollow for material savings")
        print("  case     - Generate a case/enclosure")
        print("  mount    - Generate a wall mount")
        print("  stand    - Generate an angled stand")
        print("  cradle   - Generate a cradle holder")
