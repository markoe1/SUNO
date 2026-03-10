"""
RQ Task: Build performance reports for all active clients.
Schedule weekly (e.g. every Monday) and monthly (1st of month).
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db.engine import DATABASE_URL
from services.report_builder import build_reports_for_all_clients

logger = logging.getLogger(__name__)


async def _build_reports_async(operator_user_id: str, period_type: str, period_start: datetime, period_end: datetime):
    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        summary = await build_reports_for_all_clients(
            db, operator_user_id, period_type, period_start, period_end
        )

    await engine.dispose()
    return summary


def build_weekly_reports(operator_user_id: str):
    """Build reports for the past 7 days. Call this every Monday."""
    now = datetime.now(timezone.utc)
    period_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    period_start = period_end - timedelta(days=7)

    logger.info(f"Building weekly reports for operator {operator_user_id}: {period_start.date()} → {period_end.date()}")
    result = asyncio.run(_build_reports_async(operator_user_id, "weekly", period_start, period_end))
    logger.info(f"Weekly report run done: {len(result['built'])} built, {len(result['errors'])} errors")
    return result


def build_monthly_reports(operator_user_id: str, year: int, month: int):
    """Build reports for a full calendar month. Call this on the 1st."""
    period_start = datetime(year, month, 1, tzinfo=timezone.utc)
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    period_end = datetime(next_year, next_month, 1, tzinfo=timezone.utc)

    logger.info(f"Building monthly reports for operator {operator_user_id}: {year}-{month:02d}")
    result = asyncio.run(_build_reports_async(operator_user_id, "monthly", period_start, period_end))
    logger.info(f"Monthly report run done: {len(result['built'])} built, {len(result['errors'])} errors")
    return result
