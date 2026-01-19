"""Analytics and reporting routes."""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.repositories.jobs import PrintJobRepository
from src.db.repositories.materials import MaterialRepository
from src.auth.middleware import CurrentUser, require_permission
from src.auth.rbac import Permission

router = APIRouter()


@router.get("/summary")
async def get_analytics_summary(
    current_user: CurrentUser = Depends(require_permission(Permission.ANALYTICS_VIEW)),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get analytics summary for the organization."""
    job_repo = PrintJobRepository(db)
    material_repo = MaterialRepository(db)

    start_date = datetime.utcnow() - timedelta(days=days)

    # Get job stats
    job_stats = await job_repo.get_stats(
        current_user.org_id,
        start_date=start_date
    )

    # Get material inventory
    inventory = await material_repo.get_inventory_value(current_user.org_id)

    return {
        "period_days": days,
        "jobs": job_stats,
        "inventory": inventory
    }


@router.get("/print-history")
async def get_print_history(
    current_user: CurrentUser = Depends(require_permission(Permission.ANALYTICS_VIEW)),
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db)
):
    """Get recent print history."""
    repo = PrintJobRepository(db)
    jobs = await repo.get_recent(current_user.org_id, days=days)
    return [j.to_dict() for j in jobs]


@router.get("/failure-analysis")
async def get_failure_analysis(
    current_user: CurrentUser = Depends(require_permission(Permission.ANALYTICS_VIEW)),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Analyze print failures."""
    from sqlalchemy import select, func
    from src.db.models import PrintJob, JobStatus

    start_date = datetime.utcnow() - timedelta(days=days)

    # Get failure reasons breakdown
    result = await db.execute(
        select(
            PrintJob.failure_reason,
            PrintJob.failure_detected_by,
            func.count(PrintJob.id)
        )
        .where(
            PrintJob.organization_id == current_user.org_id,
            PrintJob.status == JobStatus.FAILED,
            PrintJob.completed_at >= start_date
        )
        .group_by(PrintJob.failure_reason, PrintJob.failure_detected_by)
    )

    failures = [
        {"reason": row[0] or "Unknown", "detected_by": row[1] or "Unknown", "count": row[2]}
        for row in result.all()
    ]

    return {
        "period_days": days,
        "failures": failures,
        "total_failures": sum(f["count"] for f in failures)
    }


@router.get("/material-usage")
async def get_material_usage(
    current_user: CurrentUser = Depends(require_permission(Permission.ANALYTICS_VIEW)),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get material usage statistics."""
    from sqlalchemy import select, func
    from src.db.models import PrintJob, JobStatus

    start_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(func.sum(PrintJob.actual_material_grams))
        .where(
            PrintJob.organization_id == current_user.org_id,
            PrintJob.status == JobStatus.COMPLETED,
            PrintJob.completed_at >= start_date
        )
    )
    total_used = result.scalar() or 0

    # Get inventory
    material_repo = MaterialRepository(db)
    inventory = await material_repo.get_inventory_value(current_user.org_id)

    return {
        "period_days": days,
        "total_used_grams": total_used,
        "current_inventory": inventory
    }


@router.get("/export")
async def export_analytics(
    current_user: CurrentUser = Depends(require_permission(Permission.ANALYTICS_EXPORT)),
    format: str = Query("json", regex="^(json|csv)$"),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Export analytics data."""
    from fastapi.responses import Response

    repo = PrintJobRepository(db)
    jobs = await repo.get_recent(current_user.org_id, days=days, limit=1000)

    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "id", "name", "status", "created_at", "completed_at",
            "actual_duration_minutes", "actual_material_grams"
        ])
        writer.writeheader()
        for job in jobs:
            writer.writerow({
                "id": job.id,
                "name": job.name,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else "",
                "actual_duration_minutes": job.actual_duration_minutes or "",
                "actual_material_grams": job.actual_material_grams or ""
            })

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=analytics.csv"}
        )

    return [j.to_dict() for j in jobs]
