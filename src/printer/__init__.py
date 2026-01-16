"""Bamboo Labs printer communication module."""

from .connection import BambooConnection, PrinterStatus, PrinterState
from .commands import PrinterCommands, PrintResult, SpeedLevel, LightMode
from .file_transfer import PrinterFileTransfer, TransferResult, FileInfo
from .mock import MockPrinter, MockBambooConnection, create_mock_printer

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
]
