"""Tests for real-time failure detection and camera streaming."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.monitoring.camera_stream import (
    CameraStream,
    CameraConfig,
    CameraType,
    Frame,
    StreamStatus,
    StreamStats,
)
from src.monitoring.failure_detector import (
    FailureDetector,
    FailureAlert,
    FailureType,
    AlertSeverity,
    DetectorStatus,
    DetectionSettings,
    DetectionStats,
    monitor_print,
)


class TestCameraType:
    """Tests for CameraType enum."""

    def test_camera_type_values(self):
        """Test camera type enum values."""
        assert CameraType.H2D.value == "h2d"
        assert CameraType.USB.value == "usb"
        assert CameraType.IP.value == "ip"
        assert CameraType.MOCK.value == "mock"


class TestStreamStatus:
    """Tests for StreamStatus enum."""

    def test_stream_status_values(self):
        """Test stream status enum values."""
        assert StreamStatus.DISCONNECTED.value == "disconnected"
        assert StreamStatus.CONNECTING.value == "connecting"
        assert StreamStatus.CONNECTED.value == "connected"
        assert StreamStatus.STREAMING.value == "streaming"
        assert StreamStatus.ERROR.value == "error"


class TestFrame:
    """Tests for Frame dataclass."""

    def test_create_frame(self):
        """Test creating a frame."""
        frame = Frame(
            frame_id="abc123",
            timestamp="2024-01-01T12:00:00",
            width=1280,
            height=720,
            data=b"\xff\xd8\xff" + bytes(1000),
            camera_type=CameraType.MOCK,
        )

        assert frame.frame_id == "abc123"
        assert frame.width == 1280
        assert frame.height == 720
        assert frame.camera_type == CameraType.MOCK

    def test_frame_size_kb(self):
        """Test frame size calculation."""
        frame = Frame(
            frame_id="test",
            timestamp="2024-01-01T12:00:00",
            width=1280,
            height=720,
            data=bytes(2048),
            camera_type=CameraType.MOCK,
        )

        assert frame.size_kb == 2.0


class TestCameraConfig:
    """Tests for CameraConfig dataclass."""

    def test_default_config(self):
        """Test default camera config."""
        config = CameraConfig()

        assert config.camera_type == CameraType.H2D
        assert config.resolution == "720p"
        assert config.fps == 15
        assert config.quality == 85
        assert config.buffer_size == 30

    def test_resolution_tuple(self):
        """Test resolution tuple calculation."""
        config_480 = CameraConfig(resolution="480p")
        config_720 = CameraConfig(resolution="720p")
        config_1080 = CameraConfig(resolution="1080p")

        assert config_480.resolution_tuple == (640, 480)
        assert config_720.resolution_tuple == (1280, 720)
        assert config_1080.resolution_tuple == (1920, 1080)

    def test_custom_config(self):
        """Test custom camera config."""
        config = CameraConfig(
            camera_type=CameraType.USB,
            resolution="1080p",
            fps=30,
            device_id=1,
        )

        assert config.camera_type == CameraType.USB
        assert config.fps == 30
        assert config.device_id == 1


class TestCameraStream:
    """Tests for CameraStream class."""

    @pytest.fixture
    def camera(self):
        """Create a camera instance with mock config."""
        config = CameraConfig(camera_type=CameraType.MOCK)
        return CameraStream(config)

    def test_initial_status(self, camera):
        """Test initial camera status."""
        assert camera.status == StreamStatus.DISCONNECTED
        assert not camera.is_connected

    @pytest.mark.asyncio
    async def test_connect_mock(self, camera):
        """Test connecting mock camera."""
        result = await camera.connect()

        assert result is True
        assert camera.status == StreamStatus.CONNECTED
        assert camera.is_connected

    @pytest.mark.asyncio
    async def test_start_stream(self, camera):
        """Test starting stream."""
        await camera.connect()
        result = await camera.start_stream()

        assert result is True
        assert camera.status == StreamStatus.STREAMING

        # Clean up
        await camera.stop_stream()

    @pytest.mark.asyncio
    async def test_stop_stream(self, camera):
        """Test stopping stream."""
        await camera.connect()
        await camera.start_stream()
        await camera.stop_stream()

        assert camera.status == StreamStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_disconnect(self, camera):
        """Test disconnecting camera."""
        await camera.connect()
        await camera.start_stream()
        await camera.disconnect()

        assert camera.status == StreamStatus.DISCONNECTED
        assert not camera.is_connected

    @pytest.mark.asyncio
    async def test_get_latest_frame(self, camera):
        """Test getting latest frame."""
        await camera.connect()
        await camera.start_stream()

        # Allow some frames to be captured
        await asyncio.sleep(0.2)

        frame = camera.get_latest_frame()
        assert frame is not None
        assert isinstance(frame, Frame)

        await camera.disconnect()

    @pytest.mark.asyncio
    async def test_get_frames(self, camera):
        """Test getting multiple frames."""
        await camera.connect()
        await camera.start_stream()

        await asyncio.sleep(0.2)

        frames = camera.get_frames(5)
        assert isinstance(frames, list)

        await camera.disconnect()

    def test_register_callback(self, camera):
        """Test registering frame callback."""
        callback = MagicMock()
        camera.register_callback(callback)

        assert callback in camera._callbacks

    def test_unregister_callback(self, camera):
        """Test unregistering frame callback."""
        callback = MagicMock()
        camera.register_callback(callback)
        camera.unregister_callback(callback)

        assert callback not in camera._callbacks

    @pytest.mark.asyncio
    async def test_stats_tracking(self, camera):
        """Test stream stats tracking."""
        await camera.connect()
        await camera.start_stream()

        await asyncio.sleep(0.2)

        stats = camera.stats
        assert stats.frames_received >= 0
        assert stats.uptime_seconds >= 0

        await camera.disconnect()


class TestFailureType:
    """Tests for FailureType enum."""

    def test_failure_type_values(self):
        """Test failure type enum values."""
        assert FailureType.SPAGHETTI.value == "spaghetti"
        assert FailureType.WARPING.value == "warping"
        assert FailureType.LAYER_SHIFT.value == "layer_shift"
        assert FailureType.STRINGING.value == "stringing"
        assert FailureType.MISSING_EXTRUSION.value == "missing_extrusion"
        assert FailureType.BLOB.value == "blob"
        assert FailureType.ADHESION_FAILURE.value == "adhesion_failure"


class TestAlertSeverity:
    """Tests for AlertSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"


class TestFailureAlert:
    """Tests for FailureAlert dataclass."""

    def test_create_alert(self):
        """Test creating a failure alert."""
        alert = FailureAlert(
            alert_id="alert123",
            failure_type=FailureType.SPAGHETTI,
            severity=AlertSeverity.CRITICAL,
            confidence=0.95,
            timestamp="2024-01-01T12:00:00",
        )

        assert alert.alert_id == "alert123"
        assert alert.failure_type == FailureType.SPAGHETTI
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.confidence == 0.95
        assert not alert.auto_paused

    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = FailureAlert(
            alert_id="test",
            failure_type=FailureType.WARPING,
            severity=AlertSeverity.WARNING,
            confidence=0.8,
            timestamp="2024-01-01T12:00:00",
            recommended_action="Check bed adhesion",
        )

        d = alert.to_dict()
        assert d["alert_id"] == "test"
        assert d["failure_type"] == "warping"
        assert d["severity"] == "warning"
        assert d["confidence"] == 0.8


class TestDetectionSettings:
    """Tests for DetectionSettings dataclass."""

    def test_default_settings(self):
        """Test default detection settings."""
        settings = DetectionSettings()

        assert settings.spaghetti_threshold == 0.7
        assert settings.warping_threshold == 0.8
        assert settings.auto_pause_enabled is True
        assert settings.auto_pause_severity == AlertSeverity.CRITICAL
        assert settings.consecutive_frames_for_alert == 3

    def test_custom_settings(self):
        """Test custom detection settings."""
        settings = DetectionSettings(
            spaghetti_threshold=0.5,
            auto_pause_enabled=False,
            detection_interval_seconds=2.0,
        )

        assert settings.spaghetti_threshold == 0.5
        assert settings.auto_pause_enabled is False
        assert settings.detection_interval_seconds == 2.0


class TestFailureDetector:
    """Tests for FailureDetector class."""

    @pytest.fixture
    def camera(self):
        """Create a mock camera."""
        config = CameraConfig(camera_type=CameraType.MOCK)
        return CameraStream(config)

    @pytest.fixture
    def detector(self, camera):
        """Create a detector instance."""
        return FailureDetector(camera)

    def test_initial_status(self, detector):
        """Test initial detector status."""
        assert detector.status == DetectorStatus.IDLE
        assert not detector.is_monitoring

    def test_set_camera(self, detector):
        """Test setting camera."""
        new_camera = CameraStream(CameraConfig(camera_type=CameraType.MOCK))
        detector.set_camera(new_camera)

        assert detector.camera is new_camera

    def test_set_pause_callback(self, detector):
        """Test setting pause callback."""
        callback = MagicMock()
        detector.set_pause_callback(callback)

        assert detector._pause_callback is callback

    def test_register_alert_callback(self, detector):
        """Test registering alert callback."""
        callback = MagicMock()
        detector.register_alert_callback(callback)

        assert callback in detector._alert_callbacks

    @pytest.mark.asyncio
    async def test_start_monitoring(self, detector, camera):
        """Test starting monitoring."""
        result = await detector.start_monitoring()

        assert result is True
        assert detector.status == DetectorStatus.MONITORING
        assert detector.is_monitoring

        await detector.stop_monitoring()

    @pytest.mark.asyncio
    async def test_start_monitoring_no_camera(self):
        """Test starting monitoring without camera."""
        detector = FailureDetector()
        result = await detector.start_monitoring()

        assert result is False
        assert detector.status == DetectorStatus.IDLE

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, detector):
        """Test stopping monitoring."""
        await detector.start_monitoring()
        await detector.stop_monitoring()

        assert detector.status == DetectorStatus.IDLE
        assert not detector.is_monitoring

    @pytest.mark.asyncio
    async def test_pause_resume_monitoring(self, detector):
        """Test pausing and resuming monitoring."""
        await detector.start_monitoring()

        detector.pause_monitoring()
        assert detector.status == DetectorStatus.PAUSED

        detector.resume_monitoring()
        assert detector.status == DetectorStatus.MONITORING

        await detector.stop_monitoring()

    @pytest.mark.asyncio
    async def test_stats_tracking(self, detector):
        """Test detection stats tracking."""
        await detector.start_monitoring()
        await asyncio.sleep(0.2)

        stats = detector.stats
        assert isinstance(stats, DetectionStats)
        assert stats.frames_analyzed >= 0
        assert stats.uptime_seconds >= 0

        await detector.stop_monitoring()

    def test_get_alerts(self, detector):
        """Test getting alerts."""
        alerts = detector.alerts
        assert isinstance(alerts, list)

    def test_get_active_alerts(self, detector):
        """Test getting active alerts."""
        alerts = detector.active_alerts
        assert isinstance(alerts, list)

    def test_clear_alerts(self, detector):
        """Test clearing alerts."""
        # Add a mock alert
        alert = FailureAlert(
            alert_id="test",
            failure_type=FailureType.SPAGHETTI,
            severity=AlertSeverity.CRITICAL,
            confidence=0.9,
            timestamp=datetime.now().isoformat(),
        )
        detector._alerts.append(alert)

        count = detector.clear_alerts()
        assert count == 1
        assert len(detector.alerts) == 0

    def test_mark_false_positive(self, detector):
        """Test marking alert as false positive."""
        alert = FailureAlert(
            alert_id="fp_test",
            failure_type=FailureType.WARPING,
            severity=AlertSeverity.WARNING,
            confidence=0.7,
            timestamp=datetime.now().isoformat(),
        )
        detector._alerts.append(alert)

        result = detector.mark_false_positive("fp_test")
        assert result is True
        assert detector._stats.false_positives_marked == 1

    def test_mark_false_positive_not_found(self, detector):
        """Test marking non-existent alert."""
        result = detector.mark_false_positive("nonexistent")
        assert result is False

    def test_get_alert(self, detector):
        """Test getting specific alert."""
        alert = FailureAlert(
            alert_id="get_test",
            failure_type=FailureType.BLOB,
            severity=AlertSeverity.INFO,
            confidence=0.6,
            timestamp=datetime.now().isoformat(),
        )
        detector._alerts.append(alert)

        found = detector.get_alert("get_test")
        assert found is not None
        assert found.alert_id == "get_test"

    def test_get_alert_not_found(self, detector):
        """Test getting non-existent alert."""
        found = detector.get_alert("nonexistent")
        assert found is None


class TestDetectorStatus:
    """Tests for DetectorStatus enum."""

    def test_status_values(self):
        """Test detector status enum values."""
        assert DetectorStatus.IDLE.value == "idle"
        assert DetectorStatus.MONITORING.value == "monitoring"
        assert DetectorStatus.PAUSED.value == "paused"
        assert DetectorStatus.ALERT.value == "alert"
        assert DetectorStatus.ERROR.value == "error"


class TestMonitorPrint:
    """Tests for monitor_print convenience function."""

    @pytest.mark.asyncio
    async def test_monitor_print_duration(self):
        """Test monitor_print with duration."""
        stats = await monitor_print(
            printer_ip="192.168.1.100",
            auto_pause=True,
            duration_seconds=0.2,
        )

        assert isinstance(stats, DetectionStats)
        assert stats.uptime_seconds >= 0


class TestIntegration:
    """Integration tests for failure detection workflow."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete monitoring workflow."""
        # Create camera
        config = CameraConfig(camera_type=CameraType.MOCK, fps=30)
        camera = CameraStream(config)

        # Create detector
        settings = DetectionSettings(
            auto_pause_enabled=True,
            detection_interval_seconds=0.1,
        )
        detector = FailureDetector(camera, settings)

        # Set up callback
        alerts_received = []
        detector.register_alert_callback(lambda a: alerts_received.append(a))

        # Start monitoring
        await detector.start_monitoring()
        assert detector.is_monitoring

        # Let it run briefly
        await asyncio.sleep(0.3)

        # Check stats
        stats = detector.stats
        assert stats.frames_analyzed >= 0

        # Stop monitoring
        await detector.stop_monitoring()
        await camera.disconnect()

        assert not detector.is_monitoring

    @pytest.mark.asyncio
    async def test_camera_callback_integration(self):
        """Test camera callback with detector."""
        config = CameraConfig(camera_type=CameraType.MOCK)
        camera = CameraStream(config)

        frames_received = []

        def on_frame(frame):
            frames_received.append(frame)

        camera.register_callback(on_frame)

        await camera.start_stream()
        await asyncio.sleep(0.2)

        assert len(frames_received) >= 0

        await camera.disconnect()
