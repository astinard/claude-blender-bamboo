"""Tests for time-lapse generator."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.monitoring.timelapse import (
    TimelapseGenerator,
    TimelapseConfig,
    TimelapseSession,
    OutputFormat,
    CaptureMode,
    create_timelapse,
)
from src.monitoring.camera_stream import CameraStream, CameraConfig, CameraType, Frame, StreamStatus


def make_test_frame() -> Frame:
    """Create a test frame with valid structure."""
    return Frame(
        frame_id="frame_001",
        timestamp="2024-01-15T10:30:00",
        width=1280,
        height=720,
        data=b"fake_image_data",
        camera_type=CameraType.MOCK,
    )


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_mp4_format(self):
        """Test MP4 format value."""
        assert OutputFormat.MP4.value == "mp4"

    def test_gif_format(self):
        """Test GIF format value."""
        assert OutputFormat.GIF.value == "gif"

    def test_frames_format(self):
        """Test frames-only format value."""
        assert OutputFormat.FRAMES.value == "frames"


class TestCaptureMode:
    """Tests for CaptureMode enum."""

    def test_interval_mode(self):
        """Test interval capture mode."""
        assert CaptureMode.INTERVAL.value == "interval"

    def test_layer_mode(self):
        """Test layer capture mode."""
        assert CaptureMode.LAYER.value == "layer"

    def test_manual_mode(self):
        """Test manual capture mode."""
        assert CaptureMode.MANUAL.value == "manual"


class TestTimelapseConfig:
    """Tests for TimelapseConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TimelapseConfig()

        assert config.capture_mode == CaptureMode.INTERVAL
        assert config.capture_interval_seconds == 10.0
        assert config.output_format == OutputFormat.MP4
        assert config.output_fps == 30
        assert config.max_frames == 10000
        assert config.resolution == "720p"
        assert config.quality == 85
        assert config.auto_start is True
        assert config.auto_export is True
        assert config.keep_frames is False

    def test_custom_config(self):
        """Test custom configuration."""
        config = TimelapseConfig(
            capture_mode=CaptureMode.LAYER,
            capture_interval_seconds=5.0,
            output_format=OutputFormat.GIF,
            output_fps=15,
            max_frames=500,
            resolution="1080p",
            quality=95,
            auto_start=False,
            auto_export=False,
            keep_frames=True,
        )

        assert config.capture_mode == CaptureMode.LAYER
        assert config.capture_interval_seconds == 5.0
        assert config.output_format == OutputFormat.GIF
        assert config.output_fps == 15
        assert config.max_frames == 500
        assert config.resolution == "1080p"
        assert config.quality == 95
        assert config.auto_start is False
        assert config.auto_export is False
        assert config.keep_frames is True

    def test_resolution_tuple_480p(self):
        """Test 480p resolution tuple."""
        config = TimelapseConfig(resolution="480p")
        assert config.resolution_tuple == (640, 480)

    def test_resolution_tuple_720p(self):
        """Test 720p resolution tuple."""
        config = TimelapseConfig(resolution="720p")
        assert config.resolution_tuple == (1280, 720)

    def test_resolution_tuple_1080p(self):
        """Test 1080p resolution tuple."""
        config = TimelapseConfig(resolution="1080p")
        assert config.resolution_tuple == (1920, 1080)

    def test_resolution_tuple_unknown(self):
        """Test unknown resolution defaults to 720p."""
        config = TimelapseConfig(resolution="4k")
        assert config.resolution_tuple == (1280, 720)


class TestTimelapseSession:
    """Tests for TimelapseSession dataclass."""

    def test_create_session(self):
        """Test creating a session."""
        session = TimelapseSession(
            session_id="abc123",
            started_at="2024-01-15T10:30:00",
            print_id="print_001",
            print_name="test_model.stl",
        )

        assert session.session_id == "abc123"
        assert session.started_at == "2024-01-15T10:30:00"
        assert session.print_id == "print_001"
        assert session.print_name == "test_model.stl"
        assert session.frames_captured == 0
        assert session.frames_dir is None
        assert session.output_path is None
        assert session.completed_at is None
        assert session.duration_seconds == 0

    def test_session_to_dict(self):
        """Test session serialization."""
        session = TimelapseSession(
            session_id="xyz789",
            started_at="2024-01-15T10:30:00",
            print_id="print_002",
            print_name="cube.stl",
            frames_captured=100,
            frames_dir="/tmp/frames",
            output_path="/tmp/timelapse.mp4",
            completed_at="2024-01-15T11:30:00",
            duration_seconds=3600,
        )

        d = session.to_dict()

        assert d["session_id"] == "xyz789"
        assert d["started_at"] == "2024-01-15T10:30:00"
        assert d["print_id"] == "print_002"
        assert d["print_name"] == "cube.stl"
        assert d["frames_captured"] == 100
        assert d["frames_dir"] == "/tmp/frames"
        assert d["output_path"] == "/tmp/timelapse.mp4"
        assert d["completed_at"] == "2024-01-15T11:30:00"
        assert d["duration_seconds"] == 3600


class TestTimelapseGenerator:
    """Tests for TimelapseGenerator class."""

    @pytest.fixture
    def mock_camera(self):
        """Create a mock camera stream."""
        camera = Mock(spec=CameraStream)
        camera.is_connected = True
        camera.status = StreamStatus.STREAMING
        camera.connect = AsyncMock()
        camera.start_stream = AsyncMock()
        camera.get_latest_frame = Mock(return_value=make_test_frame())
        return camera

    @pytest.fixture
    def generator(self, mock_camera, tmp_path):
        """Create a timelapse generator."""
        config = TimelapseConfig(
            capture_interval_seconds=0.1,  # Fast for testing
            auto_export=False,  # Disable auto-export for most tests
        )
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator(mock_camera, config)
            return gen

    def test_init_without_camera(self, tmp_path):
        """Test initialization without camera."""
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator()

        assert gen.camera is None
        assert gen.is_recording is False

    def test_init_with_camera(self, generator, mock_camera):
        """Test initialization with camera."""
        assert generator.camera == mock_camera
        assert generator.is_recording is False
        assert generator.session is None
        assert generator.frame_count == 0

    def test_set_camera(self, generator, tmp_path):
        """Test setting camera after init."""
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator()

        new_camera = Mock(spec=CameraStream)
        gen.set_camera(new_camera)

        assert gen.camera == new_camera

    @pytest.mark.asyncio
    async def test_start_recording(self, generator):
        """Test starting recording."""
        session_id = await generator.start_recording(
            print_id="print_001",
            print_name="test.stl",
        )

        assert session_id is not None
        assert len(session_id) == 8
        assert generator.is_recording is True
        assert generator.session is not None
        assert generator.session.print_id == "print_001"
        assert generator.session.print_name == "test.stl"

        # Clean up
        await generator.stop_recording(export=False)

    @pytest.mark.asyncio
    async def test_start_recording_creates_mock_camera(self, tmp_path):
        """Test starting recording creates mock camera if none provided."""
        config = TimelapseConfig(
            capture_interval_seconds=0.1,
            auto_export=False,
        )
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator(config=config)

        session_id = await gen.start_recording()

        assert session_id is not None
        assert gen.camera is not None
        assert gen.is_recording is True

        # Clean up
        await gen.stop_recording(export=False)
        await gen.camera.disconnect()

    @pytest.mark.asyncio
    async def test_start_recording_stops_existing(self, generator):
        """Test starting recording stops existing session."""
        # Start first session
        session1 = await generator.start_recording()
        assert generator.is_recording is True

        # Start second session (should stop first)
        session2 = await generator.start_recording()
        assert generator.is_recording is True
        assert session1 != session2

        # Clean up
        await generator.stop_recording(export=False)

    @pytest.mark.asyncio
    async def test_stop_recording(self, generator):
        """Test stopping recording."""
        await generator.start_recording()
        assert generator.is_recording is True

        session = await generator.stop_recording(export=False)

        assert generator.is_recording is False
        assert session is not None
        assert session.completed_at is not None

    @pytest.mark.asyncio
    async def test_stop_recording_when_not_recording(self, generator):
        """Test stopping when not recording returns None."""
        result = await generator.stop_recording()
        assert result is None

    @pytest.mark.asyncio
    async def test_capture_frame_manual(self, generator):
        """Test manual frame capture."""
        await generator.start_recording()

        result = generator.capture_frame()

        assert result is True
        assert generator.frame_count == 1

        # Clean up
        await generator.stop_recording(export=False)

    def test_capture_frame_when_not_recording(self, generator):
        """Test capture returns False when not recording."""
        result = generator.capture_frame()
        assert result is False

    @pytest.mark.asyncio
    async def test_capture_frame_no_camera(self, tmp_path):
        """Test capture returns False with no camera."""
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator()
            gen._running = True

        result = gen.capture_frame()
        assert result is False

    @pytest.mark.asyncio
    async def test_capture_loop_interval_mode(self, generator):
        """Test automatic capture in interval mode."""
        await generator.start_recording()

        # Let capture loop run for a short time
        await asyncio.sleep(0.25)

        # Should have captured at least 2 frames (at 0.1s interval)
        assert generator.frame_count >= 2

        # Clean up
        await generator.stop_recording(export=False)

    @pytest.mark.asyncio
    async def test_capture_loop_max_frames(self, generator, mock_camera, tmp_path):
        """Test capture loop stops at max frames."""
        config = TimelapseConfig(
            capture_interval_seconds=0.01,
            max_frames=3,
            auto_export=False,
        )
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator(mock_camera, config)

        await gen.start_recording()

        # Wait for max frames to be reached
        await asyncio.sleep(0.15)

        # Should have stopped at max frames
        assert gen.frame_count == 3
        assert gen.is_recording is False

    @pytest.mark.asyncio
    async def test_get_session_info(self, generator):
        """Test getting session info."""
        await generator.start_recording(
            print_id="print_001",
            print_name="test.stl",
        )

        info = generator.get_session_info()

        assert info is not None
        assert info["print_id"] == "print_001"
        assert info["print_name"] == "test.stl"
        assert info["is_recording"] is True
        assert "current_frames" in info
        assert "current_duration" in info

        # Clean up
        await generator.stop_recording(export=False)

    def test_get_session_info_when_not_recording(self, generator):
        """Test session info returns None when not recording."""
        info = generator.get_session_info()
        assert info is None

    @pytest.mark.asyncio
    async def test_register_completion_callback(self, generator):
        """Test completion callback registration."""
        callback_called = []

        def on_complete(session):
            callback_called.append(session)

        generator.register_completion_callback(on_complete)

        await generator.start_recording()
        await generator.stop_recording(export=False)

        assert len(callback_called) == 1
        assert callback_called[0] is not None

    @pytest.mark.asyncio
    async def test_completion_callback_error_handling(self, generator):
        """Test completion callback error doesn't crash."""
        def bad_callback(session):
            raise ValueError("Test error")

        generator.register_completion_callback(bad_callback)

        await generator.start_recording()
        # Should not raise
        session = await generator.stop_recording(export=False)
        assert session is not None


class TestTimelapseExport:
    """Tests for timelapse export functionality."""

    @pytest.fixture
    def mock_camera(self):
        """Create a mock camera stream."""
        camera = Mock(spec=CameraStream)
        camera.is_connected = True
        camera.status = StreamStatus.STREAMING
        camera.connect = AsyncMock()
        camera.start_stream = AsyncMock()
        camera.get_latest_frame = Mock(return_value=make_test_frame())
        return camera

    @pytest.mark.asyncio
    async def test_export_mp4_no_ffmpeg(self, mock_camera, tmp_path):
        """Test MP4 export fails gracefully without ffmpeg."""
        config = TimelapseConfig(
            capture_interval_seconds=0.1,
            output_format=OutputFormat.MP4,
            auto_export=True,
        )
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator(mock_camera, config)

        with patch("shutil.which", return_value=None):
            await gen.start_recording()
            gen.capture_frame()  # Capture one frame
            session = await gen.stop_recording()

        # Should complete without crash even without ffmpeg
        assert session is not None

    @pytest.mark.asyncio
    async def test_export_gif_no_ffmpeg_no_pillow(self, mock_camera, tmp_path):
        """Test GIF export fails gracefully without dependencies."""
        config = TimelapseConfig(
            capture_interval_seconds=0.1,
            output_format=OutputFormat.GIF,
            auto_export=True,
        )
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator(mock_camera, config)

        with patch("shutil.which", return_value=None):
            await gen.start_recording()
            gen.capture_frame()
            session = await gen.stop_recording()

        # Should complete without crash
        assert session is not None

    @pytest.mark.asyncio
    async def test_export_frames_only(self, mock_camera, tmp_path):
        """Test frames-only export keeps frames directory."""
        config = TimelapseConfig(
            capture_interval_seconds=0.1,
            output_format=OutputFormat.FRAMES,
            auto_export=True,
        )
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator(mock_camera, config)

        await gen.start_recording()
        gen.capture_frame()
        session = await gen.stop_recording()

        assert session is not None
        assert session.frames_dir is not None
        # Frames directory should exist for FRAMES mode
        # (In real implementation, it would contain the frames)


class TestCreateTimelapseFunction:
    """Tests for convenience create_timelapse function."""

    @pytest.mark.asyncio
    async def test_create_timelapse_basic(self, tmp_path):
        """Test basic timelapse creation."""
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)

            # Run for very short duration
            result = await create_timelapse(
                print_id="test_print",
                print_name="test.stl",
                duration_seconds=0.1,
                interval_seconds=0.05,
                output_format=OutputFormat.FRAMES,
            )

        # Should complete (may or may not have output depending on timing)
        # The function returns the output path or None

    @pytest.mark.asyncio
    async def test_create_timelapse_with_duration(self, tmp_path):
        """Test timelapse creation with specific duration."""
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)

            result = await create_timelapse(
                duration_seconds=0.15,
                interval_seconds=0.05,
                output_format=OutputFormat.FRAMES,
            )

        # Function should complete without error


class TestTimelapseManualMode:
    """Tests for manual capture mode."""

    @pytest.fixture
    def mock_camera(self):
        """Create a mock camera stream."""
        camera = Mock(spec=CameraStream)
        camera.is_connected = True
        camera.status = StreamStatus.STREAMING
        camera.connect = AsyncMock()
        camera.start_stream = AsyncMock()
        camera.get_latest_frame = Mock(return_value=make_test_frame())
        return camera

    @pytest.mark.asyncio
    async def test_manual_mode_no_auto_capture(self, mock_camera, tmp_path):
        """Test manual mode doesn't auto-capture."""
        config = TimelapseConfig(
            capture_mode=CaptureMode.MANUAL,
            auto_export=False,
        )
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator(mock_camera, config)

        await gen.start_recording()
        await asyncio.sleep(0.15)

        # No frames should be captured automatically
        assert gen.frame_count == 0

        # Manual capture should work
        gen.capture_frame()
        assert gen.frame_count == 1

        # Clean up
        await gen.stop_recording(export=False)


class TestTimelapseLayerMode:
    """Tests for layer capture mode."""

    @pytest.fixture
    def mock_camera(self):
        """Create a mock camera stream."""
        camera = Mock(spec=CameraStream)
        camera.is_connected = True
        camera.status = StreamStatus.STREAMING
        camera.connect = AsyncMock()
        camera.start_stream = AsyncMock()
        camera.get_latest_frame = Mock(return_value=make_test_frame())
        return camera

    @pytest.mark.asyncio
    async def test_layer_mode_waits_for_events(self, mock_camera, tmp_path):
        """Test layer mode waits for layer change events."""
        config = TimelapseConfig(
            capture_mode=CaptureMode.LAYER,
            auto_export=False,
        )
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator(mock_camera, config)

        await gen.start_recording()
        await asyncio.sleep(0.15)

        # No frames captured in layer mode without events
        assert gen.frame_count == 0

        # Clean up
        await gen.stop_recording(export=False)


class TestTimelapseFrameSaving:
    """Tests for frame saving functionality."""

    @pytest.fixture
    def mock_camera(self):
        """Create a mock camera stream."""
        camera = Mock(spec=CameraStream)
        camera.is_connected = True
        camera.status = StreamStatus.STREAMING
        camera.connect = AsyncMock()
        camera.start_stream = AsyncMock()
        camera.get_latest_frame = Mock(return_value=Frame(
            frame_id="frame_001",
            timestamp="2024-01-15T10:30:00",
            width=1280,
            height=720,
            data=b"fake_image_data_12345",
            camera_type=CameraType.MOCK,
        ))
        return camera

    @pytest.mark.asyncio
    async def test_frames_saved_to_disk(self, mock_camera, tmp_path):
        """Test frames are saved to disk."""
        config = TimelapseConfig(
            capture_mode=CaptureMode.MANUAL,
            auto_export=False,
            keep_frames=True,
        )
        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator(mock_camera, config)

        await gen.start_recording()

        # Capture a few frames
        gen.capture_frame()
        gen.capture_frame()
        gen.capture_frame()

        session = await gen.stop_recording(export=False)

        # Check frames directory exists
        frames_dir = Path(session.frames_dir)
        assert frames_dir.exists()

        # Check frame files exist
        frame_files = list(frames_dir.glob("frame_*.jpg"))
        assert len(frame_files) == 3


class TestTimelapseIntegration:
    """Integration tests for timelapse system."""

    @pytest.mark.asyncio
    async def test_full_recording_workflow(self, tmp_path):
        """Test complete recording workflow."""
        config = TimelapseConfig(
            capture_interval_seconds=0.05,
            output_format=OutputFormat.FRAMES,
            auto_export=True,
            keep_frames=True,
        )

        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator(config=config)

        # Start recording
        session_id = await gen.start_recording(
            print_id="integration_test",
            print_name="test_model.stl",
        )
        assert session_id is not None
        assert gen.is_recording is True

        # Let it capture some frames
        await asyncio.sleep(0.2)

        # Check progress
        info = gen.get_session_info()
        assert info["is_recording"] is True
        assert info["current_frames"] > 0

        # Stop and export
        session = await gen.stop_recording()

        assert session is not None
        assert session.frames_captured > 0
        assert session.completed_at is not None
        assert session.duration_seconds > 0

        # Clean up camera
        await gen.camera.disconnect()

    @pytest.mark.asyncio
    async def test_multiple_sessions(self, tmp_path):
        """Test multiple recording sessions."""
        config = TimelapseConfig(
            capture_interval_seconds=0.05,
            auto_export=False,
        )

        with patch("src.monitoring.timelapse.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            gen = TimelapseGenerator(config=config)

        # First session
        id1 = await gen.start_recording(print_name="first.stl")
        await asyncio.sleep(0.1)
        session1 = await gen.stop_recording(export=False)

        # Second session
        id2 = await gen.start_recording(print_name="second.stl")
        await asyncio.sleep(0.1)
        session2 = await gen.stop_recording(export=False)

        # Sessions should be different
        assert id1 != id2
        assert session1.session_id != session2.session_id
        assert session1.print_name == "first.stl"
        assert session2.print_name == "second.stl"

        # Clean up
        await gen.camera.disconnect()
