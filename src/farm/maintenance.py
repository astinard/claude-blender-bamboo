"""Predictive maintenance for print farms.

Tracks usage metrics and predicts maintenance needs for:
- Nozzle replacement
- Belt tension
- Lubrication
- Calibration
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List

from src.utils import get_logger

logger = get_logger("farm.maintenance")


class MaintenanceType(str, Enum):
    """Types of maintenance tasks."""
    NOZZLE_REPLACE = "nozzle_replace"
    BELT_TENSION = "belt_tension"
    LUBRICATION = "lubrication"
    CALIBRATION = "calibration"
    CLEANING = "cleaning"
    FIRMWARE_UPDATE = "firmware_update"
    FILTER_REPLACE = "filter_replace"
    BED_LEVEL = "bed_level"


class MaintenanceUrgency(str, Enum):
    """Urgency of maintenance."""
    OPTIONAL = "optional"
    RECOMMENDED = "recommended"
    REQUIRED = "required"
    CRITICAL = "critical"


@dataclass
class MaintenanceSchedule:
    """Maintenance schedule for a task type."""

    maintenance_type: MaintenanceType
    interval_hours: float  # Recommended interval in print hours
    interval_days: int  # Maximum days between maintenance
    description: str
    instructions: str = ""


@dataclass
class MaintenanceRecord:
    """Record of a maintenance task."""

    record_id: str
    printer_id: str
    maintenance_type: MaintenanceType
    performed_at: datetime = field(default_factory=datetime.utcnow)
    performed_by: str = ""
    notes: str = ""
    parts_replaced: List[str] = field(default_factory=list)
    print_hours_at_maintenance: float = 0.0


@dataclass
class MaintenanceTask:
    """A pending or predicted maintenance task."""

    printer_id: str
    maintenance_type: MaintenanceType
    urgency: MaintenanceUrgency
    reason: str
    due_date: Optional[datetime] = None
    estimated_duration_minutes: int = 30

    # Metrics that triggered this
    print_hours_since_last: float = 0.0
    days_since_last: int = 0

    def to_dict(self) -> dict:
        return {
            "printer_id": self.printer_id,
            "maintenance_type": self.maintenance_type.value,
            "urgency": self.urgency.value,
            "reason": self.reason,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "estimated_duration_minutes": self.estimated_duration_minutes,
        }


@dataclass
class PrinterUsageMetrics:
    """Usage metrics for maintenance prediction."""

    printer_id: str
    total_print_hours: float = 0.0
    total_prints: int = 0
    total_filament_meters: float = 0.0

    # Since last maintenance
    hours_since_nozzle_replace: float = 0.0
    hours_since_belt_tension: float = 0.0
    hours_since_lubrication: float = 0.0
    hours_since_calibration: float = 0.0
    hours_since_cleaning: float = 0.0

    # Date of last maintenance
    last_nozzle_replace: Optional[datetime] = None
    last_belt_tension: Optional[datetime] = None
    last_lubrication: Optional[datetime] = None
    last_calibration: Optional[datetime] = None
    last_cleaning: Optional[datetime] = None

    # Error counts (indicators of needed maintenance)
    failed_prints_recent: int = 0
    layer_shift_count: int = 0
    clog_count: int = 0


class MaintenancePredictor:
    """
    Predicts and tracks maintenance for print farm.

    Features:
    - Usage-based maintenance scheduling
    - Time-based maintenance reminders
    - Maintenance history tracking
    - Predictive maintenance based on error patterns
    """

    # Default maintenance schedules
    SCHEDULES: Dict[MaintenanceType, MaintenanceSchedule] = {
        MaintenanceType.NOZZLE_REPLACE: MaintenanceSchedule(
            maintenance_type=MaintenanceType.NOZZLE_REPLACE,
            interval_hours=500,  # Replace every 500 print hours
            interval_days=90,
            description="Replace printer nozzle",
            instructions="1. Heat nozzle to 250°C\n2. Remove old nozzle\n3. Install new nozzle\n4. Tighten while hot",
        ),
        MaintenanceType.BELT_TENSION: MaintenanceSchedule(
            maintenance_type=MaintenanceType.BELT_TENSION,
            interval_hours=200,
            interval_days=60,
            description="Check and adjust belt tension",
            instructions="1. Turn off printer\n2. Check X and Y belt tension\n3. Adjust tensioners if needed",
        ),
        MaintenanceType.LUBRICATION: MaintenanceSchedule(
            maintenance_type=MaintenanceType.LUBRICATION,
            interval_hours=100,
            interval_days=30,
            description="Lubricate linear rails and lead screws",
            instructions="1. Clean rails with IPA\n2. Apply light machine oil\n3. Move axes to distribute",
        ),
        MaintenanceType.CALIBRATION: MaintenanceSchedule(
            maintenance_type=MaintenanceType.CALIBRATION,
            interval_hours=300,
            interval_days=60,
            description="Full printer calibration",
            instructions="1. Bed leveling\n2. Z-offset calibration\n3. Flow rate calibration\n4. Input shaper (if supported)",
        ),
        MaintenanceType.CLEANING: MaintenanceSchedule(
            maintenance_type=MaintenanceType.CLEANING,
            interval_hours=50,
            interval_days=14,
            description="General cleaning",
            instructions="1. Clean print bed\n2. Remove debris from enclosure\n3. Clean filament path\n4. Check filters",
        ),
        MaintenanceType.FILTER_REPLACE: MaintenanceSchedule(
            maintenance_type=MaintenanceType.FILTER_REPLACE,
            interval_hours=400,
            interval_days=90,
            description="Replace air filters",
            instructions="1. Turn off printer\n2. Remove old filter\n3. Install new filter\n4. Reset filter timer",
        ),
        MaintenanceType.BED_LEVEL: MaintenanceSchedule(
            maintenance_type=MaintenanceType.BED_LEVEL,
            interval_hours=100,
            interval_days=30,
            description="Verify and adjust bed leveling",
            instructions="1. Run auto bed level\n2. Verify first layer adhesion\n3. Adjust Z-offset if needed",
        ),
    }

    def __init__(self):
        self._metrics: Dict[str, PrinterUsageMetrics] = {}
        self._history: Dict[str, List[MaintenanceRecord]] = {}
        self._schedules = dict(self.SCHEDULES)

    def register_printer(self, printer_id: str) -> None:
        """Register a printer for maintenance tracking."""
        if printer_id not in self._metrics:
            self._metrics[printer_id] = PrinterUsageMetrics(printer_id=printer_id)
            self._history[printer_id] = []
            logger.info(f"Registered printer for maintenance: {printer_id}")

    def update_metrics(self, printer_id: str, **updates) -> None:
        """Update usage metrics for a printer."""
        if printer_id not in self._metrics:
            self.register_printer(printer_id)

        metrics = self._metrics[printer_id]
        for key, value in updates.items():
            if hasattr(metrics, key):
                setattr(metrics, key, value)

    def add_print_time(self, printer_id: str, hours: float) -> None:
        """Add print time to a printer's metrics."""
        if printer_id not in self._metrics:
            self.register_printer(printer_id)

        metrics = self._metrics[printer_id]
        metrics.total_print_hours += hours
        metrics.hours_since_nozzle_replace += hours
        metrics.hours_since_belt_tension += hours
        metrics.hours_since_lubrication += hours
        metrics.hours_since_calibration += hours
        metrics.hours_since_cleaning += hours

    def record_maintenance(
        self,
        printer_id: str,
        maintenance_type: MaintenanceType,
        performed_by: str = "",
        notes: str = "",
        parts_replaced: Optional[List[str]] = None,
    ) -> MaintenanceRecord:
        """Record a completed maintenance task."""
        if printer_id not in self._metrics:
            self.register_printer(printer_id)

        metrics = self._metrics[printer_id]

        record = MaintenanceRecord(
            record_id=f"MR-{len(self._history.get(printer_id, [])) + 1:06d}",
            printer_id=printer_id,
            maintenance_type=maintenance_type,
            performed_by=performed_by,
            notes=notes,
            parts_replaced=parts_replaced or [],
            print_hours_at_maintenance=metrics.total_print_hours,
        )

        self._history.setdefault(printer_id, []).append(record)

        # Reset relevant counters
        now = datetime.utcnow()
        if maintenance_type == MaintenanceType.NOZZLE_REPLACE:
            metrics.hours_since_nozzle_replace = 0
            metrics.last_nozzle_replace = now
            metrics.clog_count = 0
        elif maintenance_type == MaintenanceType.BELT_TENSION:
            metrics.hours_since_belt_tension = 0
            metrics.last_belt_tension = now
            metrics.layer_shift_count = 0
        elif maintenance_type == MaintenanceType.LUBRICATION:
            metrics.hours_since_lubrication = 0
            metrics.last_lubrication = now
        elif maintenance_type == MaintenanceType.CALIBRATION:
            metrics.hours_since_calibration = 0
            metrics.last_calibration = now
        elif maintenance_type == MaintenanceType.CLEANING:
            metrics.hours_since_cleaning = 0
            metrics.last_cleaning = now

        logger.info(f"Recorded {maintenance_type.value} for {printer_id}")
        return record

    def get_pending_tasks(self, printer_id: str) -> List[MaintenanceTask]:
        """Get pending maintenance tasks for a printer."""
        if printer_id not in self._metrics:
            return []

        metrics = self._metrics[printer_id]
        tasks = []
        now = datetime.utcnow()

        for mtype, schedule in self._schedules.items():
            # Get hours since last maintenance
            hours_field = f"hours_since_{mtype.value}"
            date_field = f"last_{mtype.value}"

            hours_since = getattr(metrics, hours_field, 0)
            last_date = getattr(metrics, date_field, None)

            # Calculate days since
            if last_date:
                days_since = (now - last_date).days
            else:
                days_since = 999  # Never done

            # Determine urgency
            hours_ratio = hours_since / schedule.interval_hours if schedule.interval_hours > 0 else 0
            days_ratio = days_since / schedule.interval_days if schedule.interval_days > 0 else 0

            max_ratio = max(hours_ratio, days_ratio)

            if max_ratio >= 1.5:
                urgency = MaintenanceUrgency.CRITICAL
                reason = f"Overdue: {hours_since:.0f}h / {schedule.interval_hours}h or {days_since}d / {schedule.interval_days}d"
            elif max_ratio >= 1.0:
                urgency = MaintenanceUrgency.REQUIRED
                reason = f"Due: {hours_since:.0f}h print time or {days_since}d elapsed"
            elif max_ratio >= 0.8:
                urgency = MaintenanceUrgency.RECOMMENDED
                reason = f"Soon: {hours_since:.0f}h / {schedule.interval_hours}h"
            else:
                continue  # Not needed yet

            # Check for error-triggered maintenance
            if mtype == MaintenanceType.NOZZLE_REPLACE and metrics.clog_count >= 3:
                urgency = MaintenanceUrgency.REQUIRED
                reason = f"Multiple clogs detected ({metrics.clog_count})"
            elif mtype == MaintenanceType.BELT_TENSION and metrics.layer_shift_count >= 2:
                urgency = MaintenanceUrgency.REQUIRED
                reason = f"Layer shifts detected ({metrics.layer_shift_count})"

            tasks.append(MaintenanceTask(
                printer_id=printer_id,
                maintenance_type=mtype,
                urgency=urgency,
                reason=reason,
                print_hours_since_last=hours_since,
                days_since_last=days_since,
            ))

        # Sort by urgency
        urgency_order = {
            MaintenanceUrgency.CRITICAL: 0,
            MaintenanceUrgency.REQUIRED: 1,
            MaintenanceUrgency.RECOMMENDED: 2,
            MaintenanceUrgency.OPTIONAL: 3,
        }
        tasks.sort(key=lambda t: urgency_order[t.urgency])

        return tasks

    def get_all_pending_tasks(self) -> Dict[str, List[MaintenanceTask]]:
        """Get pending tasks for all printers."""
        return {
            printer_id: self.get_pending_tasks(printer_id)
            for printer_id in self._metrics.keys()
        }

    def get_history(
        self,
        printer_id: str,
        maintenance_type: Optional[MaintenanceType] = None,
        limit: int = 50,
    ) -> List[MaintenanceRecord]:
        """Get maintenance history for a printer."""
        records = self._history.get(printer_id, [])

        if maintenance_type:
            records = [r for r in records if r.maintenance_type == maintenance_type]

        return sorted(records, key=lambda r: r.performed_at, reverse=True)[:limit]

    def get_maintenance_summary(self) -> dict:
        """Get summary of maintenance status across the farm."""
        all_tasks = self.get_all_pending_tasks()

        by_urgency = {urgency: 0 for urgency in MaintenanceUrgency}
        by_type = {mtype: 0 for mtype in MaintenanceType}

        for tasks in all_tasks.values():
            for task in tasks:
                by_urgency[task.urgency] += 1
                by_type[task.maintenance_type] += 1

        return {
            "total_printers": len(self._metrics),
            "printers_need_maintenance": sum(
                1 for tasks in all_tasks.values()
                if any(t.urgency in [MaintenanceUrgency.CRITICAL, MaintenanceUrgency.REQUIRED] for t in tasks)
            ),
            "critical_tasks": by_urgency[MaintenanceUrgency.CRITICAL],
            "required_tasks": by_urgency[MaintenanceUrgency.REQUIRED],
            "recommended_tasks": by_urgency[MaintenanceUrgency.RECOMMENDED],
            "by_type": {k.value: v for k, v in by_type.items() if v > 0},
        }


# Global predictor instance
_predictor: Optional[MaintenancePredictor] = None


def get_maintenance_predictor() -> MaintenancePredictor:
    """Get the global maintenance predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = MaintenancePredictor()
    return _predictor
