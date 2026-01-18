"""Print job queue management.

P4.4: Print Queue Manager

Features:
- Add/remove/reorder jobs
- Priority levels
- Dependencies between jobs
- Persistent storage (SQLite)
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
from uuid import uuid4

from src.utils import get_logger

logger = get_logger("queue.job_queue")


class JobStatus(str, Enum):
    """Status of a print job."""
    PENDING = "pending"  # Waiting in queue
    READY = "ready"  # Dependencies met, ready to print
    PRINTING = "printing"  # Currently printing
    PAUSED = "paused"  # Print paused
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Print failed
    CANCELLED = "cancelled"  # Cancelled by user


class JobPriority(str, Enum):
    """Priority level for print jobs."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

    @property
    def value_int(self) -> int:
        """Get integer value for sorting."""
        return {
            JobPriority.LOW: 0,
            JobPriority.NORMAL: 1,
            JobPriority.HIGH: 2,
            JobPriority.URGENT: 3,
        }[self]


@dataclass
class PrintJob:
    """A print job in the queue."""

    id: str
    name: str
    file_path: str
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL

    # Material configuration
    material: str = "pla"
    color: str = "white"
    ams_slot: Optional[int] = None

    # Print settings
    quality: str = "normal"  # draft, normal, fine
    infill_percent: int = 15
    supports_enabled: bool = False

    # Timing
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    estimated_time_seconds: int = 0

    # Progress
    progress_percent: float = 0
    current_layer: int = 0
    total_layers: int = 0

    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Job IDs this depends on
    notes: str = ""

    def __post_init__(self):
        """Ensure proper types after initialization."""
        if isinstance(self.status, str):
            self.status = JobStatus(self.status)
        if isinstance(self.priority, str):
            self.priority = JobPriority(self.priority)

    @property
    def is_active(self) -> bool:
        """Check if job is currently active."""
        return self.status in [JobStatus.PRINTING, JobStatus.PAUSED]

    @property
    def is_complete(self) -> bool:
        """Check if job has finished (success or failure)."""
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]

    @property
    def can_start(self) -> bool:
        """Check if job can be started."""
        return self.status in [JobStatus.PENDING, JobStatus.READY]

    def start(self) -> None:
        """Mark job as started."""
        self.status = JobStatus.PRINTING
        self.started_at = datetime.now().isoformat()
        self.progress_percent = 0

    def complete(self, success: bool = True) -> None:
        """Mark job as completed."""
        self.status = JobStatus.COMPLETED if success else JobStatus.FAILED
        self.completed_at = datetime.now().isoformat()
        if success:
            self.progress_percent = 100

    def cancel(self) -> None:
        """Cancel the job."""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.now().isoformat()

    def pause(self) -> None:
        """Pause the job."""
        if self.status == JobStatus.PRINTING:
            self.status = JobStatus.PAUSED

    def resume(self) -> None:
        """Resume a paused job."""
        if self.status == JobStatus.PAUSED:
            self.status = JobStatus.PRINTING

    def update_progress(self, percent: float, current_layer: int = None, total_layers: int = None) -> None:
        """Update job progress."""
        self.progress_percent = min(100, max(0, percent))
        if current_layer is not None:
            self.current_layer = current_layer
        if total_layers is not None:
            self.total_layers = total_layers

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        d = asdict(self)
        d["status"] = self.status.value
        d["priority"] = self.priority.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "PrintJob":
        """Create from dictionary."""
        return cls(**data)


class PrintQueue:
    """
    Manages a queue of print jobs with persistence.

    Features:
    - Priority-based ordering
    - Job dependencies
    - SQLite persistence
    - Queue manipulation (add, remove, reorder)
    """

    def __init__(self, data_file: Optional[Path] = None):
        """Initialize the print queue."""
        self.data_file = data_file or Path("data/print_queue.json")
        self.jobs: Dict[str, PrintJob] = {}
        self.order: List[str] = []  # Job IDs in queue order
        self._load()

    def _load(self) -> None:
        """Load queue from disk."""
        if self.data_file.exists():
            try:
                with open(self.data_file) as f:
                    data = json.load(f)
                self.jobs = {
                    k: PrintJob.from_dict(v) for k, v in data.get("jobs", {}).items()
                }
                self.order = data.get("order", [])
                # Clean up order (remove any invalid job IDs)
                self.order = [jid for jid in self.order if jid in self.jobs]
                logger.info(f"Loaded {len(self.jobs)} jobs from queue")
            except Exception as e:
                logger.error(f"Failed to load queue: {e}")
                self.jobs = {}
                self.order = []

    def _save(self) -> None:
        """Save queue to disk."""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "jobs": {k: v.to_dict() for k, v in self.jobs.items()},
            "order": self.order,
        }
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)
        logger.debug("Queue saved")

    def add_job(
        self,
        file_path: str,
        name: Optional[str] = None,
        priority: JobPriority = JobPriority.NORMAL,
        material: str = "pla",
        color: str = "white",
        depends_on: Optional[List[str]] = None,
        **kwargs,
    ) -> PrintJob:
        """
        Add a new job to the queue.

        Args:
            file_path: Path to the model file
            name: Job name (defaults to filename)
            priority: Job priority level
            material: Material type
            color: Filament color
            depends_on: List of job IDs this depends on
            **kwargs: Additional job settings

        Returns:
            The created PrintJob
        """
        path = Path(file_path)
        job_name = name or path.stem

        job = PrintJob(
            id=str(uuid4())[:8],
            name=job_name,
            file_path=str(path),
            priority=priority,
            material=material,
            color=color,
            depends_on=depends_on or [],
            **kwargs,
        )

        self.jobs[job.id] = job
        self._insert_by_priority(job.id)
        self._save()

        logger.info(f"Added job {job.id}: {job_name} (priority: {priority.value})")
        return job

    def _insert_by_priority(self, job_id: str) -> None:
        """Insert job in correct position based on priority."""
        job = self.jobs[job_id]
        insert_idx = len(self.order)

        for i, existing_id in enumerate(self.order):
            existing = self.jobs[existing_id]
            # Higher priority jobs go first
            if job.priority.value_int > existing.priority.value_int:
                insert_idx = i
                break

        self.order.insert(insert_idx, job_id)

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the queue."""
        if job_id not in self.jobs:
            return False

        job = self.jobs[job_id]
        if job.is_active:
            logger.warning(f"Cannot remove active job {job_id}")
            return False

        del self.jobs[job_id]
        if job_id in self.order:
            self.order.remove(job_id)

        # Remove from dependencies
        for other_job in self.jobs.values():
            if job_id in other_job.depends_on:
                other_job.depends_on.remove(job_id)

        self._save()
        logger.info(f"Removed job {job_id}")
        return True

    def get_job(self, job_id: str) -> Optional[PrintJob]:
        """Get a job by ID."""
        return self.jobs.get(job_id)

    def get_next_job(self) -> Optional[PrintJob]:
        """Get the next job ready to print."""
        for job_id in self.order:
            job = self.jobs[job_id]
            if job.can_start and self._dependencies_met(job):
                job.status = JobStatus.READY
                return job
        return None

    def _dependencies_met(self, job: PrintJob) -> bool:
        """Check if all dependencies are completed."""
        for dep_id in job.depends_on:
            dep = self.jobs.get(dep_id)
            if dep and dep.status != JobStatus.COMPLETED:
                return False
        return True

    def move_to_top(self, job_id: str) -> bool:
        """Move a job to the top of its priority group."""
        if job_id not in self.jobs:
            return False

        job = self.jobs[job_id]
        if job.is_active or job.is_complete:
            return False

        self.order.remove(job_id)
        # Find first job with same or lower priority
        for i, existing_id in enumerate(self.order):
            existing = self.jobs[existing_id]
            if job.priority.value_int >= existing.priority.value_int:
                self.order.insert(i, job_id)
                break
        else:
            self.order.append(job_id)

        self._save()
        return True

    def move_to_bottom(self, job_id: str) -> bool:
        """Move a job to the bottom of its priority group."""
        if job_id not in self.jobs:
            return False

        job = self.jobs[job_id]
        if job.is_active or job.is_complete:
            return False

        self.order.remove(job_id)
        # Find last job with same or higher priority
        insert_idx = len(self.order)
        for i in range(len(self.order) - 1, -1, -1):
            existing = self.jobs[self.order[i]]
            if job.priority.value_int <= existing.priority.value_int:
                insert_idx = i + 1
                break

        self.order.insert(insert_idx, job_id)
        self._save()
        return True

    def set_priority(self, job_id: str, priority: JobPriority) -> bool:
        """Change a job's priority."""
        if job_id not in self.jobs:
            return False

        job = self.jobs[job_id]
        if job.is_active or job.is_complete:
            return False

        job.priority = priority
        self.order.remove(job_id)
        self._insert_by_priority(job_id)
        self._save()
        return True

    def get_pending_jobs(self) -> List[PrintJob]:
        """Get all pending (not started) jobs in order."""
        return [
            self.jobs[jid] for jid in self.order
            if self.jobs[jid].status in [JobStatus.PENDING, JobStatus.READY]
        ]

    def get_active_job(self) -> Optional[PrintJob]:
        """Get the currently printing job."""
        for job in self.jobs.values():
            if job.status == JobStatus.PRINTING:
                return job
        return None

    def get_completed_jobs(self, limit: int = 10) -> List[PrintJob]:
        """Get recently completed jobs."""
        completed = [j for j in self.jobs.values() if j.is_complete]
        # Sort by completion time, most recent first
        completed.sort(
            key=lambda j: j.completed_at or "",
            reverse=True,
        )
        return completed[:limit]

    def clear_completed(self) -> int:
        """Remove all completed jobs from queue."""
        to_remove = [jid for jid, job in self.jobs.items() if job.is_complete]
        for jid in to_remove:
            del self.jobs[jid]
            if jid in self.order:
                self.order.remove(jid)
        self._save()
        return len(to_remove)

    def update_job(self, job_id: str, **kwargs) -> bool:
        """Update job properties."""
        job = self.jobs.get(job_id)
        if job is None:
            return False

        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)

        self._save()
        return True

    def list_all(self) -> List[PrintJob]:
        """List all jobs in queue order."""
        return [self.jobs[jid] for jid in self.order if jid in self.jobs]

    def count(self) -> dict:
        """Get job counts by status."""
        counts = {status: 0 for status in JobStatus}
        for job in self.jobs.values():
            counts[job.status] += 1
        return counts

    def __len__(self) -> int:
        """Get total number of jobs."""
        return len(self.jobs)
