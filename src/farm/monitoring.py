"""Fleet monitoring for print farms.

Provides real-time monitoring across all printers including:
- Status tracking
- Performance metrics
- Alert management
- Historical data
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Awaitable

from src.utils import get_logger

logger = get_logger("farm.monitoring")


class PrinterStatus(str, Enum):
    """Printer operational status."""
    OFFLINE = "offline"
    IDLE = "idle"
    PREPARING = "preparing"
    PRINTING = "printing"
    PAUSED = "paused"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class PrinterState:
    """Current state of a printer."""

    printer_id: str
    status: PrinterStatus = PrinterStatus.OFFLINE
    last_seen: datetime = field(default_factory=datetime.utcnow)

    # Current job
    current_job_id: Optional[str] = None
    job_progress: float = 0.0
    job_started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None

    # Temperatures
    nozzle_temp: float = 0.0
    nozzle_target: float = 0.0
    bed_temp: float = 0.0
    bed_target: float = 0.0
    chamber_temp: Optional[float] = None

    # Consumables
    filament_remaining_percent: float = 100.0
    current_material: Optional[str] = None
    ams_status: Optional[Dict[int, str]] = None  # Slot -> material

    # Performance
    print_speed_percent: int = 100
    fan_speed_percent: int = 0

    # Error info
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "printer_id": self.printer_id,
            "status": self.status.value,
            "last_seen": self.last_seen.isoformat(),
            "current_job_id": self.current_job_id,
            "job_progress": self.job_progress,
            "nozzle_temp": self.nozzle_temp,
            "nozzle_target": self.nozzle_target,
            "bed_temp": self.bed_temp,
            "bed_target": self.bed_target,
            "chamber_temp": self.chamber_temp,
            "filament_remaining_percent": self.filament_remaining_percent,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass
class Alert:
    """A monitoring alert."""

    alert_id: str
    printer_id: str
    severity: AlertSeverity
    category: str
    message: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "printer_id": self.printer_id,
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
        }


@dataclass
class FarmMetrics:
    """Aggregated farm metrics."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_printers: int = 0
    online_printers: int = 0
    printing_printers: int = 0
    idle_printers: int = 0
    error_printers: int = 0
    maintenance_printers: int = 0

    # Utilization
    utilization_percent: float = 0.0
    avg_job_progress: float = 0.0

    # Performance
    jobs_completed_24h: int = 0
    jobs_failed_24h: int = 0
    success_rate_24h: float = 100.0

    # Alerts
    active_alerts: int = 0
    critical_alerts: int = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_printers": self.total_printers,
            "online_printers": self.online_printers,
            "printing_printers": self.printing_printers,
            "idle_printers": self.idle_printers,
            "error_printers": self.error_printers,
            "utilization_percent": round(self.utilization_percent, 2),
            "jobs_completed_24h": self.jobs_completed_24h,
            "jobs_failed_24h": self.jobs_failed_24h,
            "success_rate_24h": round(self.success_rate_24h, 2),
            "active_alerts": self.active_alerts,
            "critical_alerts": self.critical_alerts,
        }


class FarmMonitor:
    """
    Real-time monitoring for print farms.

    Features:
    - Status tracking for all printers
    - Performance metrics aggregation
    - Alert generation and management
    - Historical data collection
    """

    OFFLINE_THRESHOLD_SECONDS = 120  # Consider offline after 2 minutes

    def __init__(self, poll_interval_seconds: float = 10.0):
        self.poll_interval = poll_interval_seconds

        self._states: Dict[str, PrinterState] = {}
        self._alerts: Dict[str, Alert] = {}
        self._metrics_history: List[FarmMetrics] = []

        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Alert thresholds
        self._temp_variance_threshold = 10.0  # Degrees from target
        self._filament_low_threshold = 20.0  # Percent

        # Callbacks
        self._on_status_change: List[Callable[[str, PrinterStatus, PrinterStatus], Awaitable[None]]] = []
        self._on_alert: List[Callable[[Alert], Awaitable[None]]] = []

        self._alert_counter = 0

    def on_status_change(
        self,
        callback: Callable[[str, PrinterStatus, PrinterStatus], Awaitable[None]],
    ) -> None:
        """Register callback for status changes."""
        self._on_status_change.append(callback)

    def on_alert(self, callback: Callable[[Alert], Awaitable[None]]) -> None:
        """Register callback for new alerts."""
        self._on_alert.append(callback)

    async def start(self) -> None:
        """Start monitoring."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Farm monitor started")

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Farm monitor stopped")

    def register_printer(self, printer_id: str) -> None:
        """Register a printer for monitoring."""
        if printer_id not in self._states:
            self._states[printer_id] = PrinterState(printer_id=printer_id)
            logger.info(f"Registered printer for monitoring: {printer_id}")

    def unregister_printer(self, printer_id: str) -> None:
        """Unregister a printer from monitoring."""
        if printer_id in self._states:
            del self._states[printer_id]

    async def update_state(self, printer_id: str, **updates) -> None:
        """Update printer state."""
        if printer_id not in self._states:
            self.register_printer(printer_id)

        state = self._states[printer_id]
        old_status = state.status

        # Update fields
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)

        state.last_seen = datetime.utcnow()

        # Check for status change
        new_status = state.status
        if old_status != new_status:
            await self._handle_status_change(printer_id, old_status, new_status)

        # Check for alert conditions
        await self._check_alerts(state)

    def get_state(self, printer_id: str) -> Optional[PrinterState]:
        """Get current printer state."""
        return self._states.get(printer_id)

    def get_all_states(self) -> Dict[str, PrinterState]:
        """Get all printer states."""
        return dict(self._states)

    def get_metrics(self) -> FarmMetrics:
        """Get current farm metrics."""
        now = datetime.utcnow()
        offline_cutoff = now - timedelta(seconds=self.OFFLINE_THRESHOLD_SECONDS)

        states = list(self._states.values())

        online = [s for s in states if s.last_seen > offline_cutoff]
        printing = [s for s in online if s.status == PrinterStatus.PRINTING]
        idle = [s for s in online if s.status == PrinterStatus.IDLE]
        error = [s for s in online if s.status == PrinterStatus.ERROR]
        maintenance = [s for s in online if s.status == PrinterStatus.MAINTENANCE]

        active_alerts = [a for a in self._alerts.values() if not a.resolved]
        critical_alerts = [a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]

        utilization = (len(printing) / len(online) * 100) if online else 0
        avg_progress = (
            sum(s.job_progress for s in printing) / len(printing)
            if printing else 0
        )

        return FarmMetrics(
            total_printers=len(states),
            online_printers=len(online),
            printing_printers=len(printing),
            idle_printers=len(idle),
            error_printers=len(error),
            maintenance_printers=len(maintenance),
            utilization_percent=utilization,
            avg_job_progress=avg_progress,
            active_alerts=len(active_alerts),
            critical_alerts=len(critical_alerts),
        )

    def get_alerts(
        self,
        printer_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        active_only: bool = True,
    ) -> List[Alert]:
        """Get alerts with optional filters."""
        alerts = list(self._alerts.values())

        if printer_id:
            alerts = [a for a in alerts if a.printer_id == printer_id]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if active_only:
            alerts = [a for a in alerts if not a.resolved]

        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    async def create_alert(
        self,
        printer_id: str,
        severity: AlertSeverity,
        category: str,
        message: str,
    ) -> Alert:
        """Create a new alert."""
        self._alert_counter += 1
        alert = Alert(
            alert_id=f"ALT-{self._alert_counter:06d}",
            printer_id=printer_id,
            severity=severity,
            category=category,
            message=message,
        )
        self._alerts[alert.alert_id] = alert

        logger.warning(f"Alert created: {alert.alert_id} - {message}")

        # Notify callbacks
        for callback in self._on_alert:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

        return alert

    def acknowledge_alert(self, alert_id: str, user_id: str) -> bool:
        """Acknowledge an alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False

        alert.acknowledged = True
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.utcnow()
        return True

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False

        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        return True

    async def _handle_status_change(
        self,
        printer_id: str,
        old_status: PrinterStatus,
        new_status: PrinterStatus,
    ) -> None:
        """Handle printer status change."""
        logger.info(f"Printer {printer_id} status: {old_status.value} -> {new_status.value}")

        # Create alerts for concerning transitions
        if new_status == PrinterStatus.ERROR:
            state = self._states.get(printer_id)
            message = state.error_message if state else "Unknown error"
            await self.create_alert(
                printer_id=printer_id,
                severity=AlertSeverity.ERROR,
                category="status",
                message=f"Printer entered error state: {message}",
            )
        elif new_status == PrinterStatus.OFFLINE:
            await self.create_alert(
                printer_id=printer_id,
                severity=AlertSeverity.WARNING,
                category="connectivity",
                message="Printer went offline",
            )

        # Notify callbacks
        for callback in self._on_status_change:
            try:
                await callback(printer_id, old_status, new_status)
            except Exception as e:
                logger.error(f"Status change callback error: {e}")

    async def _check_alerts(self, state: PrinterState) -> None:
        """Check for alert conditions."""
        # Temperature variance
        if state.nozzle_target > 0:
            variance = abs(state.nozzle_temp - state.nozzle_target)
            if variance > self._temp_variance_threshold:
                await self.create_alert(
                    printer_id=state.printer_id,
                    severity=AlertSeverity.WARNING,
                    category="temperature",
                    message=f"Nozzle temperature variance: {variance:.1f}°C from target",
                )

        # Low filament
        if state.filament_remaining_percent < self._filament_low_threshold:
            await self.create_alert(
                printer_id=state.printer_id,
                severity=AlertSeverity.WARNING,
                category="consumables",
                message=f"Low filament: {state.filament_remaining_percent:.1f}% remaining",
            )

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Update offline status for stale printers
                now = datetime.utcnow()
                cutoff = now - timedelta(seconds=self.OFFLINE_THRESHOLD_SECONDS)

                for state in self._states.values():
                    if (
                        state.last_seen < cutoff and
                        state.status != PrinterStatus.OFFLINE
                    ):
                        await self.update_state(
                            state.printer_id,
                            status=PrinterStatus.OFFLINE,
                        )

                # Record metrics
                metrics = self.get_metrics()
                self._metrics_history.append(metrics)

                # Keep only last 24 hours of metrics
                day_ago = now - timedelta(hours=24)
                self._metrics_history = [
                    m for m in self._metrics_history
                    if m.timestamp > day_ago
                ]

                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(10)


# Global monitor instance
_monitor: Optional[FarmMonitor] = None


def get_farm_monitor() -> FarmMonitor:
    """Get the global farm monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = FarmMonitor()
    return _monitor


async def init_farm_monitor(**kwargs) -> FarmMonitor:
    """Initialize and start the farm monitor."""
    global _monitor
    _monitor = FarmMonitor(**kwargs)
    await _monitor.start()
    return _monitor
