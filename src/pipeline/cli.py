#!/usr/bin/env python3
"""
Command-line interface for Blender-Bamboo pipeline.

Usage:
    blender-bamboo create cube --size 20 --output cube.stl
    blender-bamboo print cube.stl --printer-ip 192.168.1.100
    blender-bamboo status --printer-ip 192.168.1.100
    blender-bamboo workflow cube --size 20 --auto-print
"""

import argparse
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Run the command
    args.func(args)


if __name__ == "__main__":
    main()
