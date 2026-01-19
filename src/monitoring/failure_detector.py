"""Real-time print failure detection.

Uses camera frames to detect print failures like:
- Spaghetti/stringing (detached filament)
- Layer adhesion failures
- Warping/lifting
- Missing extrusion
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from src.utils import get_logger
from src.monitoring.camera_stream import CameraStream, Frame, CameraConfig

logger = get_logger("monitoring.failure_detector")


class FailureType(str, Enum):
    """Types of detected print failures."""
    SPAGHETTI = "spaghetti"          # Detached/loose filament
    WARPING = "warping"              # Warping/lifting from bed
    LAYER_SHIFT = "layer_shift"      # Layer misalignment
    STRINGING = "stringing"          # Excessive stringing
    MISSING_EXTRUSION = "missing_extrusion"  # No filament coming out
    BLOB = "blob"                    # Filament blob/jam
    ADHESION_FAILURE = "adhesion_failure"  # Part detached from bed
    UNKNOWN = "unknown"


class AlertSeverity(str, Enum):
    """Severity levels for alerts."""
    INFO = "info"           # Informational, may not be a problem
    WARNING = "warning"     # Potential issue, monitor closely
    CRITICAL = "critical"   # Definite failure, action required


class DetectorStatus(str, Enum):
    """Status of the detector."""
    IDLE = "idle"
    MONITORING = "monitoring"
    PAUSED = "paused"
    ALERT = "alert"
    ERROR = "error"


@dataclass
class FailureAlert:
    """A detected failure alert."""

    alert_id: str
    failure_type: FailureType
    severity: AlertSeverity
    confidence: float  # 0.0-1.0
    timestamp: str
    frame_id: Optional[str] = None

    # Location info
    region: Optional[Tuple[int, int, int, int]] = None  # x, y, width, height

    # Recommendations
    recommended_action: str = ""
    auto_paused: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "failure_type": self.failure_type.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "recommended_action": self.recommended_action,
            "auto_paused": self.auto_paused,
        }


@dataclass
class DetectionSettings:
    """Settings for failure detection."""

    # Detection thresholds
    spaghetti_threshold: float = 0.7
    warping_threshold: float = 0.8
    layer_shift_threshold: float = 0.85
    stringing_threshold: float = 0.6

    # Auto-pause settings
    auto_pause_enabled: bool = True
    auto_pause_severity: AlertSeverity = AlertSeverity.CRITICAL
    pause_delay_seconds: float = 2.0  # Delay before pausing

    # Notification settings
    notification_enabled: bool = True
    notification_severity: AlertSeverity = AlertSeverity.WARNING

    # Detection intervals
    detection_interval_seconds: float = 1.0
    consecutive_frames_for_alert: int = 3  # Require multiple frames


@dataclass
class DetectionStats:
    """Statistics for detection session."""

    frames_analyzed: int = 0
    alerts_generated: int = 0
    false_positives_marked: int = 0
    auto_pauses: int = 0
    detection_time_avg_ms: float = 0.0
    uptime_seconds: float = 0.0
    alerts_by_type: Dict[FailureType, int] = field(default_factory=dict)


class FailureDetector:
    """
    Real-time print failure detection using camera feed.

    Analyzes video frames to detect:
    - Spaghetti/stringing
    - Warping/lifting
    - Layer shifts
    - Missing extrusion

    Can automatically pause printer on detection.
    """

    def __init__(
        self,
        camera: Optional[CameraStream] = None,
        settings: Optional[DetectionSettings] = None,
    ):
        """
        Initialize failure detector.

        Args:
            camera: Camera stream to analyze
            settings: Detection settings
        """
        self.camera = camera
        self.settings = settings or DetectionSettings()
        self._status = DetectorStatus.IDLE
        self._alerts: List[FailureAlert] = []
        self._stats = DetectionStats()
        self._start_time: Optional[float] = None
        self._running = False
        self._detection_task: Optional[asyncio.Task] = None
        self._alert_callbacks: List[Callable[[FailureAlert], None]] = []
        self._pause_callback: Optional[Callable[[], None]] = None

        # Detection state
        self._consecutive_detections: Dict[FailureType, int] = {}
        self._last_detection_time: Dict[FailureType, float] = {}

    @property
    def status(self) -> DetectorStatus:
        """Get detector status."""
        return self._status

    @property
    def is_monitoring(self) -> bool:
        """Check if actively monitoring."""
        return self._status == DetectorStatus.MONITORING

    @property
    def stats(self) -> DetectionStats:
        """Get detection statistics."""
        if self._start_time:
            self._stats.uptime_seconds = time.time() - self._start_time
        return self._stats

    @property
    def alerts(self) -> List[FailureAlert]:
        """Get all alerts."""
        return self._alerts.copy()

    @property
    def active_alerts(self) -> List[FailureAlert]:
        """Get recent unresolved alerts."""
        # Consider alerts in last 5 minutes as active
        cutoff = time.time() - 300
        return [
            a for a in self._alerts
            if datetime.fromisoformat(a.timestamp).timestamp() > cutoff
        ]

    def set_camera(self, camera: CameraStream) -> None:
        """Set or change the camera stream."""
        self.camera = camera

    def set_pause_callback(self, callback: Callable[[], None]) -> None:
        """
        Set callback for auto-pause action.

        Args:
            callback: Function to call to pause printer
        """
        self._pause_callback = callback

    def register_alert_callback(self, callback: Callable[[FailureAlert], None]) -> None:
        """Register callback for alerts."""
        self._alert_callbacks.append(callback)

    async def start_monitoring(self) -> bool:
        """
        Start monitoring for failures.

        Returns:
            True if monitoring started successfully
        """
        if not self.camera:
            logger.error("No camera configured")
            return False

        if not self.camera.is_connected:
            if not await self.camera.connect():
                logger.error("Failed to connect to camera")
                return False

        if self.camera.status.value != "streaming":
            if not await self.camera.start_stream():
                logger.error("Failed to start camera stream")
                return False

        self._running = True
        self._start_time = time.time()
        self._status = DetectorStatus.MONITORING
        self._stats = DetectionStats()

        # Register frame callback
        self.camera.register_callback(self._on_frame)

        # Start detection task
        self._detection_task = asyncio.create_task(self._detection_loop())

        logger.info("Failure detection started")
        return True

    async def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self._running = False

        if self._detection_task:
            self._detection_task.cancel()
            try:
                await self._detection_task
            except asyncio.CancelledError:
                pass
            self._detection_task = None

        if self.camera:
            self.camera.unregister_callback(self._on_frame)

        self._status = DetectorStatus.IDLE
        logger.info("Failure detection stopped")

    def pause_monitoring(self) -> None:
        """Temporarily pause monitoring."""
        self._status = DetectorStatus.PAUSED
        logger.info("Failure detection paused")

    def resume_monitoring(self) -> None:
        """Resume paused monitoring."""
        if self._running:
            self._status = DetectorStatus.MONITORING
            logger.info("Failure detection resumed")

    def _on_frame(self, frame: Frame) -> None:
        """Callback for new camera frames."""
        # Frames are processed in detection loop
        pass

    async def _detection_loop(self) -> None:
        """Main detection loop."""
        while self._running:
            try:
                if self._status != DetectorStatus.MONITORING:
                    await asyncio.sleep(0.1)
                    continue

                # Get latest frame
                frame = self.camera.get_latest_frame()
                if not frame:
                    await asyncio.sleep(0.1)
                    continue

                # Analyze frame
                start_time = time.time()
                detections = await self._analyze_frame(frame)
                detection_time = (time.time() - start_time) * 1000

                # Update stats
                self._stats.frames_analyzed += 1
                self._stats.detection_time_avg_ms = (
                    (self._stats.detection_time_avg_ms * (self._stats.frames_analyzed - 1) +
                     detection_time) / self._stats.frames_analyzed
                )

                # Process detections
                for failure_type, confidence in detections:
                    await self._process_detection(failure_type, confidence, frame)

                await asyncio.sleep(self.settings.detection_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Detection error: {e}")
                await asyncio.sleep(0.5)

    async def _analyze_frame(self, frame: Frame) -> List[Tuple[FailureType, float]]:
        """
        Analyze a frame for failures.

        Args:
            frame: Frame to analyze

        Returns:
            List of (failure_type, confidence) tuples
        """
        detections = []

        # In real implementation, would use ML model (e.g., Obico's)
        # For now, use simplified mock detection

        # Mock: Random detection for testing
        import random
        random.seed(int(time.time() * 1000) % 10000)

        # Spaghetti detection
        if random.random() < 0.01:  # 1% chance for testing
            confidence = random.uniform(0.6, 0.95)
            if confidence >= self.settings.spaghetti_threshold:
                detections.append((FailureType.SPAGHETTI, confidence))

        # Warping detection
        if random.random() < 0.005:  # 0.5% chance
            confidence = random.uniform(0.7, 0.9)
            if confidence >= self.settings.warping_threshold:
                detections.append((FailureType.WARPING, confidence))

        return detections

    async def _process_detection(
        self,
        failure_type: FailureType,
        confidence: float,
        frame: Frame,
    ) -> None:
        """Process a detection and potentially generate alert."""
        current_time = time.time()

        # Update consecutive detection count
        if failure_type not in self._consecutive_detections:
            self._consecutive_detections[failure_type] = 0
            self._last_detection_time[failure_type] = 0

        # Reset if too much time has passed
        time_since_last = current_time - self._last_detection_time[failure_type]
        if time_since_last > self.settings.detection_interval_seconds * 3:
            self._consecutive_detections[failure_type] = 0

        self._consecutive_detections[failure_type] += 1
        self._last_detection_time[failure_type] = current_time

        # Check if enough consecutive frames
        if self._consecutive_detections[failure_type] < self.settings.consecutive_frames_for_alert:
            return

        # Generate alert
        severity = self._determine_severity(failure_type, confidence)
        alert = self._create_alert(failure_type, severity, confidence, frame)

        self._alerts.append(alert)
        self._stats.alerts_generated += 1

        if failure_type not in self._stats.alerts_by_type:
            self._stats.alerts_by_type[failure_type] = 0
        self._stats.alerts_by_type[failure_type] += 1

        # Reset consecutive count
        self._consecutive_detections[failure_type] = 0

        # Notify callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

        # Auto-pause if enabled
        if (self.settings.auto_pause_enabled and
            severity.value >= self.settings.auto_pause_severity.value):
            await self._auto_pause(alert)

        logger.warning(f"Alert generated: {failure_type.value} ({confidence:.0%})")

    def _determine_severity(self, failure_type: FailureType, confidence: float) -> AlertSeverity:
        """Determine alert severity."""
        if failure_type in [FailureType.SPAGHETTI, FailureType.ADHESION_FAILURE]:
            return AlertSeverity.CRITICAL

        if confidence >= 0.9:
            return AlertSeverity.CRITICAL
        elif confidence >= 0.75:
            return AlertSeverity.WARNING
        else:
            return AlertSeverity.INFO

    def _create_alert(
        self,
        failure_type: FailureType,
        severity: AlertSeverity,
        confidence: float,
        frame: Frame,
    ) -> FailureAlert:
        """Create a failure alert."""
        actions = {
            FailureType.SPAGHETTI: "Pause print immediately and inspect",
            FailureType.WARPING: "Check bed adhesion and temperature",
            FailureType.LAYER_SHIFT: "Stop print, check belts and lubrication",
            FailureType.STRINGING: "Adjust retraction settings",
            FailureType.MISSING_EXTRUSION: "Check for clog or filament runout",
            FailureType.ADHESION_FAILURE: "Stop print, re-level bed",
        }

        return FailureAlert(
            alert_id=str(uuid4())[:8],
            failure_type=failure_type,
            severity=severity,
            confidence=confidence,
            timestamp=datetime.now().isoformat(),
            frame_id=frame.frame_id,
            recommended_action=actions.get(failure_type, "Inspect print"),
        )

    async def _auto_pause(self, alert: FailureAlert) -> None:
        """Execute auto-pause."""
        if not self._pause_callback:
            logger.warning("Auto-pause enabled but no pause callback set")
            return

        # Wait for delay
        await asyncio.sleep(self.settings.pause_delay_seconds)

        # Execute pause
        try:
            self._pause_callback()
            alert.auto_paused = True
            self._stats.auto_pauses += 1
            logger.info("Auto-pause executed")
        except Exception as e:
            logger.error(f"Auto-pause failed: {e}")

    def mark_false_positive(self, alert_id: str) -> bool:
        """Mark an alert as false positive for learning."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                self._stats.false_positives_marked += 1
                logger.info(f"Alert {alert_id} marked as false positive")
                return True
        return False

    def get_alert(self, alert_id: str) -> Optional[FailureAlert]:
        """Get a specific alert."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                return alert
        return None

    def clear_alerts(self) -> int:
        """Clear all alerts."""
        count = len(self._alerts)
        self._alerts.clear()
        return count


async def monitor_print(
    printer_ip: Optional[str] = None,
    auto_pause: bool = True,
    duration_seconds: Optional[float] = None,
) -> DetectionStats:
    """
    Convenience function to monitor a print.

    Args:
        printer_ip: Printer IP address
        auto_pause: Enable auto-pause on critical failure
        duration_seconds: How long to monitor (None = until stopped)

    Returns:
        Detection statistics
    """
    config = CameraConfig(printer_ip=printer_ip)
    camera = CameraStream(config)

    settings = DetectionSettings(auto_pause_enabled=auto_pause)
    detector = FailureDetector(camera, settings)

    await detector.start_monitoring()

    try:
        if duration_seconds:
            await asyncio.sleep(duration_seconds)
        else:
            # Run indefinitely until cancelled
            while detector.is_monitoring:
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await detector.stop_monitoring()
        await camera.disconnect()

    return detector.stats
