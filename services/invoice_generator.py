"""
Invoice Generator Service
=========================
Generates monthly invoices for all active clients.
Call manually via API or schedule as a background job on the 1st of each month.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models_v2 import Client, ClientClip, ClipStatus, Invoice, ClientStatus

logger = logging.getLogger(__name__)


async def generate_invoice_for_client(
    db: AsyncSession,
    client: Client,
    month: str,
    performance_bonus: float = 0.0,
) -> Invoice | None:
    """
    Generate a monthly invoice for a single client.
    Counts all POSTED clips within the given month and computes view totals.
    Returns None if invoice already exists.
    """
    # Idempotency check
    existing = await db.execute(
        select(Invoice)
        .where(Invoice.client_id == client.id)
        .where(Invoice.month == month)
    )
    if existing.scalar_one_or_none():
        logger.info(f"Invoice already exists for {client.name} — {month}, skipping")
        return None

    year, month_num = month.split("-")
    month_start = datetime(int(year), int(month_num), 1, tzinfo=timezone.utc)
    next_month = int(month_num) + 1
    next_year = int(year)
    if next_month > 12:
        next_month = 1
        next_year += 1
    month_end = datetime(next_year, next_month, 1, tzinfo=timezone.utc)

    # Count posted clips and total views for this month
    result = await db.execute(
        select(
            func.count(ClientClip.id),
            func.coalesce(func.sum(ClientClip.total_views), 0),
        )
        .where(ClientClip.client_id == client.id)
        .where(ClientClip.status == ClipStatus.POSTED)
        .where(ClientClip.posted_at >= month_start)
        .where(ClientClip.posted_at < month_end)
    )
    clips_delivered, total_views = result.one()

    view_guarantee_met = total_views >= client.view_guarantee

    # If view guarantee met, client pays full rate + any bonus
    # If not met, still generate invoice but flag it
    total = client.monthly_rate + performance_bonus

    invoice = Invoice(
        client_id=client.id,
        month=month,
        amount=total,
        base_amount=client.monthly_rate,
        performance_bonus=performance_bonus,
        clips_delivered=clips_delivered,
        total_views=total_views,
        view_guarantee_met=view_guarantee_met,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    logger.info(
        f"Generated invoice for {client.name} — {month} — "
        f"${total} | {clips_delivered} clips | {total_views:,} views | "
        f"guarantee {'MET' if view_guarantee_met else 'MISSED'}"
    )
    return invoice


async def generate_invoices_for_month(
    db: AsyncSession,
    operator_user_id: str,
    month: str,
) -> dict:
    """
    Generate invoices for ALL active clients of an operator for a given month.
    Returns summary dict.
    """
    result = await db.execute(
        select(Client)
        .where(Client.user_id == operator_user_id)
        .where(Client.status == ClientStatus.ACTIVE)
    )
    clients = result.scalars().all()

    generated = []
    skipped = []
    errors = []

    for client in clients:
        try:
            invoice = await generate_invoice_for_client(db, client, month)
            if invoice:
                generated.append({"client": client.name, "amount": invoice.amount})
            else:
                skipped.append(client.name)
        except Exception as e:
            logger.error(f"Failed to generate invoice for {client.name}: {e}")
            errors.append({"client": client.name, "error": str(e)})

    total_billed = sum(i["amount"] for i in generated)
    logger.info(
        f"Invoice run for {month}: {len(generated)} generated, "
        f"{len(skipped)} skipped, {len(errors)} errors. Total: ${total_billed:,.0f}"
    )

    return {
        "month": month,
        "generated": generated,
        "skipped": skipped,
        "errors": errors,
        "total_billed": total_billed,
    }
