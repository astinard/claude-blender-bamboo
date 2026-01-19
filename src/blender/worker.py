"""Blender job worker with queue support.

Executes Blender scripts in isolated subprocesses with timeout handling,
resource limits, and comprehensive job tracking.

Note: Uses asyncio.create_subprocess_exec (not shell) to avoid command injection.
"""

import asyncio
import json
import os
import tempfile
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Awaitable, Dict, Any
from uuid import uuid4

from src.utils import get_logger

logger = get_logger("blender.worker")


class JobStatus(str, Enum):
    """Blender job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class BlenderJob:
    """Represents a Blender job."""
    id: str = field(default_factory=lambda: str(uuid4()))
    script_path: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 300.0
    priority: int = 0
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    return_code: Optional[int] = None


@dataclass
class BlenderResult:
    """Result of a Blender job execution."""
    success: bool
    job_id: str
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    duration_seconds: float = 0.0
    output_files: list = field(default_factory=list)
    error: Optional[str] = None


class BlenderTimeoutError(Exception):
    """Raised when a Blender job times out."""
    pass


class BlenderWorker:
    """Worker for executing Blender jobs with queue support."""

    BLENDER_PATHS = [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/usr/bin/blender",
        "/snap/bin/blender",
        "blender",
    ]

    def __init__(
        self,
        blender_path: Optional[str] = None,
        max_concurrent: int = 2,
        default_timeout: float = 300.0,
        on_job_complete: Optional[Callable[[BlenderJob], Awaitable[None]]] = None
    ):
        self.blender_path = blender_path or self._find_blender()
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.on_job_complete = on_job_complete

        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._jobs: Dict[str, BlenderJob] = {}
        self._active_jobs: int = 0
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

        self.total_jobs_processed = 0
        self.total_jobs_failed = 0
        self.total_execution_time = 0.0

        logger.info(f"BlenderWorker initialized: {self.blender_path}")

    def _find_blender(self) -> str:
        """Find the Blender executable."""
        for path in self.BLENDER_PATHS:
            if os.path.exists(path):
                return path
            result = shutil.which(path)
            if result:
                return result
        raise FileNotFoundError("Blender not found")

    async def start(self):
        """Start the worker loop."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Blender worker started")

    async def stop(self):
        """Stop the worker loop."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Blender worker stopped")

    async def submit_job(
        self,
        script_path: str,
        args: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        priority: int = 0
    ) -> BlenderJob:
        """Submit a job to the queue."""
        job = BlenderJob(
            script_path=script_path,
            args=args or {},
            timeout=timeout or self.default_timeout,
            priority=priority
        )
        self._jobs[job.id] = job
        await self._queue.put((-priority, job.created_at.timestamp(), job.id))
        logger.info(f"Job {job.id} submitted: {script_path}")
        return job

    async def execute_script(
        self,
        script_path: str,
        args: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> BlenderResult:
        """Execute a Blender script directly."""
        job = BlenderJob(
            script_path=script_path,
            args=args or {},
            timeout=timeout or self.default_timeout
        )
        return await self._execute_job(job)

    async def _worker_loop(self):
        """Main worker loop."""
        while self._running:
            try:
                priority, timestamp, job_id = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                job = self._jobs.get(job_id)
                if not job or job.status == JobStatus.CANCELLED:
                    continue

                while self._active_jobs >= self.max_concurrent:
                    await asyncio.sleep(0.1)

                asyncio.create_task(self._process_job(job))
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")

    async def _process_job(self, job: BlenderJob):
        """Process a single job."""
        self._active_jobs += 1
        try:
            result = await self._execute_job(job)
            job.status = JobStatus.COMPLETED if result.success else JobStatus.FAILED
            if not result.success:
                self.total_jobs_failed += 1
            job.result = {"output_files": result.output_files, "duration": result.duration_seconds}
            self.total_jobs_processed += 1
            self.total_execution_time += result.duration_seconds
            if self.on_job_complete:
                await self.on_job_complete(job)
        except BlenderTimeoutError:
            job.status = JobStatus.TIMEOUT
            job.error = f"Timed out after {job.timeout}s"
            self.total_jobs_failed += 1
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            self.total_jobs_failed += 1
        finally:
            job.completed_at = datetime.utcnow()
            self._active_jobs -= 1

    async def _execute_job(self, job: BlenderJob) -> BlenderResult:
        """Execute a Blender job in subprocess (uses exec, not shell)."""
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()

        args_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(job.args, f)
                args_file = f.name

            # Using create_subprocess_exec (not shell) - safe from injection
            cmd = [self.blender_path, "--background", "--python", job.script_path, "--", args_file]

            start_time = datetime.utcnow()
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=job.timeout)
                duration = (datetime.utcnow() - start_time).total_seconds()

                job.stdout = stdout.decode('utf-8', errors='replace')
                job.stderr = stderr.decode('utf-8', errors='replace')
                job.return_code = proc.returncode

                output_files = self._parse_output_files(job.stdout)

                return BlenderResult(
                    success=proc.returncode == 0,
                    job_id=job.id,
                    stdout=job.stdout,
                    stderr=job.stderr,
                    return_code=proc.returncode,
                    duration_seconds=duration,
                    output_files=output_files,
                    error=job.stderr if proc.returncode != 0 else None
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise BlenderTimeoutError(f"Job {job.id} timed out")
        finally:
            if args_file and os.path.exists(args_file):
                os.remove(args_file)

    def _parse_output_files(self, stdout: str) -> list:
        """Parse output files from stdout (OUTPUT_FILE: /path)."""
        files = []
        for line in stdout.split('\n'):
            if line.startswith('OUTPUT_FILE:'):
                path = line.split(':', 1)[1].strip()
                if os.path.exists(path):
                    files.append(path)
        return files

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    def get_metrics(self) -> dict:
        return {
            "queue_size": self.queue_size,
            "active_jobs": self._active_jobs,
            "total_processed": self.total_jobs_processed,
            "total_failed": self.total_jobs_failed,
            "avg_execution_time": (
                round(self.total_execution_time / self.total_jobs_processed, 2)
                if self.total_jobs_processed > 0 else 0
            )
        }


_worker: Optional[BlenderWorker] = None


def get_blender_worker() -> BlenderWorker:
    global _worker
    if _worker is None:
        _worker = BlenderWorker()
    return _worker


async def init_blender_worker(**kwargs) -> BlenderWorker:
    global _worker
    _worker = BlenderWorker(**kwargs)
    await _worker.start()
    return _worker
