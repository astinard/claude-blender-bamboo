"""Queue scheduler for automated print processing.

Handles queue execution, job sequencing, and printer coordination.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, List
from datetime import datetime

from src.queue.job_queue import PrintQueue, PrintJob, JobStatus
from src.utils import get_logger

logger = get_logger("queue.scheduler")


class SchedulingStrategy(str, Enum):
    """Strategy for scheduling print jobs."""
    FIFO = "fifo"  # First in, first out (respects priority)
    SHORTEST_FIRST = "shortest_first"  # Shortest estimated time first
    MATERIAL_BATCH = "material_batch"  # Group by material to reduce changes


@dataclass
class SchedulerConfig:
    """Configuration for the queue scheduler."""
    strategy: SchedulingStrategy = SchedulingStrategy.FIFO
    auto_start_next: bool = True  # Start next job when one completes
    pause_on_failure: bool = True  # Pause queue if a job fails
    max_retries: int = 1  # Max retries for failed jobs
    mock_mode: bool = False  # For testing without printer


class QueueScheduler:
    """
    Schedules and executes print jobs from the queue.

    Coordinates between the queue and printer to:
    - Start jobs automatically or manually
    - Handle job completion and failure
    - Support different scheduling strategies
    """

    def __init__(
        self,
        queue: PrintQueue,
        config: Optional[SchedulerConfig] = None,
        on_job_start: Optional[Callable[[PrintJob], None]] = None,
        on_job_complete: Optional[Callable[[PrintJob], None]] = None,
        on_job_failed: Optional[Callable[[PrintJob, str], None]] = None,
    ):
        """
        Initialize the scheduler.

        Args:
            queue: The print queue to schedule from
            config: Scheduler configuration
            on_job_start: Callback when a job starts
            on_job_complete: Callback when a job completes
            on_job_failed: Callback when a job fails
        """
        self.queue = queue
        self.config = config or SchedulerConfig()
        self.on_job_start = on_job_start
        self.on_job_complete = on_job_complete
        self.on_job_failed = on_job_failed

        self._running = False
        self._paused = False
        self._current_job: Optional[PrintJob] = None

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    @property
    def is_paused(self) -> bool:
        """Check if scheduler is paused."""
        return self._paused

    @property
    def current_job(self) -> Optional[PrintJob]:
        """Get the currently printing job."""
        return self._current_job

    def start(self) -> Optional[PrintJob]:
        """
        Start processing the queue.

        Returns:
            The job that was started, or None if queue is empty
        """
        if self._running:
            logger.warning("Scheduler already running")
            return self._current_job

        self._running = True
        self._paused = False

        return self._start_next_job()

    def stop(self) -> None:
        """Stop the scheduler (doesn't cancel current job)."""
        self._running = False
        logger.info("Scheduler stopped")

    def pause(self) -> None:
        """Pause the scheduler."""
        self._paused = True
        if self._current_job:
            self._current_job.pause()
            self.queue._save()
        logger.info("Scheduler paused")

    def resume(self) -> None:
        """Resume the scheduler."""
        self._paused = False
        if self._current_job and self._current_job.status == JobStatus.PAUSED:
            self._current_job.resume()
            self.queue._save()
        logger.info("Scheduler resumed")

    def _start_next_job(self) -> Optional[PrintJob]:
        """Start the next job in the queue."""
        if self._paused:
            return None

        job = self._select_next_job()
        if job is None:
            logger.info("No jobs ready to print")
            self._running = False
            return None

        self._current_job = job
        job.start()
        self.queue._save()

        logger.info(f"Starting job {job.id}: {job.name}")

        if self.on_job_start:
            self.on_job_start(job)

        if self.config.mock_mode:
            # In mock mode, simulate completion
            self._simulate_job_completion(job)

        return job

    def _select_next_job(self) -> Optional[PrintJob]:
        """Select the next job based on scheduling strategy."""
        if self.config.strategy == SchedulingStrategy.FIFO:
            return self.queue.get_next_job()

        elif self.config.strategy == SchedulingStrategy.SHORTEST_FIRST:
            pending = self.queue.get_pending_jobs()
            if not pending:
                return None
            # Sort by estimated time
            pending.sort(key=lambda j: j.estimated_time_seconds)
            return pending[0]

        elif self.config.strategy == SchedulingStrategy.MATERIAL_BATCH:
            pending = self.queue.get_pending_jobs()
            if not pending:
                return None
            # Group by material, prefer larger groups
            materials = {}
            for job in pending:
                mat = job.material
                if mat not in materials:
                    materials[mat] = []
                materials[mat].append(job)
            # Get material with most jobs
            best_mat = max(materials.keys(), key=lambda m: len(materials[m]))
            return materials[best_mat][0]

        return self.queue.get_next_job()

    def _simulate_job_completion(self, job: PrintJob) -> None:
        """Simulate job completion in mock mode."""
        job.update_progress(100)
        self.job_completed(job.id, success=True)

    def job_completed(self, job_id: str, success: bool = True, error_message: str = "") -> None:
        """
        Mark a job as completed.

        Args:
            job_id: ID of the completed job
            success: Whether the job succeeded
            error_message: Error message if failed
        """
        job = self.queue.get_job(job_id)
        if job is None:
            logger.warning(f"Job {job_id} not found")
            return

        job.complete(success)
        self.queue._save()
        self._current_job = None

        if success:
            logger.info(f"Job {job_id} completed successfully")
            if self.on_job_complete:
                self.on_job_complete(job)
        else:
            logger.warning(f"Job {job_id} failed: {error_message}")
            if self.on_job_failed:
                self.on_job_failed(job, error_message)

            if self.config.pause_on_failure:
                self._paused = True
                logger.info("Queue paused due to failure")
                return

        # Start next job if auto-start enabled
        if self._running and self.config.auto_start_next and not self._paused:
            self._start_next_job()

    def job_progress(self, job_id: str, percent: float, layer: int = None, total_layers: int = None) -> None:
        """
        Update job progress.

        Args:
            job_id: ID of the job
            percent: Progress percentage (0-100)
            layer: Current layer number
            total_layers: Total layers
        """
        job = self.queue.get_job(job_id)
        if job:
            job.update_progress(percent, layer, total_layers)
            self.queue._save()

    def cancel_current(self) -> bool:
        """Cancel the currently printing job."""
        if self._current_job is None:
            return False

        self._current_job.cancel()
        self.queue._save()
        logger.info(f"Cancelled job {self._current_job.id}")

        self._current_job = None

        # Start next if running
        if self._running and not self._paused:
            self._start_next_job()

        return True

    def get_status(self) -> dict:
        """Get scheduler status."""
        counts = self.queue.count()

        return {
            "running": self._running,
            "paused": self._paused,
            "current_job": self._current_job.to_dict() if self._current_job else None,
            "strategy": self.config.strategy.value,
            "jobs_pending": counts[JobStatus.PENDING] + counts[JobStatus.READY],
            "jobs_completed": counts[JobStatus.COMPLETED],
            "jobs_failed": counts[JobStatus.FAILED],
            "total_jobs": len(self.queue),
        }

    def estimate_queue_time(self) -> int:
        """Estimate total time to complete all pending jobs."""
        pending = self.queue.get_pending_jobs()
        return sum(j.estimated_time_seconds for j in pending)

    def get_queue_summary(self) -> List[dict]:
        """Get summary of jobs in queue order."""
        result = []
        for job in self.queue.list_all():
            result.append({
                "id": job.id,
                "name": job.name,
                "status": job.status.value,
                "priority": job.priority.value,
                "material": job.material,
                "progress": job.progress_percent,
            })
        return result
