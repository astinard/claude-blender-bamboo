"""Maintenance schedules for 3D printers.

Defines standard maintenance intervals and tasks for Bambu Lab printers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ScheduleType(str, Enum):
    """Types of maintenance schedules."""
    HOURS = "hours"  # Based on print hours
    DAYS = "days"  # Based on calendar days
    PRINTS = "prints"  # Based on number of prints
    MATERIAL = "material"  # Based on material used (grams)


@dataclass
class ScheduleItem:
    """A maintenance task schedule item."""
    name: str
    description: str
    schedule_type: ScheduleType
    interval: float  # Interval value (hours, days, prints, or grams)
    component: str  # Component this applies to
    instructions: List[str] = field(default_factory=list)
    warning_threshold: float = 0.8  # Warn at 80% of interval
    critical_threshold: float = 1.0  # Critical at 100% of interval

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "schedule_type": self.schedule_type.value,
            "interval": self.interval,
            "component": self.component,
            "instructions": self.instructions,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduleItem":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            schedule_type=ScheduleType(data["schedule_type"]),
            interval=data["interval"],
            component=data["component"],
            instructions=data.get("instructions", []),
            warning_threshold=data.get("warning_threshold", 0.8),
            critical_threshold=data.get("critical_threshold", 1.0),
        )


@dataclass
class MaintenanceSchedule:
    """Complete maintenance schedule for a printer."""
    printer_model: str
    items: List[ScheduleItem] = field(default_factory=list)

    def get_items_by_component(self, component: str) -> List[ScheduleItem]:
        """Get all schedule items for a component."""
        return [item for item in self.items if item.component == component]

    def get_items_by_type(self, schedule_type: ScheduleType) -> List[ScheduleItem]:
        """Get all schedule items of a type."""
        return [item for item in self.items if item.schedule_type == schedule_type]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "printer_model": self.printer_model,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MaintenanceSchedule":
        """Create from dictionary."""
        return cls(
            printer_model=data["printer_model"],
            items=[ScheduleItem.from_dict(item) for item in data.get("items", [])],
        )


def get_default_schedule(printer_model: str = "bambu_x1c") -> MaintenanceSchedule:
    """
    Get default maintenance schedule for a printer model.

    Args:
        printer_model: Printer model identifier

    Returns:
        Maintenance schedule with default items
    """
    # Default schedule for Bambu Lab X1 Carbon
    items = [
        # Nozzle maintenance
        ScheduleItem(
            name="Nozzle Inspection",
            description="Inspect nozzle for wear and clogs",
            schedule_type=ScheduleType.HOURS,
            interval=100,  # Every 100 print hours
            component="nozzle",
            instructions=[
                "Heat nozzle to printing temperature",
                "Inspect nozzle tip for damage or buildup",
                "Check for stringing or poor extrusion quality",
                "Clean nozzle with brass brush if needed",
            ],
        ),
        ScheduleItem(
            name="Nozzle Replacement",
            description="Replace hardened steel nozzle",
            schedule_type=ScheduleType.HOURS,
            interval=500,  # Every 500 print hours
            component="nozzle",
            instructions=[
                "Heat nozzle to printing temperature",
                "Carefully unload filament",
                "Remove old nozzle with wrench",
                "Install new nozzle and tighten",
                "Re-calibrate Z offset if needed",
            ],
        ),

        # Hotend maintenance
        ScheduleItem(
            name="Hotend Cleaning",
            description="Clean hotend and heat break",
            schedule_type=ScheduleType.HOURS,
            interval=200,
            component="hotend",
            instructions=[
                "Allow hotend to cool completely",
                "Perform cold pull to clean",
                "Check PTFE tube condition",
                "Inspect heat break for debris",
            ],
        ),

        # Bed maintenance
        ScheduleItem(
            name="Bed Cleaning",
            description="Clean print bed surface",
            schedule_type=ScheduleType.PRINTS,
            interval=10,  # Every 10 prints
            component="bed",
            instructions=[
                "Allow bed to cool completely",
                "Clean with isopropyl alcohol (90%+)",
                "Remove any adhesive residue",
                "Check for scratches or damage",
            ],
        ),
        ScheduleItem(
            name="Bed Level Check",
            description="Verify bed level and mesh",
            schedule_type=ScheduleType.DAYS,
            interval=30,  # Monthly
            component="bed",
            instructions=[
                "Run auto bed leveling routine",
                "Check for any major deviations",
                "Clean bed before leveling",
                "Consider re-tramming if consistently off",
            ],
        ),

        # Belt maintenance
        ScheduleItem(
            name="Belt Tension Check",
            description="Check X and Y belt tension",
            schedule_type=ScheduleType.HOURS,
            interval=200,
            component="belts",
            instructions=[
                "Check belt tension on X axis",
                "Check belt tension on Y axis",
                "Adjust tensioners if needed",
                "Listen for unusual sounds during movement",
            ],
        ),
        ScheduleItem(
            name="Belt Replacement",
            description="Replace timing belts",
            schedule_type=ScheduleType.HOURS,
            interval=2000,  # Every 2000 print hours
            component="belts",
            instructions=[
                "Order replacement belts from manufacturer",
                "Follow official belt replacement guide",
                "Re-calibrate after replacement",
                "Test with calibration prints",
            ],
        ),

        # Lubrication
        ScheduleItem(
            name="Rod Lubrication",
            description="Lubricate linear rods",
            schedule_type=ScheduleType.HOURS,
            interval=100,
            component="motion",
            instructions=[
                "Wipe clean existing lubricant",
                "Apply thin layer of PTFE-based lubricant",
                "Move axes through full range",
                "Wipe excess lubricant",
            ],
        ),
        ScheduleItem(
            name="Lead Screw Lubrication",
            description="Lubricate Z lead screws",
            schedule_type=ScheduleType.HOURS,
            interval=200,
            component="motion",
            instructions=[
                "Clean lead screws with cloth",
                "Apply appropriate grease",
                "Move Z axis through full range",
                "Check for smooth movement",
            ],
        ),

        # Fans
        ScheduleItem(
            name="Fan Cleaning",
            description="Clean cooling fans",
            schedule_type=ScheduleType.DAYS,
            interval=30,  # Monthly
            component="fans",
            instructions=[
                "Power off printer",
                "Use compressed air to clean fans",
                "Check for debris in ducts",
                "Listen for bearing noise on startup",
            ],
        ),

        # Filament path
        ScheduleItem(
            name="Filament Path Inspection",
            description="Inspect PTFE tubes and fittings",
            schedule_type=ScheduleType.MATERIAL,
            interval=5000,  # Every 5kg of filament
            component="filament_path",
            instructions=[
                "Check PTFE tube for damage or wear",
                "Inspect pneumatic fittings",
                "Check for filament debris",
                "Replace PTFE if showing wear",
            ],
        ),

        # AMS maintenance (if applicable)
        ScheduleItem(
            name="AMS Cleaning",
            description="Clean AMS unit and buffer",
            schedule_type=ScheduleType.DAYS,
            interval=14,  # Bi-weekly
            component="ams",
            instructions=[
                "Clean AMS feed tubes",
                "Check buffer position",
                "Inspect spool holders",
                "Test color switching",
            ],
        ),

        # General maintenance
        ScheduleItem(
            name="Firmware Update Check",
            description="Check for firmware updates",
            schedule_type=ScheduleType.DAYS,
            interval=14,  # Bi-weekly
            component="system",
            instructions=[
                "Check Bambu Handy app for updates",
                "Review release notes",
                "Backup current settings if needed",
                "Apply updates during non-print time",
            ],
        ),
        ScheduleItem(
            name="Cable Inspection",
            description="Inspect cables and connectors",
            schedule_type=ScheduleType.DAYS,
            interval=90,  # Quarterly
            component="electrical",
            instructions=[
                "Check all visible cable connections",
                "Look for wear at bend points",
                "Inspect cable chain routing",
                "Check for loose connections",
            ],
        ),
    ]

    return MaintenanceSchedule(
        printer_model=printer_model,
        items=items,
    )


# Default schedules for different printer models
PRINTER_SCHEDULES: Dict[str, MaintenanceSchedule] = {
    "bambu_x1c": get_default_schedule("bambu_x1c"),
    "bambu_p1s": get_default_schedule("bambu_p1s"),
    "bambu_a1": get_default_schedule("bambu_a1"),
}


def get_schedule_for_printer(model: str) -> MaintenanceSchedule:
    """Get maintenance schedule for a specific printer model."""
    return PRINTER_SCHEDULES.get(model, get_default_schedule(model))
