"""Print job repository for job-related database operations."""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PrintJob, JobStatus, JobPriority
from src.db.repositories.base import BaseRepository


class PrintJobRepository(BaseRepository[PrintJob]):
    """Repository for PrintJob entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, PrintJob)

    async def get_queue(
        self,
        organization_id: str,
        printer_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[PrintJob]:
        """Get queued jobs ordered by priority and queue time."""
        query = select(PrintJob).where(
            PrintJob.organization_id == organization_id,
            PrintJob.status.in_([JobStatus.PENDING, JobStatus.QUEUED])
        )

        if printer_id:
            query = query.where(PrintJob.printer_id == printer_id)

        # Order by priority (urgent first) then queue time
        query = query.order_by(
            PrintJob.priority.desc(),
            PrintJob.queued_at.asc()
        ).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_jobs(
        self,
        organization_id: str,
        printer_id: Optional[str] = None
    ) -> List[PrintJob]:
        """Get currently active (printing/paused) jobs."""
        query = select(PrintJob).where(
            PrintJob.organization_id == organization_id,
            PrintJob.status.in_([JobStatus.PRINTING, JobStatus.PAUSED, JobStatus.PREPARING])
        )

        if printer_id:
            query = query.where(PrintJob.printer_id == printer_id)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_printer(
        self,
        printer_id: str,
        status: Optional[JobStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[PrintJob]:
        """Get jobs for a specific printer."""
        query = select(PrintJob).where(PrintJob.printer_id == printer_id)

        if status:
            query = query.where(PrintJob.status == status)

        query = query.order_by(PrintJob.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent(
        self,
        organization_id: str,
        days: int = 7,
        limit: int = 100
    ) -> List[PrintJob]:
        """Get recent jobs from the last N days."""
        threshold = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            select(PrintJob)
            .where(
                PrintJob.organization_id == organization_id,
                PrintJob.created_at > threshold
            )
            .order_by(PrintJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_job(
        self,
        organization_id: str,
        user_id: str,
        model_id: str,
        name: str,
        priority: JobPriority = JobPriority.NORMAL,
        printer_id: Optional[str] = None,
        estimated_duration_minutes: Optional[int] = None,
        estimated_material_grams: Optional[float] = None,
        settings: Optional[dict] = None
    ) -> PrintJob:
        """Create a new print job."""
        import json

        job = PrintJob(
            organization_id=organization_id,
            user_id=user_id,
            model_id=model_id,
            name=name,
            priority=priority,
            printer_id=printer_id,
            estimated_duration_minutes=estimated_duration_minutes,
            estimated_material_grams=estimated_material_grams,
            settings=json.dumps(settings) if settings else None,
            queued_at=datetime.utcnow() if printer_id else None
        )
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def assign_to_printer(
        self,
        job_id: str,
        printer_id: str,
        queue_position: int
    ) -> Optional[PrintJob]:
        """Assign job to a printer and set queue position."""
        return await self.update(
            job_id,
            printer_id=printer_id,
            queue_position=queue_position,
            queued_at=datetime.utcnow(),
            status=JobStatus.QUEUED
        )

    async def start_job(self, job_id: str) -> Optional[PrintJob]:
        """Mark job as started."""
        return await self.update(
            job_id,
            status=JobStatus.PRINTING,
            started_at=datetime.utcnow()
        )

    async def update_progress(
        self,
        job_id: str,
        progress: float,
        current_layer: Optional[int] = None,
        total_layers: Optional[int] = None
    ) -> None:
        """Update job progress."""
        updates = {"progress_percent": progress}
        if current_layer is not None:
            updates["current_layer"] = current_layer
        if total_layers is not None:
            updates["total_layers"] = total_layers
        await self.update(job_id, **updates)

    async def complete_job(
        self,
        job_id: str,
        success: bool,
        actual_material_grams: Optional[float] = None,
        material_cost: Optional[float] = None,
        failure_reason: Optional[str] = None,
        failure_detected_by: Optional[str] = None
    ) -> Optional[PrintJob]:
        """Mark job as completed or failed."""
        job = await self.get_by_id(job_id)
        if not job:
            return None

        now = datetime.utcnow()
        actual_duration = None
        if job.started_at:
            actual_duration = int((now - job.started_at).total_seconds() / 60)

        return await self.update(
            job_id,
            status=JobStatus.COMPLETED if success else JobStatus.FAILED,
            completed_at=now,
            progress_percent=100.0 if success else job.progress_percent,
            actual_duration_minutes=actual_duration,
            actual_material_grams=actual_material_grams,
            material_cost=material_cost,
            failure_reason=failure_reason,
            failure_detected_by=failure_detected_by
        )

    async def cancel_job(self, job_id: str) -> Optional[PrintJob]:
        """Cancel a job."""
        return await self.update(
            job_id,
            status=JobStatus.CANCELLED,
            completed_at=datetime.utcnow()
        )

    async def pause_job(self, job_id: str) -> Optional[PrintJob]:
        """Pause a job."""
        return await self.update(job_id, status=JobStatus.PAUSED)

    async def resume_job(self, job_id: str) -> Optional[PrintJob]:
        """Resume a paused job."""
        return await self.update(job_id, status=JobStatus.PRINTING)

    async def get_stats(
        self,
        organization_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict:
        """Get job statistics for an organization."""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Total jobs
        total = await self.session.execute(
            select(func.count(PrintJob.id)).where(
                PrintJob.organization_id == organization_id,
                PrintJob.created_at >= start_date,
                PrintJob.created_at <= end_date
            )
        )

        # Completed jobs
        completed = await self.session.execute(
            select(func.count(PrintJob.id)).where(
                PrintJob.organization_id == organization_id,
                PrintJob.status == JobStatus.COMPLETED,
                PrintJob.completed_at >= start_date,
                PrintJob.completed_at <= end_date
            )
        )

        # Failed jobs
        failed = await self.session.execute(
            select(func.count(PrintJob.id)).where(
                PrintJob.organization_id == organization_id,
                PrintJob.status == JobStatus.FAILED,
                PrintJob.completed_at >= start_date,
                PrintJob.completed_at <= end_date
            )
        )

        # Total print time
        print_time = await self.session.execute(
            select(func.sum(PrintJob.actual_duration_minutes)).where(
                PrintJob.organization_id == organization_id,
                PrintJob.status == JobStatus.COMPLETED,
                PrintJob.completed_at >= start_date,
                PrintJob.completed_at <= end_date
            )
        )

        # Total material used
        material = await self.session.execute(
            select(func.sum(PrintJob.actual_material_grams)).where(
                PrintJob.organization_id == organization_id,
                PrintJob.status == JobStatus.COMPLETED,
                PrintJob.completed_at >= start_date,
                PrintJob.completed_at <= end_date
            )
        )

        total_count = total.scalar() or 0
        completed_count = completed.scalar() or 0
        failed_count = failed.scalar() or 0

        return {
            "total_jobs": total_count,
            "completed_jobs": completed_count,
            "failed_jobs": failed_count,
            "success_rate": completed_count / total_count if total_count > 0 else 0,
            "total_print_time_minutes": print_time.scalar() or 0,
            "total_material_grams": material.scalar() or 0
        }
