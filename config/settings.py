"""
Configuration settings for Blender + Bamboo Labs integration.

Copy this file to settings_local.py and fill in your actual values.
settings_local.py is gitignored for security.
"""

import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMP_DIR = PROJECT_ROOT / "temp"

# Ensure output directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

# Bamboo Labs Printer Configuration
# Override these in settings_local.py or via environment variables
PRINTER_IP = os.getenv("BAMBOO_PRINTER_IP", "192.168.1.100")
PRINTER_ACCESS_CODE = os.getenv("BAMBOO_ACCESS_CODE", "your_access_code")
PRINTER_SERIAL = os.getenv("BAMBOO_SERIAL", "your_serial_number")

# MQTT Settings
MQTT_PORT = 8883
MQTT_USERNAME = "bblp"

# Blender Settings
BLENDER_EXECUTABLE = os.getenv("BLENDER_PATH", "blender")
DEFAULT_EXPORT_FORMAT = "stl"  # or "3mf"

# File paths
DEFAULT_OUTPUT_PATH = OUTPUT_DIR / "model.stl"


def load_local_settings():
    """Load local settings if they exist."""
    local_settings_path = Path(__file__).parent / "settings_local.py"
    if local_settings_path.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("settings_local", local_settings_path)
        local_settings = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(local_settings)

        # Override globals with local settings
        for key in dir(local_settings):
            if key.isupper():
                globals()[key] = getattr(local_settings, key)


# Load local overrides
load_local_settings()
