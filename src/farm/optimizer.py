"""Job distribution optimizer for print farms.

Uses optimization algorithms to distribute print jobs across
multiple printers for maximum throughput and efficiency.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from uuid import uuid4

from src.utils import get_logger

logger = get_logger("farm.optimizer")


class OptimizationGoal(str, Enum):
    """Optimization objectives."""
    MINIMIZE_TIME = "minimize_time"  # Fastest completion
    MINIMIZE_COST = "minimize_cost"  # Lowest material/energy cost
    MAXIMIZE_UTILIZATION = "maximize_utilization"  # Keep printers busy
    BALANCED = "balanced"  # Balance all factors


class PrinterCapability(str, Enum):
    """Printer capabilities."""
    FDM = "fdm"
    SLA = "sla"
    SLS = "sls"
    MJF = "mjf"
    METAL = "metal"
    MULTI_COLOR = "multi_color"
    LARGE_FORMAT = "large_format"
    HIGH_SPEED = "high_speed"


@dataclass
class PrinterProfile:
    """Profile of a printer in the farm."""

    printer_id: str
    name: str
    model: str
    capabilities: List[PrinterCapability] = field(default_factory=list)

    # Build volume (mm)
    build_x: float = 256.0
    build_y: float = 256.0
    build_z: float = 256.0

    # Performance
    print_speed_mm_s: float = 100.0
    layer_height_range: Tuple[float, float] = (0.1, 0.3)

    # Materials
    supported_materials: List[str] = field(default_factory=list)
    current_material: Optional[str] = None
    has_ams: bool = False
    ams_slots: int = 0

    # Cost factors
    hourly_cost: float = 5.0  # Operating cost per hour
    material_cost_multiplier: float = 1.0

    # Status
    available: bool = True
    current_job_id: Optional[str] = None
    estimated_free_at: Optional[datetime] = None
    maintenance_due: bool = False

    # Location
    location: str = ""
    zone: str = ""

    def can_print(self, job: "PrintJob") -> bool:
        """Check if printer can handle the job."""
        # Check build volume
        if job.size_x > self.build_x or job.size_y > self.build_y or job.size_z > self.build_z:
            return False

        # Check material
        if job.material and job.material not in self.supported_materials:
            return False

        # Check capabilities
        for cap in job.required_capabilities:
            if cap not in self.capabilities:
                return False

        return True

    def estimate_time(self, job: "PrintJob") -> float:
        """Estimate print time in hours."""
        # Simplified estimation based on volume and speed
        volume_mm3 = job.size_x * job.size_y * job.size_z * 0.2  # Assume 20% fill
        layers = job.size_z / 0.2  # Assume 0.2mm layers

        # Time = layers * layer_time + volume / deposition_rate
        layer_time_s = (job.size_x * job.size_y) / (self.print_speed_mm_s * 50)  # Rough estimate
        total_seconds = layers * layer_time_s

        return total_seconds / 3600  # Convert to hours

    def estimate_cost(self, job: "PrintJob") -> float:
        """Estimate print cost."""
        time_hours = self.estimate_time(job)
        return time_hours * self.hourly_cost * self.material_cost_multiplier


@dataclass
class PrintJob:
    """A print job to be scheduled."""

    job_id: str = field(default_factory=lambda: str(uuid4())[:8])
    name: str = ""
    model_path: str = ""

    # Dimensions (mm)
    size_x: float = 50.0
    size_y: float = 50.0
    size_z: float = 50.0

    # Requirements
    material: Optional[str] = None
    colors: List[str] = field(default_factory=list)
    required_capabilities: List[PrinterCapability] = field(default_factory=list)

    # Timing
    priority: int = 0  # Higher = more important
    deadline: Optional[datetime] = None
    estimated_duration_hours: float = 1.0

    # Organization
    organization_id: Optional[str] = None
    user_id: Optional[str] = None

    # Status
    assigned_printer: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    status: str = "pending"


@dataclass
class Assignment:
    """Job-to-printer assignment."""

    job_id: str
    printer_id: str
    start_time: datetime
    end_time: datetime
    estimated_cost: float
    score: float  # Optimization score


@dataclass
class OptimizationResult:
    """Result of job optimization."""

    assignments: List[Assignment]
    unassigned_jobs: List[str]
    total_time_hours: float
    total_cost: float
    utilization_percent: float
    optimization_goal: OptimizationGoal
    computed_at: datetime = field(default_factory=datetime.utcnow)


class FarmOptimizer:
    """
    Optimizes job distribution across a print farm.

    Uses greedy and constraint-based optimization to:
    - Minimize total completion time
    - Balance workload across printers
    - Respect material and capability constraints
    - Handle priorities and deadlines
    """

    def __init__(self):
        self._printers: Dict[str, PrinterProfile] = {}

    def register_printer(self, printer: PrinterProfile) -> None:
        """Register a printer with the farm."""
        self._printers[printer.printer_id] = printer
        logger.info(f"Registered printer: {printer.printer_id} ({printer.model})")

    def remove_printer(self, printer_id: str) -> None:
        """Remove a printer from the farm."""
        if printer_id in self._printers:
            del self._printers[printer_id]

    def get_printer(self, printer_id: str) -> Optional[PrinterProfile]:
        """Get a printer by ID."""
        return self._printers.get(printer_id)

    def get_available_printers(self) -> List[PrinterProfile]:
        """Get all available printers."""
        return [p for p in self._printers.values() if p.available and not p.maintenance_due]

    def find_compatible_printers(self, job: PrintJob) -> List[PrinterProfile]:
        """Find printers that can handle a job."""
        return [p for p in self.get_available_printers() if p.can_print(job)]

    def optimize(
        self,
        jobs: List[PrintJob],
        goal: OptimizationGoal = OptimizationGoal.BALANCED,
        time_horizon_hours: float = 168.0,  # 1 week
    ) -> OptimizationResult:
        """
        Optimize job distribution across the farm.

        Args:
            jobs: List of jobs to schedule
            goal: Optimization goal
            time_horizon_hours: Planning horizon

        Returns:
            OptimizationResult with assignments
        """
        logger.info(f"Optimizing {len(jobs)} jobs with goal: {goal.value}")

        # Sort jobs by priority and deadline
        sorted_jobs = sorted(
            jobs,
            key=lambda j: (-j.priority, j.deadline or datetime.max),
        )

        assignments = []
        unassigned = []

        # Track printer availability
        printer_end_times: Dict[str, datetime] = {
            p.printer_id: p.estimated_free_at or datetime.utcnow()
            for p in self._printers.values()
        }

        for job in sorted_jobs:
            compatible = self.find_compatible_printers(job)

            if not compatible:
                unassigned.append(job.job_id)
                logger.warning(f"No compatible printer for job {job.job_id}")
                continue

            # Score each compatible printer based on optimization goal
            best_printer = None
            best_score = float("inf")
            best_start = None
            best_end = None
            best_cost = 0.0

            for printer in compatible:
                start_time = max(
                    printer_end_times.get(printer.printer_id, datetime.utcnow()),
                    datetime.utcnow(),
                )
                duration_hours = printer.estimate_time(job)
                end_time = start_time + timedelta(hours=duration_hours)
                cost = printer.estimate_cost(job)

                # Calculate score based on goal
                score = self._calculate_score(
                    goal=goal,
                    start_time=start_time,
                    end_time=end_time,
                    cost=cost,
                    deadline=job.deadline,
                    printer=printer,
                )

                if score < best_score:
                    best_score = score
                    best_printer = printer
                    best_start = start_time
                    best_end = end_time
                    best_cost = cost

            if best_printer:
                assignment = Assignment(
                    job_id=job.job_id,
                    printer_id=best_printer.printer_id,
                    start_time=best_start,
                    end_time=best_end,
                    estimated_cost=best_cost,
                    score=best_score,
                )
                assignments.append(assignment)

                # Update printer availability
                printer_end_times[best_printer.printer_id] = best_end

                logger.debug(f"Assigned {job.job_id} to {best_printer.printer_id}")
            else:
                unassigned.append(job.job_id)

        # Calculate summary statistics
        total_time = sum(
            (a.end_time - a.start_time).total_seconds() / 3600
            for a in assignments
        )
        total_cost = sum(a.estimated_cost for a in assignments)

        # Calculate utilization
        if assignments:
            min_start = min(a.start_time for a in assignments)
            max_end = max(a.end_time for a in assignments)
            total_span = (max_end - min_start).total_seconds() / 3600
            max_printer_hours = total_span * len(self._printers)
            utilization = (total_time / max_printer_hours * 100) if max_printer_hours > 0 else 0
        else:
            utilization = 0

        result = OptimizationResult(
            assignments=assignments,
            unassigned_jobs=unassigned,
            total_time_hours=total_time,
            total_cost=total_cost,
            utilization_percent=utilization,
            optimization_goal=goal,
        )

        logger.info(
            f"Optimization complete: {len(assignments)} assigned, "
            f"{len(unassigned)} unassigned, {utilization:.1f}% utilization"
        )

        return result

    def _calculate_score(
        self,
        goal: OptimizationGoal,
        start_time: datetime,
        end_time: datetime,
        cost: float,
        deadline: Optional[datetime],
        printer: PrinterProfile,
    ) -> float:
        """Calculate optimization score (lower is better)."""
        duration_hours = (end_time - start_time).total_seconds() / 3600
        wait_hours = (start_time - datetime.utcnow()).total_seconds() / 3600

        if goal == OptimizationGoal.MINIMIZE_TIME:
            # Prioritize earliest completion
            return wait_hours + duration_hours

        elif goal == OptimizationGoal.MINIMIZE_COST:
            # Prioritize lowest cost
            return cost

        elif goal == OptimizationGoal.MAXIMIZE_UTILIZATION:
            # Prioritize keeping printers busy (minimize wait)
            return wait_hours * 2 + duration_hours

        else:  # BALANCED
            # Weighted combination
            time_score = wait_hours + duration_hours
            cost_score = cost / 10  # Normalize
            deadline_penalty = 0

            if deadline:
                slack = (deadline - end_time).total_seconds() / 3600
                if slack < 0:
                    deadline_penalty = abs(slack) * 100  # Heavy penalty for missing deadline
                elif slack < 24:
                    deadline_penalty = (24 - slack) * 2  # Mild penalty for tight deadline

            return time_score + cost_score + deadline_penalty

    def rebalance(self, max_migrations: int = 5) -> List[Tuple[str, str, str]]:
        """
        Rebalance jobs across printers.

        Returns list of (job_id, from_printer, to_printer) migrations.
        """
        # Find overloaded and underloaded printers
        workloads = {}
        for printer in self._printers.values():
            if printer.estimated_free_at:
                workloads[printer.printer_id] = (
                    printer.estimated_free_at - datetime.utcnow()
                ).total_seconds() / 3600
            else:
                workloads[printer.printer_id] = 0

        if not workloads:
            return []

        avg_workload = sum(workloads.values()) / len(workloads)
        overloaded = {k: v for k, v in workloads.items() if v > avg_workload * 1.5}
        underloaded = {k: v for k, v in workloads.items() if v < avg_workload * 0.5}

        migrations = []
        # In a real implementation, would migrate pending jobs from overloaded to underloaded

        return migrations[:max_migrations]


# Global optimizer instance
_optimizer: Optional[FarmOptimizer] = None


def get_farm_optimizer() -> FarmOptimizer:
    """Get the global farm optimizer instance."""
    global _optimizer
    if _optimizer is None:
        _optimizer = FarmOptimizer()
    return _optimizer
