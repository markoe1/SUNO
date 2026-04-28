"""RQ task: sync Whop campaigns for a user and upsert into DB."""

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

# Ensure project root is on path when executed by RQ worker
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db.engine import DATABASE_URL
from db.models import AuditLog, Campaign, Job, User, UserSecret
from services.secrets import decrypt_blob
from services.whop_client import WhopAuthError, WhopClient

logger = logging.getLogger(__name__)


async def _sync_campaigns_async(user_id: str, job_id: str):
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
            # Use global WHOP_API_KEY from environment (no per-user session needed)
            client = WhopClient()
            campaigns = client.list_campaigns()

            upserted = 0
            for c in campaigns:
                whop_id = c.get("whop_campaign_id")
                if not whop_id:
                    continue
                existing = await db.execute(
                    select(Campaign).where(Campaign.whop_campaign_id == whop_id)
                )
                existing = existing.scalar_one_or_none()
                if existing:
                    existing.name = c.get("name", existing.name)
                    existing.cpm = c.get("cpm", existing.cpm)
                    existing.budget_remaining = c.get("budget_remaining", existing.budget_remaining)
                    existing.is_free = c.get("is_free", existing.is_free)
                    existing.drive_url = c.get("drive_url", existing.drive_url)
                    existing.youtube_url = c.get("youtube_url", existing.youtube_url)
                    existing.allowed_platforms = c.get("allowed_platforms", existing.allowed_platforms)
                    existing.available = c.get("available", existing.available)
                    existing.last_checked = datetime.now(timezone.utc)
                else:
                    db.add(
                        Campaign(
                            id=uuid.uuid4(),
                            whop_campaign_id=whop_id,
                            name=c.get("name", "Unknown"),
                            cpm=c.get("cpm"),
                            budget_remaining=c.get("budget_remaining"),
                            is_free=c.get("is_free", False),
                            drive_url=c.get("drive_url"),
                            youtube_url=c.get("youtube_url"),
                            allowed_platforms=c.get("allowed_platforms"),
                            active=c.get("active", True),
                        )
                    )
                upserted += 1

            await db.commit()

            # Audit log
            db.add(
                AuditLog(
                    id=uuid.uuid4(),
                    user_id=uuid.UUID(user_id),
                    job_id=uuid.UUID(job_id),
                    level="info",
                    message=f"Synced {upserted} campaigns from Whop",
                    meta_json={"campaigns_synced": upserted},
                )
            )

            # Mark job done
            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="done",
                    result_json={"campaigns_synced": upserted},
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.info("sync_campaigns: user=%s synced %d campaigns", user_id, upserted)

        except WhopAuthError as exc:
            logger.error("sync_campaigns auth error: %s", exc)
            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="failed", error_message=f"Auth error: {exc}", updated_at=datetime.now(timezone.utc))
            )
            await db.commit()
            raise

        except Exception as exc:
            logger.error("sync_campaigns error: %s", exc)
            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="failed", error_message=str(exc), updated_at=datetime.now(timezone.utc))
            )
            await db.commit()
            raise

    await engine.dispose()


def sync_campaigns(user_id: str, job_id: str):
    """RQ entry point."""
    asyncio.run(_sync_campaigns_async(user_id, job_id))
