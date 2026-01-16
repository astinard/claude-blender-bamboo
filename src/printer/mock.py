"""
Mock printer for testing without hardware.

Simulates a Bamboo Labs printer for development and testing.
"""

import time
import threading
from typing import Optional, Callable, List
from dataclasses import dataclass

from .connection import BambooConnection, PrinterStatus, PrinterState
from .commands import PrinterCommands, PrintResult
from .file_transfer import PrinterFileTransfer, TransferResult, FileInfo


class MockPrinter:
    """
    Simulated Bamboo Labs printer for testing.

    Provides realistic simulation of printer behavior without hardware.
    """

    def __init__(self):
        """Initialize mock printer."""
        self._status = PrinterStatus(
            state=PrinterState.IDLE,
            bed_temp=25.0,
            nozzle_temp=25.0
        )
        self._callbacks: List[Callable[[PrinterStatus], None]] = []
        self._print_thread: Optional[threading.Thread] = None
        self._printing = False
        self._print_progress = 0.0
        self._files: List[FileInfo] = []
        self._connected = False

    def connect(self) -> bool:
        """Simulate connection."""
        time.sleep(0.5)  # Simulate connection delay
        self._connected = True
        return True

    def disconnect(self):
        """Simulate disconnection."""
        self._connected = False
        self._stop_print_simulation()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def status(self) -> PrinterStatus:
        return self._status

    def add_status_callback(self, callback: Callable[[PrinterStatus], None]):
        self._callbacks.append(callback)

    def _notify_callbacks(self):
        """Notify all callbacks of status change."""
        for callback in self._callbacks:
            try:
                callback(self._status)
            except Exception as e:
                print(f"Callback error: {e}")

    def upload_file(self, filename: str, size: int = 1024) -> TransferResult:
        """Simulate file upload."""
        time.sleep(size / 1024 / 100)  # Simulate transfer time
        self._files.append(FileInfo(
            name=filename,
            size=size,
            is_directory=False,
            path=f"/cache/{filename}"
        ))
        return TransferResult(
            success=True,
            message="Upload successful",
            remote_path=f"/cache/{filename}",
            bytes_transferred=size
        )

    def start_print(self, filename: str) -> PrintResult:
        """Start a simulated print."""
        # Check if file exists
        file_exists = any(f.name == filename for f in self._files)
        if not file_exists:
            return PrintResult(
                success=False,
                message=f"File not found: {filename}"
            )

        if self._status.state != PrinterState.IDLE:
            return PrintResult(
                success=False,
                message=f"Printer not idle (state: {self._status.state.value})"
            )

        self._printing = True
        self._print_progress = 0.0
        self._status.state = PrinterState.PRINTING
        self._status.current_file = filename
        self._status.progress = 0

        # Start simulation thread
        self._print_thread = threading.Thread(target=self._simulate_print)
        self._print_thread.daemon = True
        self._print_thread.start()

        return PrintResult(
            success=True,
            message=f"Started printing: {filename}"
        )

    def _simulate_print(self):
        """Simulate print progress in background."""
        total_layers = 100
        self._status.layer_total = total_layers

        # Simulate heating
        self._status.state = PrinterState.PREPARING
        self._status.bed_temp_target = 60
        self._status.nozzle_temp_target = 210

        # Heat bed
        while self._printing and self._status.bed_temp < 60:
            time.sleep(0.2)
            self._status.bed_temp = min(60, self._status.bed_temp + 2)
            self._notify_callbacks()

        # Heat nozzle
        while self._printing and self._status.nozzle_temp < 210:
            time.sleep(0.1)
            self._status.nozzle_temp = min(210, self._status.nozzle_temp + 5)
            self._notify_callbacks()

        if not self._printing:
            return

        self._status.state = PrinterState.PRINTING

        # Simulate printing
        while self._printing and self._print_progress < 100:
            time.sleep(0.5)  # Each "layer" takes 0.5 seconds
            self._print_progress += 1
            self._status.progress = self._print_progress
            self._status.layer_current = int(self._print_progress)
            self._status.remaining_time = int((100 - self._print_progress) * 30)
            self._notify_callbacks()

        if self._printing:
            # Print finished
            self._status.state = PrinterState.FINISHED
            self._status.progress = 100
            self._notify_callbacks()

            # Cool down
            time.sleep(1)
            self._status.bed_temp_target = 0
            self._status.nozzle_temp_target = 0

            while self._status.nozzle_temp > 50:
                time.sleep(0.2)
                self._status.nozzle_temp = max(25, self._status.nozzle_temp - 3)
                self._status.bed_temp = max(25, self._status.bed_temp - 1)
                self._notify_callbacks()

    def pause_print(self) -> PrintResult:
        """Pause the current print."""
        if self._status.state != PrinterState.PRINTING:
            return PrintResult(
                success=False,
                message="Not printing"
            )

        self._status.state = PrinterState.PAUSED
        self._notify_callbacks()
        return PrintResult(success=True, message="Paused")

    def resume_print(self) -> PrintResult:
        """Resume paused print."""
        if self._status.state != PrinterState.PAUSED:
            return PrintResult(
                success=False,
                message="Not paused"
            )

        self._status.state = PrinterState.PRINTING
        self._notify_callbacks()
        return PrintResult(success=True, message="Resumed")

    def stop_print(self) -> PrintResult:
        """Stop the current print."""
        self._stop_print_simulation()
        self._status.state = PrinterState.IDLE
        self._status.progress = 0
        self._status.current_file = ""
        self._notify_callbacks()
        return PrintResult(success=True, message="Stopped")

    def _stop_print_simulation(self):
        """Stop the simulation thread."""
        self._printing = False
        if self._print_thread and self._print_thread.is_alive():
            self._print_thread.join(timeout=2)

    def set_bed_temp(self, temp: int) -> PrintResult:
        """Set bed temperature."""
        self._status.bed_temp_target = temp
        # Simulate heating/cooling in background
        return PrintResult(success=True, message=f"Bed target: {temp}°C")

    def set_nozzle_temp(self, temp: int) -> PrintResult:
        """Set nozzle temperature."""
        self._status.nozzle_temp_target = temp
        return PrintResult(success=True, message=f"Nozzle target: {temp}°C")

    def list_files(self) -> List[FileInfo]:
        """List uploaded files."""
        return self._files

    def delete_file(self, filename: str) -> TransferResult:
        """Delete a file."""
        self._files = [f for f in self._files if f.name != filename]
        return TransferResult(
            success=True,
            message=f"Deleted: {filename}",
            remote_path=f"/cache/{filename}"
        )


def create_mock_printer() -> MockPrinter:
    """Factory function to create a mock printer."""
    return MockPrinter()


# Convenience class that wraps MockPrinter with the standard interface
class MockBambooConnection(BambooConnection):
    """Mock connection that uses MockPrinter internally."""

    def __init__(self):
        # Don't call super().__init__ as it would try to set up real connection
        self.ip = "mock"
        self.access_code = "mock"
        self.serial = "MOCK000000000"
        self.use_mock = True
        self._mock = MockPrinter()
        self._connected = False
        self._callbacks = []

    def connect(self, timeout: float = 10.0) -> bool:
        result = self._mock.connect()
        self._connected = result
        return result

    def disconnect(self):
        self._mock.disconnect()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def status(self) -> PrinterStatus:
        return self._mock.status

    def add_status_callback(self, callback):
        self._mock.add_status_callback(callback)

    def refresh_status(self) -> PrinterStatus:
        return self._mock.status
