"""
Report Builder Service
======================
Aggregates clip performance data into PerformanceReport records.
Used for weekly/monthly client reports.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.models_v2 import Client, ClientClip, ClipStatus, PerformanceReport

logger = logging.getLogger(__name__)


async def build_report(
    db: AsyncSession,
    client_id: str,
    period_type: str,  # "weekly" or "monthly"
    period_start: datetime,
    period_end: datetime,
) -> PerformanceReport:
    """Build a performance report for a client over a given period."""

    # Aggregate totals for posted clips in the period
    totals_result = await db.execute(
        select(
            func.count(ClientClip.id).label("total_clips"),
            func.coalesce(func.sum(ClientClip.total_views), 0).label("total_views"),
            func.coalesce(func.sum(ClientClip.total_likes), 0).label("total_likes"),
            func.coalesce(func.sum(ClientClip.total_comments), 0).label("total_comments"),
            func.coalesce(func.sum(ClientClip.total_shares), 0).label("total_shares"),
        )
        .where(ClientClip.client_id == client_id)
        .where(ClientClip.status == ClipStatus.POSTED)
        .where(ClientClip.posted_at >= period_start)
        .where(ClientClip.posted_at < period_end)
    )
    totals = totals_result.one()

    # Top 5 performing clips
    top_clips_result = await db.execute(
        select(ClientClip)
        .where(ClientClip.client_id == client_id)
        .where(ClientClip.status == ClipStatus.POSTED)
        .where(ClientClip.posted_at >= period_start)
        .where(ClientClip.posted_at < period_end)
        .order_by(desc(ClientClip.total_views))
        .limit(5)
    )
    top_clips = top_clips_result.scalars().all()
    top_clips_json = [
        {
            "clip_id": str(c.id),
            "title": c.title or c.hook_used or "Untitled",
            "views": c.total_views,
            "likes": c.total_likes,
            "tiktok_url": c.tiktok_url,
            "instagram_url": c.instagram_url,
            "youtube_url": c.youtube_url,
        }
        for c in top_clips
    ]

    # Best performing hooks (clips with hook text, sorted by views)
    hooks_result = await db.execute(
        select(ClientClip.hook_used, func.avg(ClientClip.total_views).label("avg_views"))
        .where(ClientClip.client_id == client_id)
        .where(ClientClip.status == ClipStatus.POSTED)
        .where(ClientClip.posted_at >= period_start)
        .where(ClientClip.posted_at < period_end)
        .where(ClientClip.hook_used.is_not(None))
        .group_by(ClientClip.hook_used)
        .order_by(desc("avg_views"))
        .limit(5)
    )
    best_hooks_json = [
        {"hook": row.hook_used, "avg_views": int(row.avg_views)}
        for row in hooks_result.all()
    ]

    # Auto-generate insights
    insights = _generate_insights(totals, top_clips_json, period_type)

    report = PerformanceReport(
        client_id=client_id,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        total_clips=totals.total_clips,
        total_views=totals.total_views,
        total_likes=totals.total_likes,
        total_comments=totals.total_comments,
        total_shares=totals.total_shares,
        top_clips_json=top_clips_json,
        best_hooks_json=best_hooks_json,
        insights_json=insights,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    logger.info(
        f"Built {period_type} report for client {client_id}: "
        f"{totals.total_clips} clips, {totals.total_views:,} views"
    )
    return report


def _generate_insights(totals, top_clips: list, period_type: str) -> dict:
    """Generate simple rule-based insights from the performance data."""
    insights = []

    if totals.total_clips == 0:
        insights.append({"type": "warning", "text": "No clips were posted this period."})
        return {"items": insights}

    avg_views = totals.total_views / totals.total_clips if totals.total_clips else 0
    engagement_rate = (
        (totals.total_likes + totals.total_comments + totals.total_shares) / totals.total_views * 100
        if totals.total_views > 0
        else 0
    )

    # Views insights
    if avg_views >= 100000:
        insights.append({"type": "success", "text": f"Averaging {avg_views:,.0f} views/clip — excellent performance."})
    elif avg_views >= 10000:
        insights.append({"type": "success", "text": f"Averaging {avg_views:,.0f} views/clip — solid results."})
    else:
        insights.append({"type": "warning", "text": f"Averaging {avg_views:,.0f} views/clip — room to improve hooks and posting times."})

    # Engagement insights
    if engagement_rate >= 5:
        insights.append({"type": "success", "text": f"{engagement_rate:.1f}% engagement rate — audience is highly engaged."})
    elif engagement_rate >= 2:
        insights.append({"type": "info", "text": f"{engagement_rate:.1f}% engagement rate — healthy."})
    else:
        insights.append({"type": "warning", "text": f"{engagement_rate:.1f}% engagement rate — consider stronger CTAs."})

    # Top clip insight
    if top_clips:
        best = top_clips[0]
        insights.append({
            "type": "info",
            "text": f"Top clip: \"{best['title']}\" with {best['views']:,} views.",
        })

    # Volume insight
    expected = 60 if period_type == "monthly" else 15
    if totals.total_clips >= expected:
        insights.append({"type": "success", "text": f"{totals.total_clips} clips posted — on track with delivery target."})
    else:
        insights.append({
            "type": "warning",
            "text": f"Only {totals.total_clips} clips posted vs ~{expected} target. Increase output.",
        })

    return {
        "items": insights,
        "avg_views_per_clip": round(avg_views),
        "engagement_rate": round(engagement_rate, 2),
    }


async def build_reports_for_all_clients(
    db: AsyncSession,
    operator_user_id: str,
    period_type: str,
    period_start: datetime,
    period_end: datetime,
) -> dict:
    """Build reports for all active clients of an operator."""
    from db.models_v2 import ClientStatus

    result = await db.execute(
        select(Client)
        .where(Client.user_id == operator_user_id)
        .where(Client.status == ClientStatus.ACTIVE)
    )
    clients = result.scalars().all()

    built = []
    errors = []
    for client in clients:
        try:
            report = await build_report(db, str(client.id), period_type, period_start, period_end)
            built.append({"client": client.name, "report_id": str(report.id)})
        except Exception as e:
            logger.error(f"Failed to build report for {client.name}: {e}")
            errors.append({"client": client.name, "error": str(e)})

    return {"built": built, "errors": errors, "period_type": period_type}
