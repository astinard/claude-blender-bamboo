#!/usr/bin/env python3
"""
Design helper for Claude Code integration.

This module provides simple functions for Claude Code to interact with
Blender for visual design iteration.

Usage in Claude Code:
    from src.blender.design import design, start_blender, status

    # Start Blender with a scan
    start_blender("test_scans/phone_mockup.stl")

    # Send natural language commands
    design("make it 2 inches taller")
    design("add a 25 degree angle")
    design("show me the dimensions")

    # Export when ready
    design("export to output/my_design.stl")
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to path
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.blender.command_interpreter import (
    execute_natural_command,
    send_command,
    is_blender_connected,
    COMMAND_FILE,
    RESPONSE_FILE,
)

# Track Blender process
_blender_process: Optional[subprocess.Popen] = None


def start_blender(scan_file: Optional[str] = None, wait: bool = True) -> Dict[str, Any]:
    """
    Start Blender with interactive mode.

    Args:
        scan_file: Optional scan file to load
        wait: Wait for Blender to be ready

    Returns:
        Status dict with success and message
    """
    global _blender_process

    if _blender_process and _blender_process.poll() is None:
        return {"success": True, "message": "Blender already running"}

    addon_path = project_root / "src" / "blender" / "interactive_addon.py"

    cmd = ["blender", "--python", str(addon_path)]

    print(f"Starting Blender...")
    _blender_process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if wait:
        # Wait for Blender to be ready
        for _ in range(60):  # 30 second timeout
            if is_blender_connected():
                break
            time.sleep(0.5)
        else:
            return {"success": False, "message": "Blender failed to start"}

    # Load scan file if provided
    if scan_file:
        time.sleep(1)  # Give Blender time to fully initialize
        return load(scan_file)

    return {"success": True, "message": "Blender started"}


def stop_blender() -> Dict[str, Any]:
    """Stop the Blender process."""
    global _blender_process

    if _blender_process and _blender_process.poll() is None:
        _blender_process.terminate()
        _blender_process.wait(timeout=5)
        _blender_process = None
        return {"success": True, "message": "Blender stopped"}

    return {"success": True, "message": "Blender was not running"}


def is_running() -> bool:
    """Check if Blender is running and connected."""
    return is_blender_connected()


def design(command: str) -> Dict[str, Any]:
    """
    Send a natural language design command to Blender.

    Args:
        command: Natural language command like "make it 2 inches taller"

    Returns:
        Response dict with success, message, and data
    """
    if not is_blender_connected():
        return {
            "success": False,
            "message": "Blender not connected. Run start_blender() first."
        }

    return execute_natural_command(command)


def load(filepath: str) -> Dict[str, Any]:
    """
    Load a scan file into Blender.

    Args:
        filepath: Path to STL, OBJ, or PLY file

    Returns:
        Response dict
    """
    filepath = str(Path(filepath).resolve())
    if not Path(filepath).exists():
        return {"success": False, "message": f"File not found: {filepath}"}

    return send_command({"action": "load", "params": {"file": filepath}})


def status() -> Dict[str, Any]:
    """Get current object dimensions and status."""
    return design("status")


def height(value: str) -> Dict[str, Any]:
    """
    Set or adjust height.

    Args:
        value: Height like "2 inches", "50mm", or "+10mm"
    """
    if value.startswith('+'):
        return design(f"make it {value[1:]} taller")
    elif value.startswith('-'):
        return design(f"make it {value[1:]} shorter")
    else:
        return design(f"set height to {value}")


def width(value: str) -> Dict[str, Any]:
    """Set or adjust width."""
    if value.startswith('+'):
        return design(f"make it {value[1:]} wider")
    elif value.startswith('-'):
        return design(f"make it {value[1:]} narrower")
    else:
        return design(f"set width to {value}")


def rotate(angle: float, axis: str = "x") -> Dict[str, Any]:
    """
    Rotate the object.

    Args:
        angle: Angle in degrees
        axis: Rotation axis (x, y, or z)
    """
    return design(f"rotate {angle} degrees on {axis} axis")


def scale(factor: float) -> Dict[str, Any]:
    """
    Scale the object uniformly.

    Args:
        factor: Scale factor (1.5 = 50% bigger)
    """
    return design(f"scale by {factor}")


def hollow(thickness: str = "2mm") -> Dict[str, Any]:
    """Make the object hollow with specified wall thickness."""
    return design(f"make it hollow with {thickness} walls")


def smooth(iterations: int = 1) -> Dict[str, Any]:
    """Smooth the mesh."""
    return design(f"smooth it {iterations} times")


def bevel(amount: str = "1mm") -> Dict[str, Any]:
    """Round the edges."""
    return design(f"bevel edges by {amount}")


def undo() -> Dict[str, Any]:
    """Undo last change."""
    return design("undo")


def redo() -> Dict[str, Any]:
    """Redo last undone change."""
    return design("redo")


def export(filepath: str) -> Dict[str, Any]:
    """
    Export the design to a file.

    Args:
        filepath: Output path (STL or OBJ)
    """
    filepath = str(Path(filepath).resolve())
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    return design(f"export to {filepath}")


def view(direction: str = "front") -> Dict[str, Any]:
    """
    Change the view direction.

    Args:
        direction: front, back, left, right, top, bottom
    """
    return design(f"view from {direction}")


def fit_view() -> Dict[str, Any]:
    """Fit the view to show the entire object."""
    return send_command({"action": "fit", "params": {}})


def help_commands() -> Dict[str, Any]:
    """Get list of available commands."""
    return design("help")


# Convenience function for quick testing
def quick_demo():
    """Quick demo of the design functions."""
    print("Starting Blender...")
    result = start_blender("test_scans/phone_mockup.stl")
    print(f"  {result['message']}")

    print("\nCurrent status:")
    result = status()
    if result.get("data", {}).get("dimensions"):
        dims = result["data"]["dimensions"]
        print(f"  {dims['width']:.1f} x {dims['depth']:.1f} x {dims['height']:.1f} mm")

    print("\nMaking it 1 inch taller...")
    result = height("+1 inch")
    print(f"  {result['message']}")

    print("\nRotating 15 degrees...")
    result = rotate(15)
    print(f"  {result['message']}")

    print("\nFinal status:")
    result = status()
    if result.get("data", {}).get("dimensions"):
        dims = result["data"]["dimensions"]
        print(f"  {dims['width']:.1f} x {dims['depth']:.1f} x {dims['height']:.1f} mm")

    print("\nBlender window is open - make more changes there!")
    print("Or use design() function to send more commands.")


if __name__ == "__main__":
    quick_demo()
