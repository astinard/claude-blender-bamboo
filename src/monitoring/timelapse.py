"""Time-lapse generator for print monitoring.

Captures frames during prints and generates time-lapse videos.
Features:
- Auto-capture during prints
- Configurable intervals
- MP4/GIF export
- Integration with camera stream
"""

import asyncio
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional
from uuid import uuid4

from src.utils import get_logger
from src.config import get_settings
from src.monitoring.camera_stream import CameraStream, CameraConfig, CameraType, Frame

logger = get_logger("monitoring.timelapse")


class OutputFormat(str, Enum):
    """Supported output formats."""
    MP4 = "mp4"
    GIF = "gif"
    FRAMES = "frames"  # Keep frames only


class CaptureMode(str, Enum):
    """Capture modes."""
    INTERVAL = "interval"  # Capture at fixed intervals
    LAYER = "layer"  # Capture at each layer change
    MANUAL = "manual"  # Manual capture only


@dataclass
class TimelapseConfig:
    """Time-lapse configuration."""
    capture_mode: CaptureMode = CaptureMode.INTERVAL
    capture_interval_seconds: float = 10.0  # For interval mode
    output_format: OutputFormat = OutputFormat.MP4
    output_fps: int = 30
    max_frames: int = 10000
    resolution: str = "720p"  # 480p, 720p, 1080p
    quality: int = 85
    auto_start: bool = True
    auto_export: bool = True
    keep_frames: bool = False  # Keep individual frames after export

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
class TimelapseSession:
    """A time-lapse recording session."""
    session_id: str
    started_at: str
    print_id: Optional[str] = None
    print_name: Optional[str] = None
    frames_captured: int = 0
    frames_dir: Optional[str] = None
    output_path: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "print_id": self.print_id,
            "print_name": self.print_name,
            "frames_captured": self.frames_captured,
            "frames_dir": self.frames_dir,
            "output_path": self.output_path,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
        }


class TimelapseGenerator:
    """
    Generates time-lapse videos from print captures.

    Captures frames at configurable intervals during prints
    and exports them as MP4 or GIF videos.
    """

    def __init__(
        self,
        camera: Optional[CameraStream] = None,
        config: Optional[TimelapseConfig] = None,
    ):
        """
        Initialize time-lapse generator.

        Args:
            camera: Camera stream for capturing frames
            config: Time-lapse configuration
        """
        self.camera = camera
        self.config = config or TimelapseConfig()
        self._session: Optional[TimelapseSession] = None
        self._frames: List[Frame] = []
        self._running = False
        self._capture_task: Optional[asyncio.Task] = None
        self._start_time: Optional[float] = None
        self._completion_callbacks: List[Callable[[TimelapseSession], None]] = []

        # Output directory
        settings = get_settings()
        self._output_dir = Path(settings.output_dir) / "timelapses"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._running

    @property
    def session(self) -> Optional[TimelapseSession]:
        """Get current session."""
        return self._session

    @property
    def frame_count(self) -> int:
        """Get number of captured frames."""
        return len(self._frames)

    def set_camera(self, camera: CameraStream) -> None:
        """Set or change the camera stream."""
        self.camera = camera

    async def start_recording(
        self,
        print_id: Optional[str] = None,
        print_name: Optional[str] = None,
    ) -> str:
        """
        Start recording a time-lapse.

        Args:
            print_id: ID of the print job
            print_name: Name of the print file

        Returns:
            Session ID
        """
        if self._running:
            logger.warning("Already recording, stopping current session")
            await self.stop_recording()

        # Ensure camera is available
        if not self.camera:
            logger.warning("No camera configured, creating mock camera")
            self.camera = CameraStream(CameraConfig(camera_type=CameraType.MOCK))

        # Connect camera if needed
        if not self.camera.is_connected:
            await self.camera.connect()
        if self.camera.status.value != "streaming":
            await self.camera.start_stream()

        # Create session
        session_id = str(uuid4())[:8]
        frames_dir = self._output_dir / f"frames_{session_id}"
        frames_dir.mkdir(parents=True, exist_ok=True)

        self._session = TimelapseSession(
            session_id=session_id,
            started_at=datetime.now().isoformat(),
            print_id=print_id,
            print_name=print_name,
            frames_dir=str(frames_dir),
        )

        self._frames = []
        self._running = True
        self._start_time = time.time()

        # Start capture task
        self._capture_task = asyncio.create_task(self._capture_loop())

        logger.info(f"Time-lapse recording started: {session_id}")
        return session_id

    async def stop_recording(self, export: bool = True) -> Optional[TimelapseSession]:
        """
        Stop recording and optionally export.

        Args:
            export: Whether to export the time-lapse

        Returns:
            Completed session
        """
        if not self._running:
            return None

        self._running = False

        # Cancel capture task
        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
            self._capture_task = None

        # Update session
        if self._session:
            self._session.completed_at = datetime.now().isoformat()
            self._session.frames_captured = len(self._frames)
            if self._start_time:
                self._session.duration_seconds = time.time() - self._start_time

            # Export if requested
            if export and self.config.auto_export and len(self._frames) > 0:
                output_path = await self._export_timelapse()
                self._session.output_path = output_path

            # Notify callbacks
            for callback in self._completion_callbacks:
                try:
                    callback(self._session)
                except Exception as e:
                    logger.error(f"Completion callback error: {e}")

        logger.info(f"Time-lapse recording stopped: {self._session.session_id if self._session else 'unknown'}")

        session = self._session
        self._session = None
        return session

    def capture_frame(self) -> bool:
        """
        Manually capture a single frame.

        Returns:
            True if frame captured successfully
        """
        if not self.camera or not self._running:
            return False

        frame = self.camera.get_latest_frame()
        if frame:
            self._frames.append(frame)
            self._save_frame(frame, len(self._frames))
            return True
        return False

    async def _capture_loop(self) -> None:
        """Main capture loop."""
        while self._running:
            try:
                if self.config.capture_mode == CaptureMode.INTERVAL:
                    # Capture at fixed interval
                    frame = self.camera.get_latest_frame()
                    if frame:
                        self._frames.append(frame)
                        self._save_frame(frame, len(self._frames))

                        if len(self._frames) >= self.config.max_frames:
                            logger.warning("Max frames reached, stopping")
                            self._running = False
                            break

                    await asyncio.sleep(self.config.capture_interval_seconds)

                elif self.config.capture_mode == CaptureMode.MANUAL:
                    # Wait for manual captures
                    await asyncio.sleep(0.5)

                else:
                    # Layer mode - wait for layer change events
                    await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Capture error: {e}")
                await asyncio.sleep(1)

    def _save_frame(self, frame: Frame, index: int) -> None:
        """Save a frame to disk."""
        if not self._session or not self._session.frames_dir:
            return

        frame_path = Path(self._session.frames_dir) / f"frame_{index:06d}.jpg"
        frame_path.write_bytes(frame.data)

    async def _export_timelapse(self) -> Optional[str]:
        """Export frames to video/gif."""
        if not self._session or not self._session.frames_dir:
            return None

        frames_dir = Path(self._session.frames_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.config.output_format == OutputFormat.MP4:
            output_path = self._output_dir / f"timelapse_{timestamp}.mp4"
            success = await self._export_mp4(frames_dir, output_path)
        elif self.config.output_format == OutputFormat.GIF:
            output_path = self._output_dir / f"timelapse_{timestamp}.gif"
            success = await self._export_gif(frames_dir, output_path)
        else:
            # Keep frames only
            output_path = frames_dir
            success = True

        if success:
            # Clean up frames if not keeping
            if not self.config.keep_frames and self.config.output_format != OutputFormat.FRAMES:
                shutil.rmtree(frames_dir, ignore_errors=True)

            return str(output_path)

        return None

    async def _export_mp4(self, frames_dir: Path, output_path: Path) -> bool:
        """Export frames to MP4 using ffmpeg.

        Note: Uses subprocess_exec which does NOT use a shell,
        preventing command injection vulnerabilities.
        """
        try:
            # Check if ffmpeg is available
            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                logger.warning("ffmpeg not found, falling back to frames output")
                return False

            # Build ffmpeg command - using list of args, not shell string
            # This is safe from injection as args are passed directly
            args = [
                "-y",  # Overwrite output
                "-framerate", str(self.config.output_fps),
                "-i", str(frames_dir / "frame_%06d.jpg"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "23",
                str(output_path),
            ]

            # Run ffmpeg using subprocess_exec (no shell)
            process = await asyncio.create_subprocess_exec(
                ffmpeg_path,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"MP4 exported: {output_path}")
                return True
            else:
                logger.error(f"ffmpeg error: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"MP4 export failed: {e}")
            return False

    async def _export_gif(self, frames_dir: Path, output_path: Path) -> bool:
        """Export frames to GIF using ffmpeg or pillow.

        Note: Uses subprocess_exec which does NOT use a shell,
        preventing command injection vulnerabilities.
        """
        try:
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                # Use ffmpeg for GIF - args as list, no shell
                args = [
                    "-y",
                    "-framerate", str(min(self.config.output_fps, 15)),  # Limit GIF fps
                    "-i", str(frames_dir / "frame_%06d.jpg"),
                    "-vf", "scale=480:-1",  # Scale down for GIF
                    str(output_path),
                ]

                process = await asyncio.create_subprocess_exec(
                    ffmpeg_path,
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await process.communicate()

                if process.returncode == 0:
                    logger.info(f"GIF exported: {output_path}")
                    return True
                else:
                    logger.error(f"ffmpeg GIF error: {stderr.decode()}")
                    return False
            else:
                # Fallback: try pillow
                try:
                    from PIL import Image

                    frames = []
                    for frame_file in sorted(frames_dir.glob("frame_*.jpg")):
                        img = Image.open(frame_file)
                        img = img.resize((480, 360))  # Scale down
                        frames.append(img)

                    if frames:
                        frames[0].save(
                            output_path,
                            save_all=True,
                            append_images=frames[1:],
                            duration=int(1000 / min(self.config.output_fps, 15)),
                            loop=0,
                        )
                        logger.info(f"GIF exported with Pillow: {output_path}")
                        return True
                except ImportError:
                    logger.warning("Neither ffmpeg nor Pillow available for GIF export")
                    return False

        except Exception as e:
            logger.error(f"GIF export failed: {e}")
            return False

    def register_completion_callback(
        self,
        callback: Callable[[TimelapseSession], None],
    ) -> None:
        """Register callback for session completion."""
        self._completion_callbacks.append(callback)

    def get_session_info(self) -> Optional[dict]:
        """Get current session info."""
        if not self._session:
            return None

        info = self._session.to_dict()
        info["is_recording"] = self._running
        info["current_frames"] = len(self._frames)
        if self._start_time:
            info["current_duration"] = time.time() - self._start_time
        return info


async def create_timelapse(
    print_id: Optional[str] = None,
    print_name: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    interval_seconds: float = 10.0,
    output_format: OutputFormat = OutputFormat.MP4,
) -> Optional[str]:
    """
    Convenience function to create a time-lapse.

    Args:
        print_id: ID of the print job
        print_name: Name of the print file
        duration_seconds: Duration to record
        interval_seconds: Capture interval
        output_format: Output format

    Returns:
        Path to output file
    """
    config = TimelapseConfig(
        capture_interval_seconds=interval_seconds,
        output_format=output_format,
    )

    camera = CameraStream(CameraConfig(camera_type=CameraType.MOCK))
    generator = TimelapseGenerator(camera, config)

    await generator.start_recording(print_id, print_name)

    if duration_seconds:
        await asyncio.sleep(duration_seconds)

    session = await generator.stop_recording()
    await camera.disconnect()

    return session.output_path if session else None
