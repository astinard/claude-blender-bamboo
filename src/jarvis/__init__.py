"""JARVIS module for Claude Fab Lab.

Provides voice control and dashboard capabilities for print monitoring.
"""

from src.jarvis.dashboard import (
    Dashboard,
    DashboardConfig,
    PrintStatus,
    TemperatureData,
    PrintProgress,
    create_dashboard,
)
from src.jarvis.voice_control import (
    VoiceController,
    VoiceCommand,
    CommandCategory,
    CommandResult,
    create_voice_controller,
)

__all__ = [
    "Dashboard",
    "DashboardConfig",
    "PrintStatus",
    "TemperatureData",
    "PrintProgress",
    "create_dashboard",
    "VoiceController",
    "VoiceCommand",
    "CommandCategory",
    "CommandResult",
    "create_voice_controller",
]
