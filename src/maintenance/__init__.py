"""Maintenance module for Claude Fab Lab.

Predicts maintenance needs based on printer usage and schedules.
"""

from src.maintenance.predictor import (
    MaintenancePredictor,
    MaintenanceAlert,
    MaintenanceType,
    AlertPriority,
    PrinterStats,
    predict_maintenance,
)
from src.maintenance.schedules import (
    MaintenanceSchedule,
    ScheduleItem,
    ScheduleType,
    get_default_schedule,
)

__all__ = [
    "MaintenancePredictor",
    "MaintenanceAlert",
    "MaintenanceType",
    "AlertPriority",
    "PrinterStats",
    "predict_maintenance",
    "MaintenanceSchedule",
    "ScheduleItem",
    "ScheduleType",
    "get_default_schedule",
]
