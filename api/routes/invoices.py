"""Invoice routes — monthly billing for clip operator clients."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models_v2 import Client, ClientClip, ClipStatus, Invoice
from services.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/invoices", tags=["invoices"])


class InvoiceCreate(BaseModel):
    client_id: UUID
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")  # "2026-03"
    base_amount: float = Field(1500.0, ge=0)
    performance_bonus: float = Field(0.0, ge=0)


class InvoiceMarkPaid(BaseModel):
    paddle_transaction_id: Optional[str] = None


class InvoiceResponse(BaseModel):
    id: UUID
    client_id: UUID
    month: str
    amount: float
    base_amount: float
    performance_bonus: float
    clips_delivered: int
    total_views: int
    view_guarantee_met: bool
    paddle_transaction_id: Optional[str]
    paid_at: Optional[datetime]
    created_at: datetime
    # computed
    client_name: Optional[str] = None
    is_paid: bool = False

    class Config:
        from_attributes = True


@router.post("/generate", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def generate_invoice(
    data: InvoiceCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a monthly invoice for a client. Auto-calculates clips delivered and views."""

    # Verify client ownership
    client_result = await db.execute(
        select(Client).where(Client.id == data.client_id).where(Client.user_id == current_user.id)
    )
    client = client_result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    # Check for duplicate invoice
    existing = await db.execute(
        select(Invoice)
        .where(Invoice.client_id == data.client_id)
        .where(Invoice.month == data.month)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice for {data.month} already exists for this client",
        )

    # Count posted clips for this month
    year, month_num = data.month.split("-")
    month_start = datetime(int(year), int(month_num), 1, tzinfo=timezone.utc)
    if int(month_num) == 12:
        month_end = datetime(int(year) + 1, 1, 1, tzinfo=timezone.utc)
    else:
        month_end = datetime(int(year), int(month_num) + 1, 1, tzinfo=timezone.utc)

    clips_result = await db.execute(
        select(func.count(ClientClip.id), func.coalesce(func.sum(ClientClip.total_views), 0))
        .where(ClientClip.client_id == data.client_id)
        .where(ClientClip.status == ClipStatus.POSTED)
        .where(ClientClip.posted_at >= month_start)
        .where(ClientClip.posted_at < month_end)
    )
    clips_delivered, total_views = clips_result.one()

    view_guarantee_met = total_views >= client.view_guarantee
    total_amount = data.base_amount + data.performance_bonus

    invoice = Invoice(
        client_id=data.client_id,
        month=data.month,
        amount=total_amount,
        base_amount=data.base_amount,
        performance_bonus=data.performance_bonus,
        clips_delivered=clips_delivered,
        total_views=total_views,
        view_guarantee_met=view_guarantee_met,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    logger.info(f"Generated invoice for {client.name} — {data.month} — ${total_amount}")
    return InvoiceResponse(
        **invoice.__dict__,
        client_name=client.name,
        is_paid=invoice.paid_at is not None,
    )


@router.get("/", response_model=List[InvoiceResponse])
async def list_invoices(
    client_id: Optional[UUID] = None,
    unpaid_only: bool = False,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Invoice, Client)
        .join(Client, Invoice.client_id == Client.id)
        .where(Client.user_id == current_user.id)
    )
    if client_id:
        query = query.where(Invoice.client_id == client_id)
    if unpaid_only:
        query = query.where(Invoice.paid_at.is_(None))

    query = query.order_by(Invoice.created_at.desc())
    result = await db.execute(query)
    rows = result.all()

    return [
        InvoiceResponse(
            **inv.__dict__,
            client_name=client.name,
            is_paid=inv.paid_at is not None,
        )
        for inv, client in rows
    ]


@router.post("/{invoice_id}/mark-paid", response_model=InvoiceResponse)
async def mark_invoice_paid(
    invoice_id: UUID,
    data: InvoiceMarkPaid,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Invoice, Client)
        .join(Client, Invoice.client_id == Client.id)
        .where(Invoice.id == invoice_id)
        .where(Client.user_id == current_user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    invoice, client = row

    if invoice.paid_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice already marked as paid")

    invoice.paid_at = datetime.now(timezone.utc)
    if data.paddle_transaction_id:
        invoice.paddle_transaction_id = data.paddle_transaction_id

    await db.commit()
    await db.refresh(invoice)
    logger.info(f"Invoice {invoice_id} marked paid for {client.name}")
    return InvoiceResponse(
        **invoice.__dict__,
        client_name=client.name,
        is_paid=True,
    )


@router.get("/summary", response_model=dict)
async def invoice_summary(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Overall revenue summary across all clients."""
    result = await db.execute(
        select(
            func.coalesce(func.sum(Invoice.amount), 0).label("total_billed"),
            func.coalesce(
                func.sum(Invoice.amount).filter(Invoice.paid_at.is_not(None)), 0
            ).label("total_collected"),
            func.count(Invoice.id).label("total_invoices"),
            func.count(Invoice.id).filter(Invoice.paid_at.is_(None)).label("unpaid_count"),
        )
        .join(Client, Invoice.client_id == Client.id)
        .where(Client.user_id == current_user.id)
    )
    row = result.one()
    return {
        "total_billed": float(row.total_billed),
        "total_collected": float(row.total_collected),
        "outstanding": float(row.total_billed) - float(row.total_collected),
        "total_invoices": row.total_invoices,
        "unpaid_count": row.unpaid_count,
    }
