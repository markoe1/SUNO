"""Performance report routes — generate and retrieve client reports."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models_v2 import Client, ClientStatus, PerformanceReport
from services.report_builder import build_report, build_reports_for_all_clients
from services.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportGenerateRequest(BaseModel):
    client_id: Optional[UUID] = None  # None = all active clients
    period_type: str = "monthly"  # "weekly" or "monthly"
    period_start: datetime
    period_end: datetime


class ReportResponse(BaseModel):
    id: UUID
    client_id: UUID
    period_type: str
    period_start: datetime
    period_end: datetime
    total_clips: int
    total_views: int
    total_likes: int
    total_comments: int
    total_shares: int
    top_clips_json: Optional[list]
    best_hooks_json: Optional[list]
    insights_json: Optional[dict]
    created_at: datetime
    client_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_reports(
    data: ReportGenerateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate performance reports for one client or all active clients."""
    if data.client_id:
        # Single client
        result = await db.execute(
            select(Client)
            .where(Client.id == data.client_id)
            .where(Client.user_id == current_user.id)
        )
        client = result.scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        report = await build_report(
            db, str(data.client_id), data.period_type, data.period_start, data.period_end
        )
        return {"generated": [{"client": client.name, "report_id": str(report.id)}], "errors": []}
    else:
        # All active clients
        summary = await build_reports_for_all_clients(
            db, str(current_user.id), data.period_type, data.period_start, data.period_end
        )
        return summary


@router.get("", response_model=List[ReportResponse])
async def list_reports(
    client_id: Optional[UUID] = None,
    period_type: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(PerformanceReport, Client)
        .join(Client, PerformanceReport.client_id == Client.id)
        .where(Client.user_id == current_user.id)
    )
    if client_id:
        query = query.where(PerformanceReport.client_id == client_id)
    if period_type:
        query = query.where(PerformanceReport.period_type == period_type)

    query = query.order_by(PerformanceReport.created_at.desc())
    result = await db.execute(query)
    rows = result.all()

    return [
        ReportResponse(**report.__dict__, client_name=client.name)
        for report, client in rows
    ]


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PerformanceReport, Client)
        .join(Client, PerformanceReport.client_id == Client.id)
        .where(PerformanceReport.id == report_id)
        .where(Client.user_id == current_user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    report, client = row
    return ReportResponse(**report.__dict__, client_name=client.name)


@router.post("/invoice-run")
async def run_invoice_generation(
    month: str,  # "2026-03"
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate invoices for all active clients for a given month."""
    import re
    if not re.match(r"^\d{4}-\d{2}$", month):
        raise HTTPException(status_code=400, detail="month must be in YYYY-MM format")

    from services.invoice_generator import generate_invoices_for_month
    summary = await generate_invoices_for_month(db, str(current_user.id), month)
    return summary
