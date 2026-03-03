"""RQ task: monitor the status of pending submissions for a user."""

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db.engine import DATABASE_URL
from db.models import AuditLog, Job, Submission, UserSecret
from services.secrets import decrypt_blob
from services.whop_client import WhopAuthError, WhopClient

logger = logging.getLogger(__name__)

# Whop statuses that map to our "confirmed"
CONFIRMED_STATUSES = {"approved", "confirmed", "accepted", "paid"}
REJECTED_STATUSES = {"rejected", "denied", "declined", "removed"}


async def _monitor_submissions_async(user_id: str, job_id: str):
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
            # Load Whop session
            result = await db.execute(
                select(UserSecret).where(UserSecret.user_id == user_id)
            )
            secret = result.scalar_one_or_none()
            if not secret:
                raise ValueError("No Whop session found for user")

            blob = decrypt_blob(secret.encrypted_blob)
            client = WhopClient(cookies=blob.get("cookies", {}))

            # Load all "submitted" submissions for this user
            subs_result = await db.execute(
                select(Submission).where(
                    Submission.user_id == user_id,
                    Submission.status == "submitted",
                    Submission.whop_submission_id.isnot(None),
                )
            )
            submissions = subs_result.scalars().all()

            updated_count = 0
            for sub in submissions:
                try:
                    check = client.check_submission(sub.whop_submission_id)
                    whop_status = (check.get("status") or "").lower()

                    new_status = sub.status
                    if whop_status in CONFIRMED_STATUSES:
                        new_status = "confirmed"
                    elif whop_status in REJECTED_STATUSES:
                        new_status = "rejected"
                    elif whop_status == "failed":
                        new_status = "failed"

                    if new_status != sub.status:
                        await db.execute(
                            update(Submission)
                            .where(Submission.id == sub.id)
                            .values(status=new_status, updated_at=datetime.now(timezone.utc))
                        )
                        db.add(
                            AuditLog(
                                id=uuid.uuid4(),
                                user_id=uuid.UUID(user_id),
                                job_id=uuid.UUID(job_id),
                                level="info",
                                message=f"Submission {sub.id} status: {sub.status} → {new_status}",
                                meta_json={
                                    "submission_id": str(sub.id),
                                    "whop_submission_id": sub.whop_submission_id,
                                    "old_status": sub.status,
                                    "new_status": new_status,
                                    "whop_status": whop_status,
                                },
                            )
                        )
                        updated_count += 1

                except WhopAuthError:
                    raise
                except Exception as exc:
                    logger.warning("check_submission %s failed: %s", sub.whop_submission_id, exc)

            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="done",
                    result_json={
                        "checked": len(submissions),
                        "updated": updated_count,
                    },
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.info(
                "monitor_submissions: user=%s checked=%d updated=%d",
                user_id,
                len(submissions),
                updated_count,
            )

        except WhopAuthError as exc:
            logger.error("monitor_submissions auth error: %s", exc)
            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="failed",
                    error_message=f"Auth error: {exc}",
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            raise

        except Exception as exc:
            logger.error("monitor_submissions error: %s", exc)
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


def monitor_submissions(user_id: str, job_id: str):
    """RQ entry point."""
    asyncio.run(_monitor_submissions_async(user_id, job_id))
