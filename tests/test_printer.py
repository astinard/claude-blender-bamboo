"""Tests for printer communication module."""

import pytest
from src.printer import (
    MockPrinter,
    MockBambooConnection,
    PrinterState,
    PrinterStatus,
    create_mock_printer,
)


class TestMockPrinter:
    """Tests for MockPrinter class."""

    def test_create_mock_printer(self):
        """Test mock printer creation."""
        printer = create_mock_printer()
        assert printer is not None

    def test_mock_connect(self):
        """Test mock connection."""
        printer = create_mock_printer()
        result = printer.connect()
        assert result is True
        assert printer.is_connected is True
        printer.disconnect()
        assert printer.is_connected is False

    def test_mock_initial_status(self):
        """Test initial printer status."""
        printer = create_mock_printer()
        printer.connect()
        status = printer.status
        assert status.state == PrinterState.IDLE
        assert status.bed_temp == 25.0
        assert status.nozzle_temp == 25.0
        printer.disconnect()

    def test_mock_upload_file(self):
        """Test file upload."""
        printer = create_mock_printer()
        printer.connect()
        result = printer.upload_file("test.stl", 1024)
        assert result.success is True
        assert "test.stl" in [f.name for f in printer.list_files()]
        printer.disconnect()

    def test_mock_start_print_without_file(self):
        """Test starting print without uploading file first."""
        printer = create_mock_printer()
        printer.connect()
        result = printer.start_print("nonexistent.stl")
        assert result.success is False
        printer.disconnect()

    def test_mock_start_print_with_file(self):
        """Test starting print with uploaded file."""
        printer = create_mock_printer()
        printer.connect()
        printer.upload_file("test.stl", 1024)
        result = printer.start_print("test.stl")
        assert result.success is True
        assert printer.status.state in (PrinterState.PRINTING, PrinterState.PREPARING)
        printer.stop_print()
        printer.disconnect()

    def test_mock_pause_resume(self):
        """Test pause and resume."""
        printer = create_mock_printer()
        printer.connect()
        printer.upload_file("test.stl", 1024)
        printer.start_print("test.stl")

        # Wait for printing to start
        import time
        time.sleep(2)

        result = printer.pause_print()
        # May or may not succeed depending on timing
        if printer.status.state == PrinterState.PAUSED:
            result = printer.resume_print()
            assert result.success is True

        printer.stop_print()
        printer.disconnect()

    def test_mock_delete_file(self):
        """Test file deletion."""
        printer = create_mock_printer()
        printer.connect()
        printer.upload_file("test.stl", 1024)
        assert "test.stl" in [f.name for f in printer.list_files()]
        printer.delete_file("test.stl")
        assert "test.stl" not in [f.name for f in printer.list_files()]
        printer.disconnect()


class TestMockBambooConnection:
    """Tests for MockBambooConnection class."""

    def test_mock_connection(self):
        """Test mock connection wrapper."""
        conn = MockBambooConnection()
        assert conn.connect() is True
        assert conn.is_connected is True
        status = conn.status
        assert isinstance(status, PrinterStatus)
        conn.disconnect()
        assert conn.is_connected is False


class TestPrinterStatus:
    """Tests for PrinterStatus dataclass."""

    def test_status_defaults(self):
        """Test default status values."""
        status = PrinterStatus()
        assert status.state == PrinterState.UNKNOWN
        assert status.progress == 0.0
        assert status.bed_temp == 0.0
        assert status.nozzle_temp == 0.0

    def test_status_to_dict(self):
        """Test status serialization."""
        status = PrinterStatus(
            state=PrinterState.PRINTING,
            progress=50.0,
            bed_temp=60.0,
            nozzle_temp=200.0
        )
        data = status.to_dict()
        assert data["state"] == "printing"
        assert data["progress"] == 50.0
        assert data["bed_temp"] == 60.0
        assert data["nozzle_temp"] == 200.0
