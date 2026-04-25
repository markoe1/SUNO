"""Jobs routes: list, detail, cancel, kill-switch."""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models import Job, User

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobResponse(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    payload_json: Optional[dict] = None
    result_json: Optional[dict] = None
    retries: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    type_filter: Optional[str] = Query(None, alias="type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = [Job.user_id == current_user.id]
    if status_filter:
        filters.append(Job.status == status_filter)
    if type_filter:
        filters.append(Job.type == type_filter)

    # Count
    count_q = select(Job).where(and_(*filters))
    all_jobs = (await db.execute(count_q)).scalars().all()
    total = len(all_jobs)

    # Paginate
    offset = (page - 1) * page_size
    q = (
        select(Job)
        .where(and_(*filters))
        .order_by(Job.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(q)
    jobs = result.scalars().all()

    return JobListResponse(
        items=[JobResponse.model_validate(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.status in ("done", "failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is already {job.status}",
        )

    # Try to cancel the RQ job
    if job.rq_job_id:
        try:
            from workers.queue import redis_conn
            from rq.job import Job as RQJob

            rq_job = RQJob.fetch(job.rq_job_id, connection=redis_conn)
            rq_job.cancel()
        except Exception:
            pass  # Job may already be running or done

    await db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="cancelled")
    )
    await db.commit()
    return {"detail": "Job cancelled", "job_id": str(job_id)}


@router.post("/kill-switch")
async def kill_switch(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pause user and cancel all pending/running jobs."""
    # Pause user
    current_user.jobs_paused = True

    # Fetch all cancellable jobs
    result = await db.execute(
        select(Job).where(
            Job.user_id == current_user.id,
            Job.status.in_(["pending", "running"]),
        )
    )
    jobs_to_cancel = result.scalars().all()

    cancelled = 0
    for job in jobs_to_cancel:
        if job.rq_job_id:
            try:
                from workers.queue import redis_conn
                from rq.job import Job as RQJob

                rq_job = RQJob.fetch(job.rq_job_id, connection=redis_conn)
                rq_job.cancel()
            except Exception:
                pass
        job.status = "cancelled"
        cancelled += 1

    await db.commit()
    return {
        "detail": "Kill switch activated",
        "jobs_paused": True,
        "jobs_cancelled": cancelled,
    }
