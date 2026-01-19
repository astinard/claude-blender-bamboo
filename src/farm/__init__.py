"""Print Farm Management module for Claude Fab Lab.

Provides tools for managing fleets of 10-100+ 3D printers including:
- Job optimization and distribution
- Farm-wide scheduling
- Real-time fleet monitoring
- Predictive maintenance
"""

from src.farm.optimizer import (
    FarmOptimizer,
    PrinterProfile,
    PrintJob,
    Assignment,
    OptimizationResult,
    OptimizationGoal,
    PrinterCapability,
    get_farm_optimizer,
)

from src.farm.scheduler import (
    FarmScheduler,
    ScheduledJob,
    ScheduleSlot,
    ScheduleStatus,
    JobState,
    get_farm_scheduler,
    init_farm_scheduler,
)

from src.farm.monitoring import (
    FarmMonitor,
    PrinterState,
    PrinterStatus,
    Alert,
    AlertSeverity,
    FarmMetrics,
    get_farm_monitor,
    init_farm_monitor,
)

from src.farm.maintenance import (
    MaintenancePredictor,
    MaintenanceTask,
    MaintenanceRecord,
    MaintenanceSchedule,
    MaintenanceType,
    MaintenanceUrgency,
    PrinterUsageMetrics,
    get_maintenance_predictor,
)

__all__ = [
    # Optimizer
    "FarmOptimizer",
    "PrinterProfile",
    "PrintJob",
    "Assignment",
    "OptimizationResult",
    "OptimizationGoal",
    "PrinterCapability",
    "get_farm_optimizer",
    # Scheduler
    "FarmScheduler",
    "ScheduledJob",
    "ScheduleSlot",
    "ScheduleStatus",
    "JobState",
    "get_farm_scheduler",
    "init_farm_scheduler",
    # Monitoring
    "FarmMonitor",
    "PrinterState",
    "PrinterStatus",
    "Alert",
    "AlertSeverity",
    "FarmMetrics",
    "get_farm_monitor",
    "init_farm_monitor",
    # Maintenance
    "MaintenancePredictor",
    "MaintenanceTask",
    "MaintenanceRecord",
    "MaintenanceSchedule",
    "MaintenanceType",
    "MaintenanceUrgency",
    "PrinterUsageMetrics",
    "get_maintenance_predictor",
]
