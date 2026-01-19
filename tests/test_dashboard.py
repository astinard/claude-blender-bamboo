"""Tests for remote monitoring dashboard."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from src.jarvis.dashboard import (
    Dashboard,
    DashboardConfig,
    PrintStatus,
    TemperatureData,
    PrintProgress,
    PrinterState,
    create_dashboard,
)


class TestPrintStatus:
    """Tests for PrintStatus enum."""

    def test_status_values(self):
        """Test print status enum values."""
        assert PrintStatus.IDLE.value == "idle"
        assert PrintStatus.PREPARING.value == "preparing"
        assert PrintStatus.PRINTING.value == "printing"
        assert PrintStatus.PAUSED.value == "paused"
        assert PrintStatus.COMPLETE.value == "complete"
        assert PrintStatus.FAILED.value == "failed"
        assert PrintStatus.CANCELLED.value == "cancelled"


class TestTemperatureData:
    """Tests for TemperatureData dataclass."""

    def test_create_temperature(self):
        """Test creating temperature data."""
        temp = TemperatureData(
            timestamp="2024-01-01T12:00:00",
            nozzle_current=200.5,
            nozzle_target=200.0,
            bed_current=60.2,
            bed_target=60.0,
        )

        assert temp.nozzle_current == 200.5
        assert temp.nozzle_target == 200.0
        assert temp.bed_current == 60.2
        assert temp.bed_target == 60.0
        assert temp.chamber_current is None

    def test_temperature_with_chamber(self):
        """Test temperature data with chamber."""
        temp = TemperatureData(
            timestamp="2024-01-01T12:00:00",
            nozzle_current=200.0,
            nozzle_target=200.0,
            bed_current=60.0,
            bed_target=60.0,
            chamber_current=35.0,
            chamber_target=35.0,
        )

        assert temp.chamber_current == 35.0
        assert temp.chamber_target == 35.0

    def test_temperature_to_dict(self):
        """Test temperature serialization."""
        temp = TemperatureData(
            timestamp="2024-01-01T12:00:00",
            nozzle_current=200.0,
            nozzle_target=200.0,
            bed_current=60.0,
            bed_target=60.0,
        )

        d = temp.to_dict()
        assert d["timestamp"] == "2024-01-01T12:00:00"
        assert d["nozzle"]["current"] == 200.0
        assert d["nozzle"]["target"] == 200.0
        assert d["bed"]["current"] == 60.0


class TestPrintProgress:
    """Tests for PrintProgress dataclass."""

    def test_create_progress(self):
        """Test creating print progress."""
        progress = PrintProgress(
            print_id="abc123",
            file_name="benchy.3mf",
            status=PrintStatus.PRINTING,
            progress_percent=45.5,
            layer_current=120,
            layer_total=450,
            time_elapsed_seconds=5000,
            time_remaining_seconds=6000,
            filament_used_mm=1500.0,
        )

        assert progress.print_id == "abc123"
        assert progress.file_name == "benchy.3mf"
        assert progress.status == PrintStatus.PRINTING
        assert progress.progress_percent == 45.5
        assert progress.layer_current == 120
        assert progress.layer_total == 450

    def test_progress_to_dict(self):
        """Test progress serialization."""
        progress = PrintProgress(
            print_id="test",
            file_name="test.3mf",
            status=PrintStatus.PRINTING,
            progress_percent=50.0,
            layer_current=100,
            layer_total=200,
            time_elapsed_seconds=3600,
            time_remaining_seconds=3600,
            filament_used_mm=1000.0,
        )

        d = progress.to_dict()
        assert d["print_id"] == "test"
        assert d["file_name"] == "test.3mf"
        assert d["status"] == "printing"
        assert d["progress_percent"] == 50.0


class TestDashboardConfig:
    """Tests for DashboardConfig dataclass."""

    def test_default_config(self):
        """Test default dashboard config."""
        config = DashboardConfig()

        assert config.host == "0.0.0.0"
        assert config.port == 9880
        assert config.enable_notifications is True
        assert config.enable_camera is True
        assert config.camera_fps == 10
        assert config.history_length == 100
        assert config.update_interval_seconds == 1.0

    def test_custom_config(self):
        """Test custom dashboard config."""
        config = DashboardConfig(
            host="127.0.0.1",
            port=9000,
            enable_notifications=False,
            camera_fps=30,
        )

        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.enable_notifications is False
        assert config.camera_fps == 30


class TestPrinterState:
    """Tests for PrinterState dataclass."""

    def test_default_state(self):
        """Test default printer state."""
        state = PrinterState()

        assert state.connected is False
        assert state.status == PrintStatus.IDLE
        assert state.progress is None
        assert len(state.temperatures) == 0
        assert len(state.alerts) == 0

    def test_state_to_dict(self):
        """Test state serialization."""
        state = PrinterState()
        state.connected = True
        state.status = PrintStatus.PRINTING
        state.last_update = "2024-01-01T12:00:00"

        d = state.to_dict()
        assert d["connected"] is True
        assert d["status"] == "printing"
        assert d["last_update"] == "2024-01-01T12:00:00"


class TestDashboard:
    """Tests for Dashboard class."""

    @pytest.fixture
    def dashboard(self):
        """Create a dashboard instance."""
        return Dashboard()

    def test_initial_state(self, dashboard):
        """Test initial dashboard state."""
        assert not dashboard.is_running
        assert dashboard.state.connected is False
        assert dashboard.state.status == PrintStatus.IDLE

    def test_url_property(self, dashboard):
        """Test dashboard URL property."""
        assert dashboard.url == "http://localhost:9880"

    def test_custom_url(self):
        """Test dashboard with custom config."""
        config = DashboardConfig(host="192.168.1.100", port=9000)
        dash = Dashboard(config)

        assert dash.url == "http://192.168.1.100:9000"

    def test_update_status(self, dashboard):
        """Test updating print status."""
        dashboard.update_status(PrintStatus.PRINTING)

        assert dashboard.state.status == PrintStatus.PRINTING
        assert dashboard.state.last_update is not None

    def test_update_progress(self, dashboard):
        """Test updating print progress."""
        progress = PrintProgress(
            print_id="test",
            file_name="test.3mf",
            status=PrintStatus.PRINTING,
            progress_percent=50.0,
            layer_current=100,
            layer_total=200,
            time_elapsed_seconds=3600,
            time_remaining_seconds=3600,
            filament_used_mm=1000.0,
        )

        dashboard.update_progress(progress)

        assert dashboard.state.progress is progress
        assert dashboard.state.status == PrintStatus.PRINTING

    def test_add_temperature(self, dashboard):
        """Test adding temperature reading."""
        temp = TemperatureData(
            timestamp="2024-01-01T12:00:00",
            nozzle_current=200.0,
            nozzle_target=200.0,
            bed_current=60.0,
            bed_target=60.0,
        )

        dashboard.add_temperature(temp)

        assert len(dashboard.state.temperatures) == 1
        assert dashboard.state.temperatures[0] is temp

    def test_temperature_history_limit(self, dashboard):
        """Test temperature history is limited."""
        dashboard.config.history_length = 5

        for i in range(10):
            temp = TemperatureData(
                timestamp=f"2024-01-01T12:{i:02d}:00",
                nozzle_current=200.0 + i,
                nozzle_target=200.0,
                bed_current=60.0,
                bed_target=60.0,
            )
            dashboard.add_temperature(temp)

        assert len(dashboard.state.temperatures) == 5

    def test_add_alert(self, dashboard):
        """Test adding an alert."""
        dashboard.add_alert("spaghetti", "Spaghetti detected!", "critical")

        assert len(dashboard.state.alerts) == 1
        alert = dashboard.state.alerts[0]
        assert alert["type"] == "spaghetti"
        assert alert["message"] == "Spaghetti detected!"
        assert alert["severity"] == "critical"

    def test_clear_alerts(self, dashboard):
        """Test clearing alerts."""
        dashboard.add_alert("test1", "Alert 1")
        dashboard.add_alert("test2", "Alert 2")

        count = dashboard.clear_alerts()

        assert count == 2
        assert len(dashboard.state.alerts) == 0

    def test_register_notification_callback(self, dashboard):
        """Test registering notification callback."""
        callback = MagicMock()
        dashboard.register_notification_callback(callback)

        dashboard.add_alert("test", "Test alert")

        callback.assert_called_once_with("test", "Test alert")


class TestCreateDashboard:
    """Tests for create_dashboard factory function."""

    def test_create_default(self):
        """Test creating dashboard with defaults."""
        dash = create_dashboard()

        assert dash.config.host == "0.0.0.0"
        assert dash.config.port == 9880

    def test_create_custom(self):
        """Test creating dashboard with custom settings."""
        dash = create_dashboard(
            host="127.0.0.1",
            port=9000,
            enable_notifications=False,
        )

        assert dash.config.host == "127.0.0.1"
        assert dash.config.port == 9000
        assert dash.config.enable_notifications is False


class TestDashboardServerMock:
    """Tests for dashboard server functionality using mocks."""

    @pytest.fixture
    def dashboard(self):
        """Create a dashboard instance."""
        return Dashboard()

    @pytest.mark.asyncio
    async def test_start_without_aiohttp(self, dashboard, monkeypatch):
        """Test starting without aiohttp installed."""
        # Mock HAS_AIOHTTP to False
        import src.jarvis.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, "HAS_AIOHTTP", False)

        result = await dashboard.start()
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_without_starting(self, dashboard):
        """Test stopping without starting."""
        await dashboard.stop()
        assert not dashboard.is_running

    def test_state_serialization_complete(self, dashboard):
        """Test complete state serialization."""
        # Add some data
        dashboard.update_status(PrintStatus.PRINTING)

        progress = PrintProgress(
            print_id="test",
            file_name="model.3mf",
            status=PrintStatus.PRINTING,
            progress_percent=75.5,
            layer_current=300,
            layer_total=400,
            time_elapsed_seconds=7200,
            time_remaining_seconds=2400,
            filament_used_mm=2000.0,
        )
        dashboard.update_progress(progress)

        for i in range(5):
            temp = TemperatureData(
                timestamp=f"2024-01-01T12:{i:02d}:00",
                nozzle_current=200.0,
                nozzle_target=200.0,
                bed_current=60.0,
                bed_target=60.0,
            )
            dashboard.add_temperature(temp)

        dashboard.add_alert("warning", "Nozzle temp fluctuation", "warning")

        # Serialize
        state_dict = dashboard.state.to_dict()

        assert state_dict["connected"] is False  # Not started
        assert state_dict["status"] == "printing"
        assert state_dict["progress"]["progress_percent"] == 75.5
        assert len(state_dict["temperatures"]) == 5
        assert len(state_dict["alerts"]) == 1


class TestDashboardIntegration:
    """Integration tests for dashboard functionality."""

    def test_full_workflow(self):
        """Test complete dashboard workflow without server."""
        # Create dashboard
        dashboard = create_dashboard(port=8888)

        # Simulate print starting
        dashboard.update_status(PrintStatus.PREPARING)

        # Add initial temperature
        temp = TemperatureData(
            timestamp=datetime.now().isoformat(),
            nozzle_current=25.0,
            nozzle_target=200.0,
            bed_current=25.0,
            bed_target=60.0,
        )
        dashboard.add_temperature(temp)

        # Start printing
        progress = PrintProgress(
            print_id="job001",
            file_name="test_model.3mf",
            status=PrintStatus.PRINTING,
            progress_percent=0.0,
            layer_current=0,
            layer_total=500,
            time_elapsed_seconds=0,
            time_remaining_seconds=7200,
            filament_used_mm=0.0,
        )
        dashboard.update_progress(progress)

        # Verify state
        assert dashboard.state.status == PrintStatus.PRINTING
        assert dashboard.state.progress.layer_total == 500

        # Simulate progress
        progress.progress_percent = 50.0
        progress.layer_current = 250
        progress.time_elapsed_seconds = 3600
        progress.time_remaining_seconds = 3600
        dashboard.update_progress(progress)

        assert dashboard.state.progress.progress_percent == 50.0

        # Add an alert
        dashboard.add_alert("stringing", "Minor stringing detected", "warning")

        assert len(dashboard.state.alerts) == 1

        # Complete print
        progress.status = PrintStatus.COMPLETE
        progress.progress_percent = 100.0
        progress.layer_current = 500
        dashboard.update_progress(progress)

        assert dashboard.state.status == PrintStatus.COMPLETE
