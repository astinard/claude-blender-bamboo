"""Farm-wide scheduling for print operations.

Coordinates job scheduling across all printers in the farm,
handling priorities, dependencies, and resource constraints.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Awaitable
from uuid import uuid4

from src.utils import get_logger
from src.farm.optimizer import (
    FarmOptimizer,
    PrintJob,
    PrinterProfile,
    OptimizationGoal,
    Assignment,
    get_farm_optimizer,
)

logger = get_logger("farm.scheduler")


class ScheduleStatus(str, Enum):
    """Status of the scheduler."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


class JobState(str, Enum):
    """State of a scheduled job."""
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    PREPARING = "preparing"
    PRINTING = "printing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledJob:
    """A job in the farm schedule."""

    job: PrintJob
    state: JobState = JobState.QUEUED
    assigned_printer: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    progress_percent: float = 0.0
    error_message: Optional[str] = None

    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job.job_id,
            "name": self.job.name,
            "state": self.state.value,
            "assigned_printer": self.assigned_printer,
            "scheduled_start": self.scheduled_start.isoformat() if self.scheduled_start else None,
            "actual_start": self.actual_start.isoformat() if self.actual_start else None,
            "progress_percent": self.progress_percent,
            "depends_on": self.depends_on,
        }


@dataclass
class ScheduleSlot:
    """A time slot in a printer's schedule."""

    printer_id: str
    job_id: str
    start_time: datetime
    end_time: datetime
    confirmed: bool = False


class FarmScheduler:
    """
    Farm-wide job scheduler.

    Features:
    - Priority-based scheduling
    - Job dependencies
    - Automatic rescheduling on failures
    - Real-time schedule updates
    - Printer availability tracking
    """

    def __init__(
        self,
        optimizer: Optional[FarmOptimizer] = None,
        reschedule_interval_seconds: float = 300.0,
    ):
        self.optimizer = optimizer or get_farm_optimizer()
        self.reschedule_interval = reschedule_interval_seconds

        self._status = ScheduleStatus.STOPPED
        self._jobs: Dict[str, ScheduledJob] = {}
        self._schedule: Dict[str, List[ScheduleSlot]] = {}  # printer_id -> slots
        self._scheduler_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_job_start: List[Callable[[ScheduledJob], Awaitable[None]]] = []
        self._on_job_complete: List[Callable[[ScheduledJob], Awaitable[None]]] = []
        self._on_job_fail: List[Callable[[ScheduledJob], Awaitable[None]]] = []

    @property
    def status(self) -> ScheduleStatus:
        """Get scheduler status."""
        return self._status

    def on_job_start(self, callback: Callable[[ScheduledJob], Awaitable[None]]) -> None:
        """Register callback for job start."""
        self._on_job_start.append(callback)

    def on_job_complete(self, callback: Callable[[ScheduledJob], Awaitable[None]]) -> None:
        """Register callback for job completion."""
        self._on_job_complete.append(callback)

    def on_job_fail(self, callback: Callable[[ScheduledJob], Awaitable[None]]) -> None:
        """Register callback for job failure."""
        self._on_job_fail.append(callback)

    async def start(self) -> None:
        """Start the scheduler."""
        if self._status == ScheduleStatus.RUNNING:
            return

        self._status = ScheduleStatus.RUNNING
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Farm scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._status = ScheduleStatus.STOPPED

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("Farm scheduler stopped")

    async def pause(self) -> None:
        """Pause scheduling (won't start new jobs)."""
        self._status = ScheduleStatus.PAUSED
        logger.info("Farm scheduler paused")

    async def resume(self) -> None:
        """Resume scheduling."""
        if self._status == ScheduleStatus.PAUSED:
            self._status = ScheduleStatus.RUNNING
            logger.info("Farm scheduler resumed")

    def add_job(
        self,
        job: PrintJob,
        depends_on: Optional[List[str]] = None,
    ) -> ScheduledJob:
        """Add a job to the schedule."""
        scheduled = ScheduledJob(
            job=job,
            depends_on=depends_on or [],
        )
        self._jobs[job.job_id] = scheduled

        # Update reverse dependencies
        for dep_id in scheduled.depends_on:
            if dep_id in self._jobs:
                self._jobs[dep_id].blocks.append(job.job_id)

        logger.info(f"Added job to schedule: {job.job_id}")
        return scheduled

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the schedule."""
        if job_id not in self._jobs:
            return False

        scheduled = self._jobs[job_id]

        # Only allow removing queued jobs
        if scheduled.state not in [JobState.QUEUED, JobState.SCHEDULED]:
            return False

        # Update dependencies
        for dep_id in scheduled.depends_on:
            if dep_id in self._jobs:
                self._jobs[dep_id].blocks.remove(job_id)

        del self._jobs[job_id]

        # Remove from schedule
        for slots in self._schedule.values():
            self._schedule = {
                pid: [s for s in slots if s.job_id != job_id]
                for pid, slots in self._schedule.items()
            }

        logger.info(f"Removed job from schedule: {job_id}")
        return True

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get a scheduled job."""
        return self._jobs.get(job_id)

    def get_all_jobs(self, state: Optional[JobState] = None) -> List[ScheduledJob]:
        """Get all jobs, optionally filtered by state."""
        if state:
            return [j for j in self._jobs.values() if j.state == state]
        return list(self._jobs.values())

    def get_queue(self) -> List[ScheduledJob]:
        """Get jobs in queue (not yet scheduled)."""
        return self.get_all_jobs(JobState.QUEUED)

    def get_printer_schedule(self, printer_id: str) -> List[ScheduleSlot]:
        """Get schedule for a specific printer."""
        return self._schedule.get(printer_id, [])

    async def reschedule(self) -> int:
        """
        Reschedule all pending jobs.

        Returns number of jobs scheduled.
        """
        # Get jobs that need scheduling
        pending_jobs = [
            j.job for j in self._jobs.values()
            if j.state in [JobState.QUEUED, JobState.SCHEDULED]
            and self._dependencies_met(j)
        ]

        if not pending_jobs:
            return 0

        # Run optimization
        result = self.optimizer.optimize(
            jobs=pending_jobs,
            goal=OptimizationGoal.BALANCED,
        )

        # Apply assignments
        scheduled_count = 0
        for assignment in result.assignments:
            job_id = assignment.job_id
            if job_id in self._jobs:
                scheduled = self._jobs[job_id]
                scheduled.assigned_printer = assignment.printer_id
                scheduled.scheduled_start = assignment.start_time
                scheduled.state = JobState.SCHEDULED

                # Add to printer schedule
                if assignment.printer_id not in self._schedule:
                    self._schedule[assignment.printer_id] = []

                self._schedule[assignment.printer_id].append(ScheduleSlot(
                    printer_id=assignment.printer_id,
                    job_id=job_id,
                    start_time=assignment.start_time,
                    end_time=assignment.end_time,
                ))

                scheduled_count += 1

        logger.info(f"Rescheduled {scheduled_count} jobs")
        return scheduled_count

    def _dependencies_met(self, job: ScheduledJob) -> bool:
        """Check if all job dependencies are met."""
        for dep_id in job.depends_on:
            dep = self._jobs.get(dep_id)
            if not dep or dep.state != JobState.COMPLETED:
                return False
        return True

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._status != ScheduleStatus.STOPPED:
            try:
                if self._status == ScheduleStatus.RUNNING:
                    # Check for jobs ready to start
                    await self._check_ready_jobs()

                    # Periodic rescheduling
                    await self.reschedule()

                await asyncio.sleep(self.reschedule_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(10)

    async def _check_ready_jobs(self) -> None:
        """Check for jobs ready to start and trigger them."""
        now = datetime.utcnow()

        for job in self._jobs.values():
            if (
                job.state == JobState.SCHEDULED and
                job.scheduled_start and
                job.scheduled_start <= now and
                self._dependencies_met(job)
            ):
                await self._start_job(job)

    async def _start_job(self, job: ScheduledJob) -> None:
        """Start a scheduled job."""
        job.state = JobState.PREPARING
        job.actual_start = datetime.utcnow()

        logger.info(f"Starting job {job.job.job_id} on {job.assigned_printer}")

        # Notify callbacks
        for callback in self._on_job_start:
            try:
                await callback(job)
            except Exception as e:
                logger.error(f"Job start callback error: {e}")

        job.state = JobState.PRINTING

    async def mark_job_complete(self, job_id: str) -> None:
        """Mark a job as completed."""
        job = self._jobs.get(job_id)
        if not job:
            return

        job.state = JobState.COMPLETED
        job.actual_end = datetime.utcnow()
        job.progress_percent = 100.0

        logger.info(f"Job completed: {job_id}")

        # Notify callbacks
        for callback in self._on_job_complete:
            try:
                await callback(job)
            except Exception as e:
                logger.error(f"Job complete callback error: {e}")

        # Trigger rescheduling for dependent jobs
        if job.blocks:
            await self.reschedule()

    async def mark_job_failed(self, job_id: str, error: str) -> None:
        """Mark a job as failed."""
        job = self._jobs.get(job_id)
        if not job:
            return

        job.state = JobState.FAILED
        job.actual_end = datetime.utcnow()
        job.error_message = error

        logger.error(f"Job failed: {job_id} - {error}")

        # Notify callbacks
        for callback in self._on_job_fail:
            try:
                await callback(job)
            except Exception as e:
                logger.error(f"Job fail callback error: {e}")

    def update_progress(self, job_id: str, progress: float) -> None:
        """Update job progress."""
        job = self._jobs.get(job_id)
        if job and job.state == JobState.PRINTING:
            job.progress_percent = min(100.0, max(0.0, progress))

    def get_schedule_summary(self) -> dict:
        """Get summary of the current schedule."""
        by_state = {state: 0 for state in JobState}
        for job in self._jobs.values():
            by_state[job.state] += 1

        return {
            "status": self._status.value,
            "total_jobs": len(self._jobs),
            "by_state": {k.value: v for k, v in by_state.items()},
            "printers_scheduled": len(self._schedule),
            "queued": by_state[JobState.QUEUED],
            "printing": by_state[JobState.PRINTING],
            "completed": by_state[JobState.COMPLETED],
            "failed": by_state[JobState.FAILED],
        }


# Global scheduler instance
_scheduler: Optional[FarmScheduler] = None


def get_farm_scheduler() -> FarmScheduler:
    """Get the global farm scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = FarmScheduler()
    return _scheduler


async def init_farm_scheduler(**kwargs) -> FarmScheduler:
    """Initialize and start the farm scheduler."""
    global _scheduler
    _scheduler = FarmScheduler(**kwargs)
    await _scheduler.start()
    return _scheduler
