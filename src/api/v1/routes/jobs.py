"""Print job routes."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.repositories.jobs import PrintJobRepository
from src.db.models import JobStatus, JobPriority
from src.auth.middleware import CurrentUser, require_permission
from src.auth.rbac import Permission

router = APIRouter()


class JobCreate(BaseModel):
    model_id: str
    name: str
    printer_id: Optional[str] = None
    priority: JobPriority = JobPriority.NORMAL


class JobResponse(BaseModel):
    id: str
    name: str
    status: str
    priority: str
    progress_percent: float
    printer_id: Optional[str] = None
    estimated_duration_minutes: Optional[int] = None
    created_at: str


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    current_user: CurrentUser,
    status_filter: Optional[JobStatus] = None,
    printer_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List print jobs."""
    repo = PrintJobRepository(db)
    jobs = await repo.get_all(
        organization_id=current_user.org_id,
        status=status_filter,
        printer_id=printer_id
    )
    return [JobResponse(**j.to_dict()) for j in jobs]


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: JobCreate,
    current_user: CurrentUser = Depends(require_permission(Permission.JOBS_CREATE)),
    db: AsyncSession = Depends(get_db)
):
    """Create a new print job."""
    repo = PrintJobRepository(db)
    job = await repo.create_job(
        organization_id=current_user.org_id,
        user_id=current_user.id,
        model_id=request.model_id,
        name=request.name,
        printer_id=request.printer_id,
        priority=request.priority
    )
    await db.commit()
    return JobResponse(**job.to_dict())


@router.get("/queue")
async def get_queue(
    current_user: CurrentUser,
    printer_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get the current print queue."""
    repo = PrintJobRepository(db)
    queue = await repo.get_queue(current_user.org_id, printer_id)
    return [JobResponse(**j.to_dict()) for j in queue]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get job details."""
    repo = PrintJobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job or job.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**job.to_dict())


@router.post("/{job_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_job(
    job_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.JOBS_CANCEL)),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a print job."""
    repo = PrintJobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job or job.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Job not found")
    await repo.cancel_job(job_id)
    await db.commit()
    return {"status": "cancelled"}


@router.post("/{job_id}/pause")
async def pause_job(
    job_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.PRINTERS_CONTROL)),
    db: AsyncSession = Depends(get_db)
):
    """Pause a running print job."""
    repo = PrintJobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job or job.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Job not found")
    await repo.pause_job(job_id)
    await db.commit()
    return {"status": "paused"}


@router.post("/{job_id}/resume")
async def resume_job(
    job_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.PRINTERS_CONTROL)),
    db: AsyncSession = Depends(get_db)
):
    """Resume a paused print job."""
    repo = PrintJobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job or job.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Job not found")
    await repo.resume_job(job_id)
    await db.commit()
    return {"status": "resumed"}
