"""RQ task: submit a clip URL to a Whop campaign with idempotency guard."""

import asyncio
import hashlib
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db.engine import DATABASE_URL
from db.models import AuditLog, Job, Submission, UserSecret
from services.secrets import decrypt_blob
from services.whop_client import DryRunWhopClient, WhopAuthError, WhopClient

logger = logging.getLogger(__name__)

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = int(os.getenv("RETRY_BACKOFF_BASE", "60"))


def _compute_dedupe_hash(user_id: str, campaign_id: str, clip_url: str) -> str:
    raw = f"{user_id}:{campaign_id}:{clip_url}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _submit_clip_async(
    user_id: str,
    job_id: str,
    campaign_id: str,
    clip_url: str,
    dry_run: bool = False,
):
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)

    async with AsyncSession() as db:
        # Mark job running
        await db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(status="running", updated_at=datetime.now(timezone.utc))
        )
        await db.commit()

        try:
            dedupe_hash = _compute_dedupe_hash(user_id, campaign_id, clip_url)

            # IDEMPOTENCY CHECK
            existing_sub = await db.execute(
                select(Submission).where(
                    Submission.dedupe_hash == dedupe_hash,
                    Submission.status.in_(["submitted", "confirmed"]),
                )
            )
            existing_sub = existing_sub.scalar_one_or_none()

            if existing_sub:
                logger.info(
                    "submit_clip: DUPLICATE detected for hash=%s status=%s — skipping",
                    dedupe_hash,
                    existing_sub.status,
                )
                db.add(
                    AuditLog(
                        id=uuid.uuid4(),
                        user_id=uuid.UUID(user_id),
                        job_id=uuid.UUID(job_id),
                        level="info",
                        message="Duplicate submission skipped (idempotency)",
                        meta_json={
                            "dedupe_hash": dedupe_hash,
                            "existing_submission_id": str(existing_sub.id),
                        },
                    )
                )
                await db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        status="done",
                        result_json={
                            "duplicate": True,
                            "existing_submission_id": str(existing_sub.id),
                        },
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await db.commit()
                return

            # Create submission row
            submission = Submission(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                whop_campaign_id=campaign_id,
                clip_url=clip_url,
                status="pending",
                dedupe_hash=dedupe_hash,
            )
            db.add(submission)
            await db.commit()
            await db.refresh(submission)

            # Load session
            result = await db.execute(
                select(UserSecret).where(UserSecret.user_id == user_id)
            )
            secret = result.scalar_one_or_none()

            if dry_run:
                client = DryRunWhopClient()
            elif not secret:
                raise ValueError("No Whop session found for user")
            else:
                blob = decrypt_blob(secret.encrypted_blob)
                client = WhopClient(cookies=blob.get("cookies", {}))

            # Submit with retry
            last_error = None
            result_data = None
            for attempt in range(MAX_RETRIES):
                try:
                    result_data = client.submit_clip(campaign_id, clip_url)
                    if result_data.get("success"):
                        break
                    else:
                        last_error = result_data.get("error", "Unknown error")
                        wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                        logger.warning(
                            "submit_clip attempt %d failed: %s — retrying in %ds",
                            attempt + 1,
                            last_error,
                            wait,
                        )
                        time.sleep(wait)
                except WhopAuthError:
                    raise
                except Exception as exc:
                    last_error = str(exc)
                    wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning("submit_clip attempt %d exception: %s", attempt + 1, exc)
                    time.sleep(wait)

            if result_data and result_data.get("success"):
                submission.status = "submitted"
                submission.whop_submission_id = result_data.get("submission_id")
                await db.execute(
                    update(Submission)
                    .where(Submission.id == submission.id)
                    .values(
                        status="submitted",
                        whop_submission_id=result_data.get("submission_id"),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                db.add(
                    AuditLog(
                        id=uuid.uuid4(),
                        user_id=uuid.UUID(user_id),
                        job_id=uuid.UUID(job_id),
                        level="info",
                        message="Clip submitted successfully",
                        meta_json={
                            "campaign_id": campaign_id,
                            "clip_url": clip_url,
                            "submission_id": str(submission.id),
                            "whop_submission_id": result_data.get("submission_id"),
                            "dry_run": dry_run,
                        },
                    )
                )
                await db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        status="done",
                        result_json={
                            "submission_id": str(submission.id),
                            "whop_submission_id": result_data.get("submission_id"),
                            "dry_run": dry_run,
                        },
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            else:
                await db.execute(
                    update(Submission)
                    .where(Submission.id == submission.id)
                    .values(
                        status="failed",
                        error_message=last_error,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                db.add(
                    AuditLog(
                        id=uuid.uuid4(),
                        user_id=uuid.UUID(user_id),
                        job_id=uuid.UUID(job_id),
                        level="error",
                        message=f"Clip submission failed after {MAX_RETRIES} attempts",
                        meta_json={"error": last_error, "campaign_id": campaign_id},
                    )
                )
                await db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        status="failed",
                        error_message=last_error,
                        updated_at=datetime.now(timezone.utc),
                    )
                )

            await db.commit()

        except WhopAuthError as exc:
            logger.error("submit_clip auth error: %s", exc)
            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="failed",
                    error_message=f"Whop auth error: {exc}",
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            raise

        except Exception as exc:
            logger.error("submit_clip error: %s", exc)
            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="failed",
                    error_message=str(exc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            raise

    await engine.dispose()


def submit_clip(
    user_id: str,
    job_id: str,
    campaign_id: str,
    clip_url: str,
    dry_run: bool = False,
):
    """RQ entry point."""
    asyncio.run(_submit_clip_async(user_id, job_id, campaign_id, clip_url, dry_run))
