"""Submissions routes: list, submit, retry."""

import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models import Job, Submission, User

router = APIRouter(prefix="/api/submissions", tags=["submissions"])

WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "2"))


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    whop_campaign_id: str
    clip_url: str
    status: str
    dedupe_hash: str
    whop_submission_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubmissionListResponse(BaseModel):
    items: List[SubmissionResponse]
    total: int
    page: int
    page_size: int


class SubmitRequest(BaseModel):
    campaign_id: str
    clip_urls: List[str]
    dry_run: bool = False


class SubmitResponse(BaseModel):
    job_ids: List[str]
    enqueued: int
    dry_run: bool


@router.get("", response_model=SubmissionListResponse)
async def list_submissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = [Submission.user_id == current_user.id]
    if status_filter:
        filters.append(Submission.status == status_filter)

    all_subs = (await db.execute(select(Submission).where(and_(*filters)))).scalars().all()
    total = len(all_subs)

    offset = (page - 1) * page_size
    q = (
        select(Submission)
        .where(and_(*filters))
        .order_by(Submission.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(q)
    subs = result.scalars().all()

    return SubmissionListResponse(
        items=[SubmissionResponse.model_validate(s) for s in subs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SubmitResponse)
async def submit_clips(
    body: SubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.jobs_paused:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Your jobs are currently paused. Resume from Settings.",
        )

    # Check concurrency limit
    running_q = await db.execute(
        select(Job).where(
            Job.user_id == current_user.id,
            Job.status.in_(["pending", "running"]),
        )
    )
    running_jobs = running_q.scalars().all()
    if len(running_jobs) >= WORKER_CONCURRENCY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Concurrency limit reached ({WORKER_CONCURRENCY} active jobs). Wait for jobs to complete.",
        )

    # Strip and deduplicate clip URLs
    clip_urls = list(dict.fromkeys(url.strip() for url in body.clip_urls if url.strip()))
    if not clip_urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No valid clip URLs provided"
        )

    from workers.queue import q
    from workers.tasks.submit_clip import submit_clip

    job_ids = []
    for clip_url in clip_urls:
        # Create DB job record
        job = Job(
            id=uuid.uuid4(),
            user_id=current_user.id,
            type="SUBMIT_CLIP",
            status="pending",
            payload_json={
                "campaign_id": body.campaign_id,
                "clip_url": clip_url,
                "dry_run": body.dry_run,
            },
        )
        db.add(job)
        await db.flush()  # Get the ID

        # Enqueue RQ job
        rq_job = q.enqueue(
            submit_clip,
            kwargs={
                "user_id": str(current_user.id),
                "job_id": str(job.id),
                "campaign_id": body.campaign_id,
                "clip_url": clip_url,
                "dry_run": body.dry_run,
            },
            job_id=str(uuid.uuid4()),
        )
        job.rq_job_id = rq_job.id
        job_ids.append(str(job.id))

    await db.commit()

    return SubmitResponse(
        job_ids=job_ids,
        enqueued=len(job_ids),
        dry_run=body.dry_run,
    )


@router.post("/{submission_id}/retry")
async def retry_submission(
    submission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.user_id == current_user.id,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    if sub.status not in ("failed", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only failed/rejected submissions can be retried (current: {sub.status})",
        )

    if current_user.jobs_paused:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Jobs are paused. Resume from Settings.",
        )

    from workers.queue import q
    from workers.tasks.submit_clip import submit_clip

    # Reset submission status
    await db.execute(
        update(Submission)
        .where(Submission.id == submission_id)
        .values(status="pending", error_message=None)
    )

    # Create new job
    job = Job(
        id=uuid.uuid4(),
        user_id=current_user.id,
        type="SUBMIT_CLIP",
        status="pending",
        payload_json={
            "campaign_id": sub.whop_campaign_id,
            "clip_url": sub.clip_url,
            "dry_run": False,
            "retry_of": str(submission_id),
        },
    )
    db.add(job)
    await db.flush()

    rq_job = q.enqueue(
        submit_clip,
        kwargs={
            "user_id": str(current_user.id),
            "job_id": str(job.id),
            "campaign_id": sub.whop_campaign_id,
            "clip_url": sub.clip_url,
            "dry_run": False,
        },
        job_id=str(uuid.uuid4()),
    )
    job.rq_job_id = rq_job.id

    await db.commit()

    return {"detail": "Submission re-enqueued", "job_id": str(job.id)}
