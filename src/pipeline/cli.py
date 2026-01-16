#!/usr/bin/env python3
"""
Command-line interface for Blender-Bamboo pipeline.

Usage:
    blender-bamboo create cube --size 20 --output cube.stl
    blender-bamboo print cube.stl --printer-ip 192.168.1.100
    blender-bamboo status --printer-ip 192.168.1.100
    blender-bamboo workflow cube --size 20 --auto-print

    # Scan processing (from iOS LiDAR apps like Polycam, 3D Scanner App)
    blender-bamboo scan analyze phone_scan.stl
    blender-bamboo scan repair phone_scan.stl --output repaired.stl
    blender-bamboo scan case phone_scan.stl --case-type full_case --output case.stl
    blender-bamboo scan mount phone_scan.stl --output mount.stl
    blender-bamboo scan stand phone_scan.stl --angle 60 --output stand.stl
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.pipeline.workflow import (
    PrintWorkflow,
    WorkflowConfig,
    WorkflowStage,
    WorkflowResult
)
from src.printer import (
    BambooConnection,
    PrinterCommands,
    PrinterFileTransfer,
    PrinterStatus,
    PrinterState,
    create_mock_printer,
)


def print_status(status: PrinterStatus):
    """Pretty print printer status."""
    print(f"\n{'='*50}")
    print(f"Printer Status: {status.state.value.upper()}")
    print(f"{'='*50}")

    if status.state == PrinterState.PRINTING:
        print(f"Progress: {status.progress:.1f}%")
        print(f"Layer: {status.layer_current}/{status.layer_total}")
        remaining_min = status.remaining_time // 60
        remaining_sec = status.remaining_time % 60
        print(f"Remaining: {remaining_min}m {remaining_sec}s")
        print(f"File: {status.current_file}")

    print(f"\nTemperatures:")
    print(f"  Bed:    {status.bed_temp:.1f}°C / {status.bed_temp_target:.1f}°C")
    print(f"  Nozzle: {status.nozzle_temp:.1f}°C / {status.nozzle_temp_target:.1f}°C")

    if status.error_message:
        print(f"\nError: {status.error_message}")


def progress_callback(stage: WorkflowStage, message: str):
    """Print workflow progress."""
    emoji = {
        WorkflowStage.IDLE: "⏸️",
        WorkflowStage.MODELING: "🎨",
        WorkflowStage.EXPORTING: "📦",
        WorkflowStage.VALIDATING: "✅",
        WorkflowStage.UPLOADING: "⬆️",
        WorkflowStage.PRINTING: "🖨️",
        WorkflowStage.MONITORING: "👀",
        WorkflowStage.COMPLETED: "🎉",
        WorkflowStage.FAILED: "❌",
    }
    print(f"{emoji.get(stage, '•')} [{stage.value.upper()}] {message}")


def cmd_create(args):
    """Handle create command."""
    config = WorkflowConfig(
        model_type=args.shape,
        model_params={
            "size": args.size,
            "radius": args.radius,
            "height": args.height,
        },
        export_format=args.format,
        output_name=args.output or args.shape,
        use_mock_printer=True,  # Don't need printer for create
    )

    workflow = PrintWorkflow(config, progress_callback)
    result = workflow.create_model()

    if result.success:
        print(f"\n✓ Model created: {result.output_path}")
        if "mesh_analysis" in result.data:
            analysis = result.data["mesh_analysis"]
            print(f"  Dimensions: {analysis.get('dimensions', 'N/A')}")
            print(f"  Faces: {analysis.get('face_count', 'N/A')}")
            print(f"  Printable: {analysis.get('is_printable', 'N/A')}")
    else:
        print(f"\n✗ Failed: {result.message}")
        sys.exit(1)


def cmd_print(args):
    """Handle print command."""
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    if args.mock:
        print("Using mock printer for testing...")
        mock = create_mock_printer()
        mock.connect()
        mock.upload_file(file_path.name, file_path.stat().st_size)
        result = mock.start_print(file_path.name)

        if result.success:
            print(f"✓ Mock print started: {file_path.name}")

            if args.monitor:
                print("Monitoring print progress (Ctrl+C to stop)...")
                try:
                    while True:
                        status = mock.status
                        print_status(status)
                        if status.state in (PrinterState.FINISHED, PrinterState.ERROR, PrinterState.IDLE):
                            break
                        time.sleep(2)
                except KeyboardInterrupt:
                    print("\nMonitoring stopped.")
        else:
            print(f"✗ Failed: {result.message}")

        mock.disconnect()
        return

    # Real printer
    if not args.printer_ip:
        print("Error: --printer-ip required (or use --mock)")
        sys.exit(1)

    print(f"Uploading {file_path.name} to printer...")

    transfer = PrinterFileTransfer(
        ip=args.printer_ip,
        access_code=args.access_code
    )

    if not transfer.connect():
        print("Error: Failed to connect to printer")
        sys.exit(1)

    result = transfer.upload_file(file_path)
    transfer.disconnect()

    if not result.success:
        print(f"Error: Upload failed - {result.message}")
        sys.exit(1)

    print(f"✓ Uploaded to {result.remote_path}")

    if args.start:
        print("Starting print...")
        conn = BambooConnection(
            ip=args.printer_ip,
            access_code=args.access_code,
            serial=args.serial or ""
        )

        if conn.connect():
            commands = PrinterCommands(conn)
            result = commands.start_print(file_path.name)

            if result.success:
                print(f"✓ Print started")

                if args.monitor:
                    print("Monitoring print progress (Ctrl+C to stop)...")
                    try:
                        while True:
                            status = conn.refresh_status()
                            print_status(status)
                            if status.state in (PrinterState.FINISHED, PrinterState.ERROR):
                                break
                            time.sleep(5)
                    except KeyboardInterrupt:
                        print("\nMonitoring stopped.")

            conn.disconnect()
        else:
            print("Error: Failed to connect to printer")
            sys.exit(1)


def cmd_status(args):
    """Handle status command."""
    if args.mock:
        mock = create_mock_printer()
        mock.connect()
        print_status(mock.status)
        mock.disconnect()
        return

    if not args.printer_ip:
        print("Error: --printer-ip required (or use --mock)")
        sys.exit(1)

    conn = BambooConnection(
        ip=args.printer_ip,
        access_code=args.access_code,
        serial=args.serial or ""
    )

    if conn.connect():
        status = conn.refresh_status()
        print_status(status)
        conn.disconnect()
    else:
        print("Error: Failed to connect to printer")
        sys.exit(1)


def cmd_workflow(args):
    """Handle full workflow command."""
    config = WorkflowConfig(
        model_type=args.shape,
        model_params={
            "size": args.size,
            "radius": args.radius,
            "height": args.height,
        },
        export_format=args.format,
        output_name=args.output or args.shape,
        printer_ip=args.printer_ip or "",
        printer_access_code=args.access_code or "",
        printer_serial=args.serial or "",
        use_mock_printer=args.mock,
        auto_start_print=args.auto_print,
        monitor_print=args.monitor,
    )

    workflow = PrintWorkflow(config, progress_callback)

    try:
        result = workflow.run_full_workflow()

        if result.success:
            print(f"\n🎉 Workflow completed successfully!")
            if result.output_path:
                print(f"   Output: {result.output_path}")
        else:
            print(f"\n❌ Workflow failed: {result.message}")
            sys.exit(1)

    finally:
        workflow.cleanup()


def cmd_list_files(args):
    """List files on printer."""
    if args.mock:
        print("Mock printer has no files.")
        return

    if not args.printer_ip:
        print("Error: --printer-ip required")
        sys.exit(1)

    transfer = PrinterFileTransfer(
        ip=args.printer_ip,
        access_code=args.access_code
    )

    if transfer.connect():
        files = transfer.list_files(args.path)
        print(f"\nFiles in {args.path}:")
        for f in files:
            icon = "📁" if f.is_directory else "📄"
            size = f"{f.size / 1024:.1f} KB" if not f.is_directory else ""
            print(f"  {icon} {f.name} {size}")
        transfer.disconnect()
    else:
        print("Error: Failed to connect to printer")
        sys.exit(1)


def run_blender_scan(action: str, input_file: str, **kwargs) -> dict:
    """
    Run Blender headless with scan_runner.py.

    Returns parsed JSON result from Blender.
    """
    scan_runner = project_root / "src" / "blender" / "scan_runner.py"

    cmd = [
        "blender", "--background", "--python", str(scan_runner),
        "--", "--action", action, "--input", input_file, "--json-output"
    ]

    # Add optional arguments
    for key, value in kwargs.items():
        if value is not None:
            flag = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:
                    cmd.append(flag)
            else:
                cmd.extend([flag, str(value)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        # Parse JSON from output
        for line in result.stdout.split('\n'):
            if line.startswith('JSON_RESULT:'):
                return json.loads(line[12:])

        # If no JSON found, create error result
        return {
            "success": False,
            "error": result.stderr or "No output from Blender",
            "stdout": result.stdout
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Blender process timed out"}
    except FileNotFoundError:
        return {"success": False, "error": "Blender not found. Install Blender and ensure it's in PATH."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cmd_scan(args):
    """Handle scan command with subcommands."""
    input_file = str(Path(args.input).resolve())

    if not Path(input_file).exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    action = args.scan_action
    kwargs = {}

    # Build kwargs based on action
    if hasattr(args, 'output') and args.output:
        kwargs['output'] = str(Path(args.output).resolve())
    if hasattr(args, 'format'):
        kwargs['format'] = args.format

    if action == "analyze":
        print(f"Analyzing scan: {args.input}")
        result = run_blender_scan("analyze", input_file)

    elif action == "repair":
        print(f"Repairing scan: {args.input}")
        if hasattr(args, 'smooth'):
            kwargs['smooth'] = args.smooth
        result = run_blender_scan("repair", input_file, **kwargs)

    elif action == "scale":
        print(f"Scaling scan: {args.input}")
        if hasattr(args, 'target_width'):
            kwargs['target_width'] = args.target_width
        if hasattr(args, 'target_height'):
            kwargs['target_height'] = args.target_height
        if hasattr(args, 'target_depth'):
            kwargs['target_depth'] = args.target_depth
        result = run_blender_scan("scale", input_file, **kwargs)

    elif action == "decimate":
        print(f"Decimating scan: {args.input}")
        if hasattr(args, 'target_faces'):
            kwargs['target_faces'] = args.target_faces
        if hasattr(args, 'ratio'):
            kwargs['decimate_ratio'] = args.ratio
        result = run_blender_scan("decimate", input_file, **kwargs)

    elif action == "hollow":
        print(f"Hollowing scan: {args.input}")
        if hasattr(args, 'wall_thickness'):
            kwargs['wall_thickness'] = args.wall_thickness
        result = run_blender_scan("hollow", input_file, **kwargs)

    elif action in ["case", "mount", "stand", "cradle"]:
        print(f"Generating {action} from scan: {args.input}")
        if hasattr(args, 'case_type'):
            kwargs['case_type'] = args.case_type
        if hasattr(args, 'wall_thickness'):
            kwargs['wall_thickness'] = args.wall_thickness
        if hasattr(args, 'clearance'):
            kwargs['clearance'] = args.clearance
        if hasattr(args, 'angle') and args.angle:
            kwargs['stand_angle'] = args.angle
        result = run_blender_scan(action, input_file, **kwargs)
    else:
        print(f"Error: Unknown scan action: {action}")
        sys.exit(1)

    # Display results
    if result.get("success"):
        print(f"\n✓ {action.title()} completed successfully!")

        if "analysis" in result:
            analysis = result["analysis"]
            dims = analysis.get("dimensions", {})
            print(f"\n  Scan Analysis:")
            print(f"    Dimensions: {dims.get('width_mm', 0):.1f} x "
                  f"{dims.get('depth_mm', 0):.1f} x "
                  f"{dims.get('height_mm', 0):.1f} mm")
            print(f"    Vertices: {analysis.get('vertex_count', 0):,}")
            print(f"    Faces: {analysis.get('face_count', 0):,}")
            print(f"    Watertight: {'Yes' if analysis.get('is_watertight') else 'No'}")
            print(f"    Manifold: {'Yes' if analysis.get('is_manifold') else 'No'}")
            if analysis.get("issues"):
                print(f"    Issues: {', '.join(analysis['issues'])}")
            print(f"    Est. print time: {analysis.get('estimated_print_time_min', 0):.0f} min")
            print(f"    Est. material: {analysis.get('estimated_material_g', 0):.1f} g")

        if "repair_stats" in result:
            stats = result["repair_stats"]
            print(f"\n  Repair Statistics:")
            print(f"    Vertices removed: {stats.get('vertices_removed', 0)}")
            print(f"    Holes filled: {stats.get('holes_filled', 0)}")

        if "case_dimensions" in result:
            dims = result["case_dimensions"]
            print(f"\n  Case Dimensions:")
            print(f"    Size: {dims['width']:.1f} x {dims['depth']:.1f} x {dims['height']:.1f} mm")
            print(f"    Est. print time: {result.get('estimated_print_time_min', 0):.0f} min")
            print(f"    Est. material: {result.get('estimated_material_g', 0):.1f} g")

        if "output_path" in result:
            print(f"\n  Output saved to: {result['output_path']}")
    else:
        print(f"\n✗ {action.title()} failed: {result.get('error', 'Unknown error')}")
        if "traceback" in result:
            print(f"\nTraceback:\n{result['traceback']}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Blender-Bamboo 3D Print Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create cube --size 25 --output my_cube
  %(prog)s create cylinder --radius 10 --height 30
  %(prog)s print model.stl --mock --monitor
  %(prog)s status --printer-ip 192.168.1.100 --access-code ABC123
  %(prog)s workflow sphere --radius 15 --mock --auto-print

LiDAR Scan Processing (iPhone/iPad with LiDAR):
  %(prog)s scan analyze phone_case.stl
  %(prog)s scan repair phone_case.stl --output repaired.stl --smooth 2
  %(prog)s scan case phone_case.stl --case-type full_case --output case.stl
  %(prog)s scan mount controller.stl --output wall_mount.stl
  %(prog)s scan stand tablet.stl --angle 60 --output stand.stl
        """
    )

    # Global arguments
    parser.add_argument("--mock", action="store_true",
                        help="Use mock printer for testing")
    parser.add_argument("--printer-ip", type=str,
                        help="Printer IP address")
    parser.add_argument("--access-code", type=str, default="",
                        help="Printer access code")
    parser.add_argument("--serial", type=str, default="",
                        help="Printer serial number")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a 3D model")
    create_parser.add_argument("shape",
                               choices=["cube", "cylinder", "sphere", "cone", "torus"],
                               help="Shape to create")
    create_parser.add_argument("--size", type=float, default=20.0,
                               help="Size in mm (for cube)")
    create_parser.add_argument("--radius", type=float, default=10.0,
                               help="Radius in mm")
    create_parser.add_argument("--height", type=float, default=20.0,
                               help="Height in mm")
    create_parser.add_argument("--format", choices=["stl", "obj", "ply"],
                               default="stl", help="Export format")
    create_parser.add_argument("--output", "-o", type=str,
                               help="Output filename (without extension)")
    create_parser.set_defaults(func=cmd_create)

    # Print command
    print_parser = subparsers.add_parser("print", help="Print a file")
    print_parser.add_argument("file", type=str, help="File to print")
    print_parser.add_argument("--start", action="store_true",
                              help="Immediately start print")
    print_parser.add_argument("--monitor", action="store_true",
                              help="Monitor print progress")
    print_parser.set_defaults(func=cmd_print)

    # Status command
    status_parser = subparsers.add_parser("status", help="Get printer status")
    status_parser.set_defaults(func=cmd_status)

    # Workflow command
    workflow_parser = subparsers.add_parser("workflow",
                                            help="Run full create-upload-print workflow")
    workflow_parser.add_argument("shape",
                                 choices=["cube", "cylinder", "sphere", "cone", "torus"],
                                 help="Shape to create")
    workflow_parser.add_argument("--size", type=float, default=20.0,
                                 help="Size in mm (for cube)")
    workflow_parser.add_argument("--radius", type=float, default=10.0,
                                 help="Radius in mm")
    workflow_parser.add_argument("--height", type=float, default=20.0,
                                 help="Height in mm")
    workflow_parser.add_argument("--format", choices=["stl", "obj", "ply"],
                                 default="stl", help="Export format")
    workflow_parser.add_argument("--output", "-o", type=str,
                                 help="Output filename")
    workflow_parser.add_argument("--auto-print", action="store_true",
                                 help="Automatically start print")
    workflow_parser.add_argument("--monitor", action="store_true",
                                 help="Monitor print progress")
    workflow_parser.set_defaults(func=cmd_workflow)

    # List files command
    list_parser = subparsers.add_parser("list", help="List files on printer")
    list_parser.add_argument("--path", type=str, default="/",
                             help="Directory path")
    list_parser.set_defaults(func=cmd_list_files)

    # Scan command with subcommands
    scan_parser = subparsers.add_parser(
        "scan",
        help="Process LiDAR scans (from Polycam, 3D Scanner App, etc.)",
        description="Process 3D scans from iOS LiDAR apps for case/mount generation"
    )
    scan_subparsers = scan_parser.add_subparsers(dest="scan_action", help="Scan operations")

    # Scan analyze
    scan_analyze = scan_subparsers.add_parser("analyze", help="Analyze scan dimensions and printability")
    scan_analyze.add_argument("input", help="Input scan file (STL, OBJ, PLY)")
    scan_analyze.set_defaults(func=cmd_scan)

    # Scan repair
    scan_repair = scan_subparsers.add_parser("repair", help="Repair mesh issues (holes, non-manifold)")
    scan_repair.add_argument("input", help="Input scan file")
    scan_repair.add_argument("--output", "-o", help="Output file path")
    scan_repair.add_argument("--format", choices=["stl", "obj", "ply"], default="stl")
    scan_repair.add_argument("--smooth", type=int, default=0,
                             help="Smoothing iterations")
    scan_repair.set_defaults(func=cmd_scan)

    # Scan scale
    scan_scale = scan_subparsers.add_parser("scale", help="Scale to real-world dimensions")
    scan_scale.add_argument("input", help="Input scan file")
    scan_scale.add_argument("--output", "-o", help="Output file path")
    scan_scale.add_argument("--format", choices=["stl", "obj", "ply"], default="stl")
    scan_scale.add_argument("--target-width", type=float, help="Target width in mm")
    scan_scale.add_argument("--target-height", type=float, help="Target height in mm")
    scan_scale.add_argument("--target-depth", type=float, help="Target depth in mm")
    scan_scale.set_defaults(func=cmd_scan)

    # Scan decimate
    scan_decimate = scan_subparsers.add_parser("decimate", help="Reduce polygon count")
    scan_decimate.add_argument("input", help="Input scan file")
    scan_decimate.add_argument("--output", "-o", help="Output file path")
    scan_decimate.add_argument("--format", choices=["stl", "obj", "ply"], default="stl")
    scan_decimate.add_argument("--target-faces", type=int, help="Target face count")
    scan_decimate.add_argument("--ratio", type=float, help="Decimation ratio (0.5 = half)")
    scan_decimate.set_defaults(func=cmd_scan)

    # Scan hollow
    scan_hollow = scan_subparsers.add_parser("hollow", help="Make hollow for material savings")
    scan_hollow.add_argument("input", help="Input scan file")
    scan_hollow.add_argument("--output", "-o", help="Output file path")
    scan_hollow.add_argument("--format", choices=["stl", "obj", "ply"], default="stl")
    scan_hollow.add_argument("--wall-thickness", type=float, default=2.0,
                             help="Wall thickness in mm")
    scan_hollow.set_defaults(func=cmd_scan)

    # Scan case
    scan_case = scan_subparsers.add_parser("case", help="Generate protective case from scan")
    scan_case.add_argument("input", help="Input scan file")
    scan_case.add_argument("--output", "-o", help="Output file path")
    scan_case.add_argument("--format", choices=["stl", "obj", "ply"], default="stl")
    scan_case.add_argument("--case-type",
                           choices=["full_case", "bumper", "cradle", "sleeve"],
                           default="full_case", help="Type of case")
    scan_case.add_argument("--wall-thickness", type=float, default=1.5,
                           help="Case wall thickness in mm")
    scan_case.add_argument("--clearance", type=float, default=0.3,
                           help="Clearance gap for fit in mm")
    scan_case.set_defaults(func=cmd_scan)

    # Scan mount
    scan_mount = scan_subparsers.add_parser("mount", help="Generate wall mount from scan")
    scan_mount.add_argument("input", help="Input scan file")
    scan_mount.add_argument("--output", "-o", help="Output file path")
    scan_mount.add_argument("--format", choices=["stl", "obj", "ply"], default="stl")
    scan_mount.add_argument("--wall-thickness", type=float, default=2.0,
                            help="Mount thickness in mm")
    scan_mount.add_argument("--clearance", type=float, default=0.3,
                            help="Clearance gap in mm")
    scan_mount.set_defaults(func=cmd_scan)

    # Scan stand
    scan_stand = scan_subparsers.add_parser("stand", help="Generate angled stand from scan")
    scan_stand.add_argument("input", help="Input scan file")
    scan_stand.add_argument("--output", "-o", help="Output file path")
    scan_stand.add_argument("--format", choices=["stl", "obj", "ply"], default="stl")
    scan_stand.add_argument("--angle", type=float, default=60.0,
                            help="Stand angle in degrees")
    scan_stand.add_argument("--wall-thickness", type=float, default=2.0,
                            help="Stand thickness in mm")
    scan_stand.add_argument("--clearance", type=float, default=0.3,
                            help="Clearance gap in mm")
    scan_stand.set_defaults(func=cmd_scan)

    # Scan cradle
    scan_cradle = scan_subparsers.add_parser("cradle", help="Generate cradle holder from scan")
    scan_cradle.add_argument("input", help="Input scan file")
    scan_cradle.add_argument("--output", "-o", help="Output file path")
    scan_cradle.add_argument("--format", choices=["stl", "obj", "ply"], default="stl")
    scan_cradle.add_argument("--wall-thickness", type=float, default=2.0,
                             help="Cradle thickness in mm")
    scan_cradle.add_argument("--clearance", type=float, default=0.3,
                             help="Clearance gap in mm")
    scan_cradle.set_defaults(func=cmd_scan)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Handle scan command with no subcommand
    if args.command == "scan" and not args.scan_action:
        scan_parser.print_help()
        sys.exit(0)

    # Run the command
    args.func(args)


if __name__ == "__main__":
    main()
