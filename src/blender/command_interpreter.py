"""
Natural Language Command Interpreter for Blender.

Parses natural language design commands and converts them to
structured commands for the Blender interactive addon.

Examples:
    "make it 2 inches taller"
    "rotate 25 degrees"
    "add a 25 degree angle"
    "scale it up by 1.5"
    "make the walls 3mm thick"
"""

import json
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# Communication files
COMMAND_FILE = Path.home() / ".claude" / "blender_commands.json"
RESPONSE_FILE = Path.home() / ".claude" / "blender_response.json"

# Ensure directory exists
COMMAND_FILE.parent.mkdir(parents=True, exist_ok=True)


def parse_measurement(text: str) -> Tuple[float, str]:
    """
    Parse a measurement from text.
    Returns (value, unit) tuple.
    """
    text = text.lower().strip()

    # Common patterns
    patterns = [
        r'([\d.]+)\s*(inch|inches|in|")',
        r'([\d.]+)\s*(cm|centimeter|centimeters)',
        r'([\d.]+)\s*(mm|millimeter|millimeters)',
        r'([\d.]+)\s*(meter|meters|m)',
        r'([\d.]+)',  # Default to mm
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1))
            unit = match.group(2) if len(match.groups()) > 1 else 'mm'

            # Normalize unit
            if unit in ('inch', 'inches', 'in', '"'):
                unit = 'inches'
            elif unit in ('cm', 'centimeter', 'centimeters'):
                unit = 'cm'
            elif unit in ('meter', 'meters', 'm'):
                unit = 'm'
            else:
                unit = 'mm'

            return value, unit

    return 0, 'mm'


def to_mm(value: float, unit: str) -> float:
    """Convert measurement to millimeters."""
    conversions = {
        'inches': 25.4,
        'cm': 10,
        'm': 1000,
        'mm': 1,
    }
    return value * conversions.get(unit, 1)


def parse_angle(text: str) -> float:
    """Parse angle from text."""
    match = re.search(r'([\d.]+)\s*(?:degree|degrees|deg|°)?', text.lower())
    if match:
        return float(match.group(1))
    return 0


def interpret_command(text: str) -> Optional[Dict[str, Any]]:
    """
    Interpret natural language command and return structured command.

    Args:
        text: Natural language command like "make it 2 inches taller"

    Returns:
        Structured command dict or None if not understood
    """
    text = text.lower().strip()

    # Add (import without replacing) commands
    add_match = re.search(r'(?:add|bring in|import additional)\s+(?:the\s+)?(?:file\s+)?["\']?([^"\']+)["\']?', text)
    if add_match and 'spike' not in text and 'horn' not in text:
        return {"action": "add", "params": {"file": add_match.group(1).strip()}}

    # Combine/Join commands
    if any(word in text for word in ['combine', 'join', 'merge all', 'join all']):
        return {"action": "combine", "params": {}}

    # Load/Open commands (replaces current)
    load_match = re.search(r'(?:load|open|replace with)\s+(?:the\s+)?(?:file\s+)?["\']?([^"\']+)["\']?', text)
    if load_match:
        return {"action": "load", "params": {"file": load_match.group(1).strip()}}

    # Height commands
    if any(word in text for word in ['taller', 'shorter', 'height']):
        value, unit = parse_measurement(text)
        value_mm = to_mm(value, unit)

        if 'taller' in text:
            return {"action": "height", "params": {"value": value_mm, "relative": True}}
        elif 'shorter' in text:
            return {"action": "height", "params": {"value": -value_mm, "relative": True}}
        else:
            # Set absolute height
            return {"action": "height", "params": {"value": value_mm, "relative": False}}

    # Width commands
    if any(word in text for word in ['wider', 'narrower', 'width']):
        value, unit = parse_measurement(text)
        value_mm = to_mm(value, unit)

        if 'wider' in text:
            return {"action": "width", "params": {"value": value_mm, "relative": True}}
        elif 'narrower' in text:
            return {"action": "width", "params": {"value": -value_mm, "relative": True}}
        else:
            return {"action": "width", "params": {"value": value_mm, "relative": False}}

    # Rotation/Angle commands
    if any(word in text for word in ['rotate', 'tilt', 'angle', 'turn']):
        angle = parse_angle(text)

        # Determine axis
        axis = 'x'  # Default
        if any(word in text for word in ['left', 'right', 'horizontal', 'yaw']):
            axis = 'z'
        elif any(word in text for word in ['forward', 'backward', 'pitch']):
            axis = 'x'
        elif any(word in text for word in ['roll', 'side']):
            axis = 'y'

        # Check for axis specification
        axis_match = re.search(r'\b([xyz])\s*(?:axis|direction)?', text)
        if axis_match:
            axis = axis_match.group(1)

        return {"action": "rotate", "params": {"angle": angle, "axis": axis}}

    # Scale commands
    if any(word in text for word in ['scale', 'bigger', 'smaller', 'larger']):
        # Look for factor
        factor_match = re.search(r'(?:by\s+)?([\d.]+)\s*(?:x|times)?', text)
        if factor_match:
            factor = float(factor_match.group(1))
        else:
            factor = 1.5 if 'bigger' in text or 'larger' in text else 0.75

        if 'smaller' in text and factor > 1:
            factor = 1 / factor

        return {"action": "scale", "params": {"factor": factor}}

    # Hollow commands
    if any(word in text for word in ['hollow', 'shell', 'empty']):
        value, unit = parse_measurement(text)
        if value == 0:
            value = 2  # Default 2mm
        value_mm = to_mm(value, unit)
        return {"action": "hollow", "params": {"thickness": value_mm}}

    # Wall thickness commands
    if any(word in text for word in ['wall', 'thick', 'thicken']):
        value, unit = parse_measurement(text)
        if value == 0:
            value = 2
        value_mm = to_mm(value, unit)
        return {"action": "thicken", "params": {"thickness": value_mm}}

    # Smooth commands
    if any(word in text for word in ['smooth', 'subdivide', 'refine']):
        iter_match = re.search(r'(\d+)\s*(?:times?|iterations?|levels?)', text)
        iterations = int(iter_match.group(1)) if iter_match else 1
        return {"action": "smooth", "params": {"iterations": iterations}}

    # Bevel commands
    if any(word in text for word in ['bevel', 'round', 'chamfer', 'edges']):
        value, unit = parse_measurement(text)
        if value == 0:
            value = 1
        value_mm = to_mm(value, unit)
        return {"action": "bevel", "params": {"amount": value_mm}}

    # Spike/horn commands
    if any(word in text for word in ['spike', 'spikes', 'horn', 'horns']):
        # Look for count
        count_match = re.search(r'(\d+)\s*(?:spike|horn)', text)
        count = int(count_match.group(1)) if count_match else 5
        return {"action": "add_spikes", "params": {"count": count}}

    # Color commands - "make the top red", "paint it blue", "color the bottom green"
    color_names = ['red', 'green', 'blue', 'yellow', 'orange', 'purple', 'pink', 'cyan',
                   'magenta', 'white', 'black', 'gray', 'grey', 'brown', 'tan', 'beige',
                   'gold', 'silver', 'copper', 'bronze']
    region_names = ['top', 'bottom', 'front', 'back', 'left', 'right', 'sides', 'all',
                    'upper', 'lower', 'base', 'head', 'everywhere', 'whole', 'entire']

    if any(word in text for word in ['color', 'paint', 'make', 'set']):
        # Find color
        found_color = None
        for color in color_names:
            if color in text:
                found_color = color
                break
        # Also check for hex colors
        hex_match = re.search(r'#[0-9a-fA-F]{3,6}', text)
        if hex_match:
            found_color = hex_match.group(0)

        if found_color:
            # Find region
            found_region = 'all'  # Default
            for region in region_names:
                if region in text:
                    found_region = region
                    break

            return {"action": "set_color", "params": {"color": found_color, "region": found_region}}

    # Material assignment - "use TPU on the bottom", "make the base flexible"
    material_names = ['pla', 'petg', 'tpu', 'abs', 'asa', 'pa', 'nylon', 'pc', 'polycarbonate']
    material_aliases = {
        'flexible': 'tpu', 'rubber': 'tpu', 'soft': 'tpu',
        'strong': 'petg', 'durable': 'petg',
        'tough': 'pa', 'industrial': 'pa',
        'clear': 'pc', 'transparent': 'pc',
        'heat resistant': 'abs', 'outdoor': 'asa',
    }

    if any(word in text for word in ['material', 'use', 'assign', 'filament']):
        # Find material
        found_material = None
        for mat in material_names:
            if mat in text:
                found_material = mat
                break
        if not found_material:
            for alias, mat in material_aliases.items():
                if alias in text:
                    found_material = mat
                    break

        if found_material:
            # Find region
            found_region = 'all'
            for region in region_names:
                if region in text:
                    found_region = region
                    break

            return {"action": "set_material", "params": {"material": found_material, "region": found_region}}

    # List colors command
    if any(phrase in text for phrase in ['list color', 'show color', 'available color', 'what color']):
        return {"action": "list_colors", "params": {}}

    # List regions command
    if any(phrase in text for phrase in ['list region', 'show region', 'available region', 'what region']):
        return {"action": "list_regions", "params": {}}

    # 3MF Export commands - "export as 3mf", "export multicolor", "save for bambu"
    if any(phrase in text for phrase in ['3mf', 'multicolor', 'multi-color', 'multi color', 'bambu', 'bamboo', 'bambu studio']):
        export_match = re.search(r'(?:export|save)\s+(?:to\s+|as\s+)?["\']?([^"\']+\.3mf)["\']?', text)
        if export_match:
            filepath = export_match.group(1).strip()
        else:
            filepath = 'output/model.3mf'
        return {"action": "export_3mf", "params": {"file": filepath}}

    # Export/Save commands
    export_match = re.search(r'(?:export|save)\s+(?:to\s+|as\s+)?["\']?([^"\']+)["\']?', text)
    if export_match:
        return {"action": "export", "params": {"file": export_match.group(1).strip()}}

    # Status/Info commands (check before view commands)
    if any(word in text for word in ['status', 'info', 'dimensions', 'size', 'measure', 'how big', 'how tall', 'how wide']):
        return {"action": "status", "params": {}}

    # View commands
    if any(word in text for word in ['view', 'look', 'camera']):
        direction = 'front'
        for d in ['front', 'back', 'left', 'right', 'top', 'bottom']:
            if d in text:
                direction = d
                break
        return {"action": "view", "params": {"direction": direction}}

    # Undo/Redo
    if 'undo' in text:
        return {"action": "undo", "params": {}}
    if 'redo' in text:
        return {"action": "redo", "params": {}}

    # Help
    if 'help' in text:
        return {"action": "help", "params": {}}

    # Reset
    if any(word in text for word in ['reset', 'revert', 'original']):
        return {"action": "reset", "params": {}}

    return None


def send_command(cmd: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
    """
    Send command to Blender and wait for response.

    Args:
        cmd: Command dictionary
        timeout: Max seconds to wait for response

    Returns:
        Response dictionary from Blender
    """
    # Write command
    with open(COMMAND_FILE, 'w') as f:
        json.dump(cmd, f)

    # Wait for response
    start_time = time.time()
    cmd_time = COMMAND_FILE.stat().st_mtime

    while time.time() - start_time < timeout:
        if RESPONSE_FILE.exists():
            try:
                resp_time = RESPONSE_FILE.stat().st_mtime
                if resp_time > cmd_time:
                    with open(RESPONSE_FILE, 'r') as f:
                        return json.load(f)
            except:
                pass
        time.sleep(0.1)

    return {"success": False, "message": "Timeout waiting for Blender response"}


def execute_natural_command(text: str) -> Dict[str, Any]:
    """
    Parse and execute a natural language command.

    Args:
        text: Natural language command

    Returns:
        Response from Blender
    """
    cmd = interpret_command(text)
    if cmd is None:
        return {
            "success": False,
            "message": f"Could not understand: '{text}'. Try 'help' for available commands."
        }

    return send_command(cmd)


def is_blender_connected() -> bool:
    """Check if Blender interactive mode is running."""
    if not RESPONSE_FILE.exists():
        return False

    try:
        # Check if response file is recent (within 10 seconds)
        mtime = RESPONSE_FILE.stat().st_mtime
        return time.time() - mtime < 10
    except:
        return False


# Example usage and testing
if __name__ == "__main__":
    # Test command interpretation
    test_commands = [
        "make it 2 inches taller",
        "rotate 25 degrees",
        "add a 25 degree angle on the x axis",
        "scale it up by 1.5",
        "make the walls 3mm thick",
        "hollow it out with 2mm walls",
        "show me the dimensions",
        "export to output/modified.stl",
        "make it 50mm wide",
        "tilt it forward 15 degrees",
        "smooth it 2 times",
        "round the edges by 1mm",
        "undo",
        "load test_scans/phone_mockup.stl",
    ]

    print("Command Interpretation Test")
    print("=" * 50)

    for cmd_text in test_commands:
        result = interpret_command(cmd_text)
        print(f"\nInput: '{cmd_text}'")
        print(f"Parsed: {json.dumps(result, indent=2)}")
