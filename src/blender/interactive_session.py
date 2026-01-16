#!/usr/bin/env python3
"""
Interactive Design Session with Blender.

This script launches Blender with the interactive addon and provides
a command interface for natural language design iteration.

Usage:
    python src/blender/interactive_session.py scan.stl

    # Then use natural language commands:
    > make it 2 inches taller
    > add a 25 degree angle
    > show me the dimensions
    > export to output/my_case.stl
    > print it
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.blender.command_interpreter import (
    interpret_command,
    send_command,
    execute_natural_command,
    is_blender_connected,
    COMMAND_FILE,
    RESPONSE_FILE,
)


def launch_blender(scan_file: str = None) -> subprocess.Popen:
    """
    Launch Blender with the interactive addon.

    Args:
        scan_file: Optional scan file to load on startup

    Returns:
        Blender subprocess
    """
    addon_path = project_root / "src" / "blender" / "interactive_addon.py"

    cmd = [
        "blender",
        "--python", str(addon_path),
    ]

    # Add scan file to load
    if scan_file:
        # Create startup script to load the file
        startup_script = f'''
import bpy
import sys
sys.path.insert(0, "{project_root}")

# Wait for addon to initialize
import time
time.sleep(0.5)

# Load the scan file
from src.blender.command_interpreter import send_command
send_command({{"action": "load", "params": {{"file": "{os.path.abspath(scan_file)}"}}}})
'''
        startup_file = COMMAND_FILE.parent / "blender_startup.py"
        with open(startup_file, 'w') as f:
            f.write(startup_script)

        cmd.extend(["--python", str(startup_file)])

    print(f"Launching Blender...")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return process


def wait_for_blender(timeout: float = 30.0) -> bool:
    """Wait for Blender to be ready."""
    print("Waiting for Blender to start...")
    start = time.time()

    while time.time() - start < timeout:
        if is_blender_connected():
            return True
        time.sleep(0.5)
        print(".", end="", flush=True)

    print()
    return False


def format_response(response: dict) -> str:
    """Format response for display."""
    lines = []

    if response.get("success"):
        lines.append(f"✓ {response.get('message', 'Done')}")
    else:
        lines.append(f"✗ {response.get('message', 'Failed')}")

    data = response.get("data", {})

    if "dimensions" in data:
        dims = data["dimensions"]
        lines.append(f"\n  Dimensions:")
        lines.append(f"    {dims.get('width', 0):.1f} x {dims.get('depth', 0):.1f} x {dims.get('height', 0):.1f} mm")
        if 'width_inches' in dims:
            lines.append(f"    {dims.get('width_inches', 0):.2f} x {dims.get('depth_inches', 0):.2f} x {dims.get('height_inches', 0):.2f} inches")

    if "commands" in data:
        lines.append("\n  Available commands:")
        for cmd in data["commands"]:
            lines.append(f"    {cmd}")

    if "filepath" in data:
        lines.append(f"\n  Saved to: {data['filepath']}")

    return "\n".join(lines)


def interactive_loop(blender_process: subprocess.Popen):
    """Run the interactive command loop."""
    print("\n" + "="*60)
    print("Interactive Design Mode")
    print("="*60)
    print("\nCommands:")
    print("  Natural language: 'make it 2 inches taller', 'rotate 25 degrees'")
    print("  status     - Show current dimensions")
    print("  undo       - Undo last change")
    print("  export     - Save to file")
    print("  print      - Send to printer (mock)")
    print("  help       - Show all commands")
    print("  quit/exit  - Exit session")
    print("="*60 + "\n")

    while True:
        try:
            # Check if Blender is still running
            if blender_process.poll() is not None:
                print("\nBlender closed. Exiting...")
                break

            # Get user input
            user_input = input("design> ").strip()

            if not user_input:
                continue

            # Handle special commands
            if user_input.lower() in ('quit', 'exit', 'q'):
                print("Exiting interactive mode...")
                break

            if user_input.lower() == 'print':
                # Export and print with mock printer
                print("Exporting for printing...")
                export_response = execute_natural_command("export to output/design_to_print.stl")
                print(format_response(export_response))

                if export_response.get("success"):
                    print("\nStarting mock print...")
                    from src.printer import create_mock_printer
                    printer = create_mock_printer()
                    printer.connect()
                    printer.upload_file("design_to_print.stl", 10000)
                    result = printer.start_print("design_to_print.stl")
                    if result.success:
                        print("✓ Print started on mock printer")
                        print("  Run 'python -m src.pipeline.cli --mock status' to monitor")
                    printer.disconnect()
                continue

            # Execute natural language command
            response = execute_natural_command(user_input)
            print(format_response(response))
            print()

        except KeyboardInterrupt:
            print("\n\nInterrupted. Exiting...")
            break
        except EOFError:
            break


def main():
    parser = argparse.ArgumentParser(
        description="Interactive design session with Blender",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s test_scans/phone_mockup.stl

  Then use natural language commands:
    design> make it 2 inches taller
    design> add a 25 degree angle
    design> show me the dimensions
    design> export to output/my_case.stl
    design> print
        """
    )

    parser.add_argument("scan_file", nargs="?",
                        help="Scan file to load (STL, OBJ, PLY)")
    parser.add_argument("--no-launch", action="store_true",
                        help="Don't launch Blender (connect to existing)")

    args = parser.parse_args()

    blender_process = None

    try:
        if not args.no_launch:
            blender_process = launch_blender(args.scan_file)

            if not wait_for_blender():
                print("\nError: Blender failed to start or connect")
                print("Make sure Blender is installed: brew install --cask blender")
                sys.exit(1)

            print("\n✓ Blender connected!")

            # If scan file provided, load it
            if args.scan_file:
                print(f"\nLoading scan: {args.scan_file}")
                time.sleep(1)  # Give Blender time to load
                response = execute_natural_command(f"load {args.scan_file}")
                print(format_response(response))
        else:
            if not is_blender_connected():
                print("Error: Blender not connected. Run without --no-launch first.")
                sys.exit(1)
            print("✓ Connected to existing Blender session")

        # Run interactive loop
        interactive_loop(blender_process or subprocess.Popen(["sleep", "infinity"]))

    finally:
        if blender_process and blender_process.poll() is None:
            print("\nClosing Blender...")
            blender_process.terminate()
            blender_process.wait(timeout=5)


if __name__ == "__main__":
    main()
