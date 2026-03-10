"""
RQ Task: Auto-generate monthly invoices for all active clients.
Schedule to run on the 1st of each month.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db.engine import DATABASE_URL
from services.invoice_generator import generate_invoices_for_month

logger = logging.getLogger(__name__)


async def _generate_invoices_async(operator_user_id: str, month: str):
    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        summary = await generate_invoices_for_month(db, operator_user_id, month)

    await engine.dispose()
    return summary


def generate_monthly_invoices(operator_user_id: str, month: str | None = None):
    """
    Generate invoices for all active clients for the given month.
    If month is None, defaults to the previous calendar month.
    Format: "YYYY-MM"
    """
    if month is None:
        now = datetime.now(timezone.utc)
        # Default to previous month
        if now.month == 1:
            month = f"{now.year - 1}-12"
        else:
            month = f"{now.year}-{now.month - 1:02d}"

    logger.info(f"Generating invoices for operator {operator_user_id}, month={month}")
    result = asyncio.run(_generate_invoices_async(operator_user_id, month))
    logger.info(
        f"Invoice run done: {len(result['generated'])} generated, "
        f"{len(result['skipped'])} skipped, total=${result['total_billed']:,.0f}"
    )
    return result
