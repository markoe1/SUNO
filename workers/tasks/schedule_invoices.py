"""RQ task: run monthly invoice generation for all operators.

Designed to run on the 1st of each month at midnight UTC.

Scheduling options:

  Option A — RQ Scheduler (recommended for existing stack):
    pip install rq-scheduler
    rqscheduler &  # starts scheduler process
    Then call schedule_monthly_invoices_cron() once at startup to register.

  Option B — APScheduler (if you want in-process scheduling):
    pip install apscheduler  # already in requirements-saas.txt
    See create_scheduler() below — call from your startup event.

  Option C — External cron (simplest for production):
    Add to crontab or a cloud scheduler:
      0 0 1 * *  curl -X POST http://localhost:8000/api/invoices/run-monthly
    The /api/invoices/run-monthly endpoint accepts a POST from internal services.

Usage (manual):
  python -c "from workers.tasks.schedule_invoices import run_monthly_invoices; run_monthly_invoices()"
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db.engine import DATABASE_URL
from db.models import User
from services.invoice_generator import generate_invoices_for_month

logger = logging.getLogger(__name__)


async def _run_monthly_invoices_async(month: str) -> dict:
    """Generate invoices for all operators' active clients for a given month."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)

    total_generated = 0
    total_billed = 0.0
    operator_results = []

    async with AsyncSession() as db:
        # Get all active operators
        result = await db.execute(
            select(User).where(User.is_active == True)
        )
        operators = result.scalars().all()

        logger.info(
            "schedule_invoices: running monthly invoices for %d operators — month=%s",
            len(operators), month,
        )

        for operator in operators:
            try:
                summary = await generate_invoices_for_month(
                    db=db,
                    operator_user_id=operator.id,
                    month=month,
                )
                if summary["generated"]:
                    total_generated += len(summary["generated"])
                    total_billed += summary["total_billed"]
                    operator_results.append({
                        "operator": operator.email,
                        "generated": len(summary["generated"]),
                        "total_billed": summary["total_billed"],
                    })
                    logger.info(
                        "schedule_invoices: operator %s — %d invoices, $%.0f",
                        operator.email, len(summary["generated"]), summary["total_billed"],
                    )
            except Exception as exc:
                logger.error(
                    "schedule_invoices: failed for operator %s: %s",
                    operator.email, exc,
                )

    await engine.dispose()

    logger.info(
        "schedule_invoices complete: %d total invoices, $%.0f total billed",
        total_generated, total_billed,
    )
    return {
        "month": month,
        "total_generated": total_generated,
        "total_billed": total_billed,
        "operators": operator_results,
    }


def run_monthly_invoices(month: str = None) -> dict:
    """RQ entry point. Generates invoices for all operators for the given month.

    Args:
        month: "YYYY-MM" string. Defaults to the previous month (current date - 1 month),
               because invoices are generated at the start of the new month for the
               month just completed.
    """
    if not month:
        now = datetime.now(timezone.utc)
        # Bill for the previous month
        if now.month == 1:
            month = f"{now.year - 1}-12"
        else:
            month = f"{now.year}-{now.month - 1:02d}"

    return asyncio.run(_run_monthly_invoices_async(month))


# ---------------------------------------------------------------------------
# APScheduler integration (Option B)
# ---------------------------------------------------------------------------

def create_scheduler():
    """Create an APScheduler that runs invoice generation on the 1st of each month.

    Call this from your FastAPI startup event:

        from workers.tasks.schedule_invoices import create_scheduler

        @app.on_event("startup")
        async def startup():
            scheduler = create_scheduler()
            scheduler.start()

    The scheduler runs in-process. For production, prefer Option C (external cron)
    to avoid issues with multiple worker replicas running duplicate invoice jobs.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(
            func=run_monthly_invoices,
            trigger=CronTrigger(day=1, hour=0, minute=0),  # 1st of every month at 00:00 UTC
            id="monthly_invoices",
            replace_existing=True,
        )
        logger.info("APScheduler: monthly invoice job registered (1st of month, 00:00 UTC)")
        return scheduler
    except ImportError:
        logger.warning("apscheduler not installed — monthly invoice scheduling disabled")
        return None
