"""Maintenance predictor for 3D printers.

Predicts maintenance needs based on printer usage statistics.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from src.utils import get_logger
from src.config import get_settings
from src.maintenance.schedules import (
    MaintenanceSchedule,
    ScheduleItem,
    ScheduleType,
    get_default_schedule,
)

logger = get_logger("maintenance.predictor")


class MaintenanceType(str, Enum):
    """Types of maintenance tasks."""
    INSPECTION = "inspection"
    CLEANING = "cleaning"
    LUBRICATION = "lubrication"
    REPLACEMENT = "replacement"
    CALIBRATION = "calibration"
    UPDATE = "update"


class AlertPriority(str, Enum):
    """Maintenance alert priority levels."""
    LOW = "low"  # Informational
    MEDIUM = "medium"  # Should address soon
    HIGH = "high"  # Address before next print
    CRITICAL = "critical"  # Address immediately


@dataclass
class PrinterStats:
    """Printer usage statistics."""
    total_print_hours: float = 0.0
    total_prints: int = 0
    total_material_grams: float = 0.0
    days_since_setup: int = 0
    last_maintenance: Dict[str, str] = field(default_factory=dict)  # component -> date

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_print_hours": self.total_print_hours,
            "total_prints": self.total_prints,
            "total_material_grams": self.total_material_grams,
            "days_since_setup": self.days_since_setup,
            "last_maintenance": self.last_maintenance,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PrinterStats":
        """Create from dictionary."""
        return cls(
            total_print_hours=data.get("total_print_hours", 0.0),
            total_prints=data.get("total_prints", 0),
            total_material_grams=data.get("total_material_grams", 0.0),
            days_since_setup=data.get("days_since_setup", 0),
            last_maintenance=data.get("last_maintenance", {}),
        )


@dataclass
class MaintenanceAlert:
    """A maintenance alert."""
    alert_id: str
    task_name: str
    component: str
    priority: AlertPriority
    description: str
    instructions: List[str]
    progress_percent: float  # How far through the interval (100% = due)
    due_at: Optional[str] = None  # When maintenance is due
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "task_name": self.task_name,
            "component": self.component,
            "priority": self.priority.value,
            "description": self.description,
            "instructions": self.instructions,
            "progress_percent": self.progress_percent,
            "due_at": self.due_at,
            "created_at": self.created_at,
        }


class MaintenancePredictor:
    """
    Predicts maintenance needs based on printer usage.

    Tracks usage statistics and generates alerts when maintenance
    tasks are due or approaching.
    """

    def __init__(
        self,
        printer_model: str = "bambu_x1c",
        schedule: Optional[MaintenanceSchedule] = None,
        data_file: Optional[Path] = None,
    ):
        """
        Initialize maintenance predictor.

        Args:
            printer_model: Printer model for default schedule
            schedule: Custom maintenance schedule
            data_file: Path to persistence file
        """
        self.printer_model = printer_model
        self.schedule = schedule or get_default_schedule(printer_model)

        settings = get_settings()
        self._data_file = data_file or Path(settings.data_dir) / "maintenance.json"
        self._stats = PrinterStats()
        self._maintenance_history: List[dict] = []

        self._load()

    def _load(self) -> None:
        """Load data from persistence file."""
        if self._data_file.exists():
            try:
                data = json.loads(self._data_file.read_text())
                self._stats = PrinterStats.from_dict(data.get("stats", {}))
                self._maintenance_history = data.get("history", [])
            except Exception as e:
                logger.error(f"Failed to load maintenance data: {e}")

    def _save(self) -> None:
        """Save data to persistence file."""
        try:
            self._data_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "stats": self._stats.to_dict(),
                "history": self._maintenance_history,
            }
            self._data_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save maintenance data: {e}")

    @property
    def stats(self) -> PrinterStats:
        """Get current printer statistics."""
        return self._stats

    def update_stats(
        self,
        print_hours: Optional[float] = None,
        prints: Optional[int] = None,
        material_grams: Optional[float] = None,
    ) -> None:
        """
        Update printer statistics.

        Args:
            print_hours: Hours to add
            prints: Number of prints to add
            material_grams: Grams of material to add
        """
        if print_hours is not None:
            self._stats.total_print_hours += print_hours
        if prints is not None:
            self._stats.total_prints += prints
        if material_grams is not None:
            self._stats.total_material_grams += material_grams

        # Update days since setup
        self._stats.days_since_setup = (
            datetime.now() - datetime.fromisoformat(
                self._maintenance_history[0]["date"]
                if self._maintenance_history else datetime.now().isoformat()
            )
        ).days if self._maintenance_history else 0

        self._save()
        logger.debug(f"Updated stats: hours={self._stats.total_print_hours}, prints={self._stats.total_prints}")

    def record_maintenance(
        self,
        component: str,
        task_name: str,
        notes: Optional[str] = None,
    ) -> None:
        """
        Record that maintenance was performed.

        Args:
            component: Component that was maintained
            task_name: Name of maintenance task
            notes: Optional notes
        """
        now = datetime.now().isoformat()

        # Update last maintenance for component
        self._stats.last_maintenance[component] = now

        # Add to history
        self._maintenance_history.append({
            "date": now,
            "component": component,
            "task": task_name,
            "notes": notes,
            "stats_at_time": {
                "print_hours": self._stats.total_print_hours,
                "prints": self._stats.total_prints,
                "material_grams": self._stats.total_material_grams,
            },
        })

        self._save()
        logger.info(f"Recorded maintenance: {task_name} on {component}")

    def get_maintenance_history(
        self,
        component: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """
        Get maintenance history.

        Args:
            component: Filter by component
            limit: Maximum entries to return

        Returns:
            List of maintenance history entries
        """
        history = self._maintenance_history
        if component:
            history = [h for h in history if h.get("component") == component]
        return history[-limit:]

    def get_alerts(self) -> List[MaintenanceAlert]:
        """
        Get all maintenance alerts based on current stats.

        Returns:
            List of maintenance alerts sorted by priority
        """
        alerts = []
        alert_counter = 0

        for item in self.schedule.items:
            progress = self._calculate_progress(item)

            if progress >= item.warning_threshold * 100:
                # Determine priority
                if progress >= item.critical_threshold * 100 * 1.2:
                    priority = AlertPriority.CRITICAL
                elif progress >= item.critical_threshold * 100:
                    priority = AlertPriority.HIGH
                elif progress >= item.warning_threshold * 100:
                    priority = AlertPriority.MEDIUM
                else:
                    priority = AlertPriority.LOW

                alert_counter += 1
                alert = MaintenanceAlert(
                    alert_id=f"maint_{alert_counter:04d}",
                    task_name=item.name,
                    component=item.component,
                    priority=priority,
                    description=item.description,
                    instructions=item.instructions,
                    progress_percent=progress,
                    due_at=self._estimate_due_date(item),
                )
                alerts.append(alert)

        # Sort by priority (critical first)
        priority_order = {
            AlertPriority.CRITICAL: 0,
            AlertPriority.HIGH: 1,
            AlertPriority.MEDIUM: 2,
            AlertPriority.LOW: 3,
        }
        alerts.sort(key=lambda a: (priority_order[a.priority], -a.progress_percent))

        return alerts

    def _calculate_progress(self, item: ScheduleItem) -> float:
        """Calculate progress toward maintenance interval (0-100+)."""
        # Get value since last maintenance
        last_maintenance = self._stats.last_maintenance.get(item.component)

        if item.schedule_type == ScheduleType.HOURS:
            # Hours since last maintenance
            if last_maintenance:
                # Find hours at last maintenance from history
                hours_at_maint = self._get_hours_at_maintenance(item.component)
                current = self._stats.total_print_hours - hours_at_maint
            else:
                current = self._stats.total_print_hours

        elif item.schedule_type == ScheduleType.PRINTS:
            if last_maintenance:
                prints_at_maint = self._get_prints_at_maintenance(item.component)
                current = self._stats.total_prints - prints_at_maint
            else:
                current = self._stats.total_prints

        elif item.schedule_type == ScheduleType.MATERIAL:
            if last_maintenance:
                material_at_maint = self._get_material_at_maintenance(item.component)
                current = self._stats.total_material_grams - material_at_maint
            else:
                current = self._stats.total_material_grams

        elif item.schedule_type == ScheduleType.DAYS:
            if last_maintenance:
                last_date = datetime.fromisoformat(last_maintenance)
                current = (datetime.now() - last_date).days
            else:
                current = self._stats.days_since_setup

        else:
            current = 0

        if item.interval <= 0:
            return 0

        return (current / item.interval) * 100

    def _get_hours_at_maintenance(self, component: str) -> float:
        """Get print hours at last maintenance for component."""
        for entry in reversed(self._maintenance_history):
            if entry.get("component") == component:
                return entry.get("stats_at_time", {}).get("print_hours", 0)
        return 0

    def _get_prints_at_maintenance(self, component: str) -> int:
        """Get print count at last maintenance for component."""
        for entry in reversed(self._maintenance_history):
            if entry.get("component") == component:
                return entry.get("stats_at_time", {}).get("prints", 0)
        return 0

    def _get_material_at_maintenance(self, component: str) -> float:
        """Get material usage at last maintenance for component."""
        for entry in reversed(self._maintenance_history):
            if entry.get("component") == component:
                return entry.get("stats_at_time", {}).get("material_grams", 0)
        return 0

    def _estimate_due_date(self, item: ScheduleItem) -> Optional[str]:
        """Estimate when maintenance will be due."""
        progress = self._calculate_progress(item)

        if progress >= 100:
            return "Now"

        remaining_percent = 100 - progress
        remaining_interval = (remaining_percent / 100) * item.interval

        if item.schedule_type == ScheduleType.DAYS:
            due_date = datetime.now() + timedelta(days=remaining_interval)
            return due_date.strftime("%Y-%m-%d")

        elif item.schedule_type == ScheduleType.HOURS:
            # Estimate based on average usage
            if self._stats.days_since_setup > 0:
                hours_per_day = self._stats.total_print_hours / self._stats.days_since_setup
                if hours_per_day > 0:
                    days_remaining = remaining_interval / hours_per_day
                    due_date = datetime.now() + timedelta(days=days_remaining)
                    return due_date.strftime("%Y-%m-%d")

        elif item.schedule_type == ScheduleType.PRINTS:
            if self._stats.days_since_setup > 0:
                prints_per_day = self._stats.total_prints / self._stats.days_since_setup
                if prints_per_day > 0:
                    days_remaining = remaining_interval / prints_per_day
                    due_date = datetime.now() + timedelta(days=days_remaining)
                    return due_date.strftime("%Y-%m-%d")

        return None

    def get_component_status(self, component: str) -> dict:
        """
        Get maintenance status for a specific component.

        Args:
            component: Component name

        Returns:
            Status dictionary
        """
        items = self.schedule.get_items_by_component(component)
        alerts = [a for a in self.get_alerts() if a.component == component]

        last_maintenance = self._stats.last_maintenance.get(component)

        return {
            "component": component,
            "last_maintenance": last_maintenance,
            "tasks": [item.to_dict() for item in items],
            "alerts": [a.to_dict() for a in alerts],
            "status": "critical" if any(a.priority == AlertPriority.CRITICAL for a in alerts)
                     else "warning" if any(a.priority in [AlertPriority.HIGH, AlertPriority.MEDIUM] for a in alerts)
                     else "good",
        }

    def get_overall_status(self) -> dict:
        """
        Get overall maintenance status.

        Returns:
            Status summary
        """
        alerts = self.get_alerts()

        critical_count = sum(1 for a in alerts if a.priority == AlertPriority.CRITICAL)
        high_count = sum(1 for a in alerts if a.priority == AlertPriority.HIGH)
        medium_count = sum(1 for a in alerts if a.priority == AlertPriority.MEDIUM)

        components = list(set(item.component for item in self.schedule.items))

        return {
            "status": "critical" if critical_count > 0
                     else "warning" if high_count > 0
                     else "attention" if medium_count > 0
                     else "good",
            "stats": self._stats.to_dict(),
            "alerts_summary": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "total": len(alerts),
            },
            "components": {comp: self.get_component_status(comp)["status"] for comp in components},
        }


def predict_maintenance(
    print_hours: float,
    total_prints: int,
    material_grams: float,
    printer_model: str = "bambu_x1c",
) -> List[MaintenanceAlert]:
    """
    Convenience function to predict maintenance needs.

    Args:
        print_hours: Total print hours
        total_prints: Total number of prints
        material_grams: Total material used in grams
        printer_model: Printer model

    Returns:
        List of maintenance alerts
    """
    predictor = MaintenancePredictor(printer_model=printer_model)
    predictor._stats.total_print_hours = print_hours
    predictor._stats.total_prints = total_prints
    predictor._stats.total_material_grams = material_grams

    return predictor.get_alerts()
