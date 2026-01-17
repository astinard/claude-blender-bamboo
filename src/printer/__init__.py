"""Bamboo Labs printer communication module."""

from .connection import BambooConnection, PrinterStatus, PrinterState
from .commands import PrinterCommands, PrintResult, SpeedLevel, LightMode
from .file_transfer import PrinterFileTransfer, TransferResult, FileInfo
from .mock import MockPrinter, MockBambooConnection, create_mock_printer

# BambuRealPrinter requires paho-mqtt, make it optional
try:
    from .bambu_real import (
        BambuRealPrinter,
        AMSSlotInfo,
        AMSStatus,
        PrintStage,
        create_real_printer,
    )
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    BambuRealPrinter = None
    AMSSlotInfo = None
    AMSStatus = None
    PrintStage = None
    create_real_printer = None

from .ams_manager import (
    AMSManager,
    AMSSlot,
    FilamentInfo,
    create_ams_manager_with_defaults,
)
from .print_preview import (
    PrintPreview,
    PrintPreviewGenerator,
    PrintPreviewWarning,
    ColorUsage,
    create_print_preview,
)

__all__ = [
    # Connection
    "BambooConnection",
    "PrinterStatus",
    "PrinterState",
    # Commands
    "PrinterCommands",
    "PrintResult",
    "SpeedLevel",
    "LightMode",
    # File Transfer
    "PrinterFileTransfer",
    "TransferResult",
    "FileInfo",
    # Mock
    "MockPrinter",
    "MockBambooConnection",
    "create_mock_printer",
    # Real Printer
    "BambuRealPrinter",
    "AMSSlotInfo",
    "AMSStatus",
    "PrintStage",
    "create_real_printer",
    # AMS Manager
    "AMSManager",
    "AMSSlot",
    "FilamentInfo",
    "create_ams_manager_with_defaults",
    # Print Preview
    "PrintPreview",
    "PrintPreviewGenerator",
    "PrintPreviewWarning",
    "ColorUsage",
    "create_print_preview",
]
