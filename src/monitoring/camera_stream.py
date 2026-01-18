"""Camera streaming for print monitoring.

Handles video streaming from Bambu Lab printers for failure detection.
Supports both the built-in H2D camera and external USB cameras.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("monitoring.camera")


class CameraType(str, Enum):
    """Types of camera sources."""
    H2D = "h2d"          # Bambu Lab H2D built-in camera
    USB = "usb"          # USB camera
    IP = "ip"            # IP camera (RTSP)
    MOCK = "mock"        # Mock camera for testing


class StreamStatus(str, Enum):
    """Status of camera stream."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    ERROR = "error"


@dataclass
class Frame:
    """A single video frame."""

    frame_id: str
    timestamp: str
    width: int
    height: int
    data: bytes  # Raw frame data (JPEG)
    camera_type: CameraType

    @property
    def size_kb(self) -> float:
        """Frame size in KB."""
        return len(self.data) / 1024


@dataclass
class CameraConfig:
    """Camera configuration."""

    camera_type: CameraType = CameraType.H2D
    resolution: str = "720p"  # 480p, 720p, 1080p
    fps: int = 15
    quality: int = 85  # JPEG quality

    # H2D/Bambu specific
    printer_ip: Optional[str] = None
    access_code: Optional[str] = None

    # USB specific
    device_id: int = 0

    # IP camera specific
    rtsp_url: Optional[str] = None

    # Frame buffer
    buffer_size: int = 30  # frames

    @property
    def resolution_tuple(self) -> tuple:
        """Get resolution as (width, height)."""
        resolutions = {
            "480p": (640, 480),
            "720p": (1280, 720),
            "1080p": (1920, 1080),
        }
        return resolutions.get(self.resolution, (1280, 720))


@dataclass
class StreamStats:
    """Statistics for camera stream."""

    frames_received: int = 0
    frames_dropped: int = 0
    bytes_received: int = 0
    average_fps: float = 0.0
    average_latency_ms: float = 0.0
    uptime_seconds: float = 0.0
    errors: int = 0


class CameraStream:
    """
    Manages camera streaming for print monitoring.

    Supports Bambu Lab H2D camera, USB cameras, and IP cameras.
    Provides frame access for failure detection algorithms.
    """

    def __init__(self, config: Optional[CameraConfig] = None):
        """
        Initialize camera stream.

        Args:
            config: Camera configuration
        """
        self.config = config or CameraConfig()
        self._status = StreamStatus.DISCONNECTED
        self._frame_buffer: List[Frame] = []
        self._stats = StreamStats()
        self._start_time: Optional[float] = None
        self._callbacks: List[Callable[[Frame], None]] = []
        self._running = False
        self._stream_task: Optional[asyncio.Task] = None

        settings = get_settings()
        if not self.config.printer_ip:
            self.config.printer_ip = settings.printer_ip

    @property
    def status(self) -> StreamStatus:
        """Get current stream status."""
        return self._status

    @property
    def is_connected(self) -> bool:
        """Check if camera is connected."""
        return self._status in [StreamStatus.CONNECTED, StreamStatus.STREAMING]

    @property
    def stats(self) -> StreamStats:
        """Get stream statistics."""
        if self._start_time:
            self._stats.uptime_seconds = time.time() - self._start_time
        return self._stats

    async def connect(self) -> bool:
        """
        Connect to the camera.

        Returns:
            True if connection successful
        """
        self._status = StreamStatus.CONNECTING
        logger.info(f"Connecting to {self.config.camera_type.value} camera...")

        try:
            if self.config.camera_type == CameraType.H2D:
                success = await self._connect_h2d()
            elif self.config.camera_type == CameraType.USB:
                success = await self._connect_usb()
            elif self.config.camera_type == CameraType.IP:
                success = await self._connect_ip()
            elif self.config.camera_type == CameraType.MOCK:
                success = True  # Mock always succeeds
            else:
                logger.error(f"Unknown camera type: {self.config.camera_type}")
                success = False

            if success:
                self._status = StreamStatus.CONNECTED
                logger.info("Camera connected successfully")
            else:
                self._status = StreamStatus.ERROR
                logger.error("Failed to connect to camera")

            return success

        except Exception as e:
            self._status = StreamStatus.ERROR
            logger.error(f"Camera connection error: {e}")
            return False

    async def _connect_h2d(self) -> bool:
        """Connect to Bambu Lab H2D camera."""
        if not self.config.printer_ip:
            logger.error("Printer IP not configured")
            return False

        # In real implementation, would use bambu-connect library
        # For now, simulate successful connection
        logger.info(f"Connecting to H2D camera at {self.config.printer_ip}")
        await asyncio.sleep(0.1)  # Simulate connection time
        return True

    async def _connect_usb(self) -> bool:
        """Connect to USB camera."""
        # Would use OpenCV VideoCapture
        logger.info(f"Connecting to USB camera device {self.config.device_id}")
        await asyncio.sleep(0.1)
        return True

    async def _connect_ip(self) -> bool:
        """Connect to IP camera."""
        if not self.config.rtsp_url:
            logger.error("RTSP URL not configured")
            return False

        logger.info(f"Connecting to IP camera at {self.config.rtsp_url}")
        await asyncio.sleep(0.1)
        return True

    async def start_stream(self) -> bool:
        """
        Start streaming frames.

        Returns:
            True if stream started successfully
        """
        if not self.is_connected:
            if not await self.connect():
                return False

        self._running = True
        self._start_time = time.time()
        self._status = StreamStatus.STREAMING

        # Start frame capture task
        self._stream_task = asyncio.create_task(self._capture_loop())

        logger.info("Camera stream started")
        return True

    async def stop_stream(self) -> None:
        """Stop streaming frames."""
        self._running = False

        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
            self._stream_task = None

        self._status = StreamStatus.CONNECTED
        logger.info("Camera stream stopped")

    async def disconnect(self) -> None:
        """Disconnect from camera."""
        await self.stop_stream()
        self._status = StreamStatus.DISCONNECTED
        self._frame_buffer.clear()
        logger.info("Camera disconnected")

    async def _capture_loop(self) -> None:
        """Main frame capture loop."""
        frame_interval = 1.0 / self.config.fps
        last_frame_time = 0.0

        while self._running:
            try:
                current_time = time.time()

                # Rate limiting
                elapsed = current_time - last_frame_time
                if elapsed < frame_interval:
                    await asyncio.sleep(frame_interval - elapsed)
                    continue

                # Capture frame
                frame = await self._capture_frame()
                if frame:
                    self._process_frame(frame)
                    last_frame_time = time.time()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Frame capture error: {e}")
                self._stats.errors += 1
                await asyncio.sleep(0.1)

    async def _capture_frame(self) -> Optional[Frame]:
        """Capture a single frame."""
        if self.config.camera_type == CameraType.MOCK:
            return self._generate_mock_frame()

        # In real implementation, would capture from actual camera
        # For now, return mock frame
        return self._generate_mock_frame()

    def _generate_mock_frame(self) -> Frame:
        """Generate a mock frame for testing."""
        width, height = self.config.resolution_tuple

        # Create minimal JPEG-like data (not a real JPEG)
        mock_data = b"\xff\xd8\xff" + bytes(1000)  # JPEG header + data

        return Frame(
            frame_id=str(uuid4())[:8],
            timestamp=datetime.now().isoformat(),
            width=width,
            height=height,
            data=mock_data,
            camera_type=self.config.camera_type,
        )

    def _process_frame(self, frame: Frame) -> None:
        """Process a captured frame."""
        # Update stats
        self._stats.frames_received += 1
        self._stats.bytes_received += len(frame.data)

        if self._start_time:
            elapsed = time.time() - self._start_time
            if elapsed > 0:
                self._stats.average_fps = self._stats.frames_received / elapsed

        # Add to buffer (circular)
        self._frame_buffer.append(frame)
        if len(self._frame_buffer) > self.config.buffer_size:
            self._frame_buffer.pop(0)
            self._stats.frames_dropped += 1

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(frame)
            except Exception as e:
                logger.error(f"Frame callback error: {e}")

    def register_callback(self, callback: Callable[[Frame], None]) -> None:
        """
        Register a callback for new frames.

        Args:
            callback: Function to call with each new frame
        """
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[Frame], None]) -> None:
        """Remove a frame callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def get_latest_frame(self) -> Optional[Frame]:
        """Get the most recent frame."""
        if self._frame_buffer:
            return self._frame_buffer[-1]
        return None

    def get_frames(self, count: int = 10) -> List[Frame]:
        """Get recent frames from buffer."""
        return self._frame_buffer[-count:] if self._frame_buffer else []

    async def capture_snapshot(self, output_path: Optional[str] = None) -> Optional[str]:
        """
        Capture a single snapshot.

        Args:
            output_path: Path to save snapshot (auto-generated if not provided)

        Returns:
            Path to saved snapshot
        """
        frame = self.get_latest_frame()
        if not frame:
            frame = await self._capture_frame()

        if not frame:
            return None

        if not output_path:
            settings = get_settings()
            output_dir = Path(settings.output_dir) / "snapshots"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / f"snapshot_{frame.frame_id}.jpg")

        # Write frame data
        Path(output_path).write_bytes(frame.data)
        logger.info(f"Snapshot saved: {output_path}")

        return output_path
