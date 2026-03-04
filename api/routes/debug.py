"""Debug routes — authenticated users only.

Helps verify Whop connection health and discover correct API endpoints
without having to inspect network traffic manually.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models import Job, Submission, User, UserSecret
from services.secrets import decrypt_blob
from services.whop_client import (
    WHOP_BASE_URL,
    WHOP_CAMPAIGNS_PATH,
    WHOP_CHECK_PATH,
    WHOP_SUBMIT_PATH,
    WhopClient,
)

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get("/whop")
async def whop_connection_test(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Test Whop connection without submitting anything.

    Returns session validity, how many campaigns were found, and the
    configured endpoint paths. Use this to verify cookies are active
    and to diagnose wrong API paths.
    """
    result = await db.execute(
        select(UserSecret).where(UserSecret.user_id == current_user.id)
    )
    secret = result.scalar_one_or_none()

    if not secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Whop session configured. Go to Settings to add your cookies.",
        )

    try:
        blob = decrypt_blob(secret.encrypted_blob)
        client = WhopClient(cookies=blob.get("cookies", {}))

        session_valid = client.validate_session()
        campaigns = []
        campaign_error = None

        if session_valid:
            try:
                campaigns = client.list_campaigns()
            except Exception as exc:
                campaign_error = str(exc)

        return {
            "session_valid": session_valid,
            "campaigns_found": len(campaigns),
            "raw_campaign_sample": campaigns[0] if campaigns else None,
            "campaign_error": campaign_error,
            "configured_paths": {
                "base_url": WHOP_BASE_URL,
                "campaigns": WHOP_CAMPAIGNS_PATH,
                "submit": WHOP_SUBMIT_PATH,
                "check": WHOP_CHECK_PATH,
            },
            "hint": (
                "If campaigns_found is 0 but session_valid is True: open DevTools "
                "Network tab while browsing whop.com/clipping, find the campaigns "
                "list XHR request, copy its path, and set WHOP_CAMPAIGNS_PATH env var."
            ),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Whop test failed: {exc}",
        )


@router.post("/trigger-monitor")
async def trigger_monitor_now(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a submission status check. Normally runs on schedule."""
    from workers.queue import q
    from workers.tasks.monitor_submissions import monitor_submissions

    result = await db.execute(
        select(Submission).where(
            Submission.user_id == current_user.id,
            Submission.status == "submitted",
        )
    )
    pending = result.scalars().all()

    if not pending:
        return {"detail": "No submitted clips to monitor.", "submitted_count": 0}

    job = Job(
        id=uuid.uuid4(),
        user_id=current_user.id,
        type="MONITOR_SUBMISSIONS",
        status="pending",
        payload_json={"triggered_by": "manual"},
    )
    db.add(job)
    await db.flush()

    rq_job = q.enqueue(
        monitor_submissions,
        kwargs={"user_id": str(current_user.id), "job_id": str(job.id)},
        job_id=str(uuid.uuid4()),
    )
    job.rq_job_id = rq_job.id
    await db.commit()

    return {
        "detail": "Monitor job enqueued",
        "job_id": str(job.id),
        "submissions_to_check": len(pending),
    }
