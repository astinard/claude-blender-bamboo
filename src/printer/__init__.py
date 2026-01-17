"""Bamboo Labs printer communication module."""

from .connection import BambooConnection, PrinterStatus, PrinterState
from .commands import PrinterCommands, PrintResult, SpeedLevel, LightMode
from .file_transfer import PrinterFileTransfer, TransferResult, FileInfo
from .mock import MockPrinter, MockBambooConnection, create_mock_printer
from .bambu_real import (
    BambuRealPrinter,
    AMSSlotInfo,
    AMSStatus,
    PrintStage,
    create_real_printer,
)
from .ams_manager import (
    AMSManager,
    AMSSlot,
    FilamentInfo,
    create_ams_manager_with_defaults,
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
]
