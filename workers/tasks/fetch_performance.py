"""RQ task: fetch real performance metrics from social platforms.

CURRENT STATUS: Framework implemented. Platform API calls are stubbed.

Platform API requirements
--------------------------

TikTok (TikTok for Developers — https://developers.tiktok.com)
  - Requires TikTok for Business account
  - OAuth 2.0 with scope: video.list
  - Endpoint: GET https://open.tiktokapis.com/v2/video/list/
  - Env: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET
  - Per-account OAuth tokens stored in DB (not yet implemented)

Instagram (Meta Graph API — https://developers.facebook.com/docs/instagram-api)
  - Requires Facebook Business Manager + Instagram Professional account
  - OAuth via Facebook Login
  - Endpoint: GET https://graph.facebook.com/v19.0/{media-id}/insights
  - Metrics: impressions, reach, likes, comments, shares, saved, plays
  - Env: META_APP_ID, META_APP_SECRET
  - Per-account access tokens stored in DB (not yet implemented)

YouTube (YouTube Data API v3 — https://developers.google.com/youtube/v3)
  - Requires Google Cloud project with YouTube Data API v3 enabled
  - OAuth 2.0 with scope: youtube.readonly
  - Endpoint: GET https://www.googleapis.com/youtube/v3/videos?part=statistics
  - Metrics: viewCount, likeCount, commentCount, favoriteCount
  - Env: YOUTUBE_API_KEY (for public stats) or GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET

To fully implement this worker:
  1. Set up the OAuth flows for each platform
  2. Store per-client access tokens in a new `platform_tokens` table
  3. Uncomment the API call stubs below and fill in real requests
"""

import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db.engine import DATABASE_URL
from db.models_v2 import Client, ClientClip, ClipStatus

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")


# ---------------------------------------------------------------------------
# URL parsing helpers
# ---------------------------------------------------------------------------

def _extract_youtube_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Platform fetchers (stubbed — see module docstring for implementation notes)
# ---------------------------------------------------------------------------

def _fetch_youtube_stats(video_id: str) -> Optional[dict]:
    """Fetch view/like/comment counts from YouTube Data API v3.

    Requires YOUTUBE_API_KEY env var. Public stats only (no OAuth needed
    for public videos).
    """
    if not YOUTUBE_API_KEY:
        logger.debug("YOUTUBE_API_KEY not set — skipping YouTube fetch for %s", video_id)
        return None

    try:
        resp = httpx.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "statistics",
                "id": video_id,
                "key": YOUTUBE_API_KEY,
            },
            timeout=10.0,
        )
        if resp.status_code != 200:
            logger.warning("YouTube API error %d for video %s", resp.status_code, video_id)
            return None

        data = resp.json()
        items = data.get("items", [])
        if not items:
            logger.warning("YouTube: video %s not found or private", video_id)
            return None

        stats = items[0].get("statistics", {})
        return {
            "total_views": int(stats.get("viewCount", 0)),
            "total_likes": int(stats.get("likeCount", 0)),
            "total_comments": int(stats.get("commentCount", 0)),
        }
    except Exception as exc:
        logger.error("YouTube fetch error for %s: %s", video_id, exc)
        return None


def _fetch_tiktok_stats(tiktok_url: str) -> Optional[dict]:
    """Stub: fetch TikTok video stats.

    TikTok's Content Posting API requires OAuth per account.
    Until per-client OAuth tokens are stored, this returns None.
    See module docstring for implementation notes.
    """
    logger.debug("TikTok fetch not implemented yet for %s", tiktok_url)
    return None


def _fetch_instagram_stats(instagram_url: str) -> Optional[dict]:
    """Stub: fetch Instagram Reel stats.

    Instagram Graph API requires OAuth per Business account.
    Until per-client OAuth tokens are stored, this returns None.
    See module docstring for implementation notes.
    """
    logger.debug("Instagram fetch not implemented yet for %s", instagram_url)
    return None


# ---------------------------------------------------------------------------
# Main worker logic
# ---------------------------------------------------------------------------

async def _fetch_performance_async(
    operator_user_id: str,
    client_id: Optional[str] = None,
) -> dict:
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)

    updated = 0
    skipped = 0
    errors = []

    async with AsyncSession() as db:
        # Get all POSTED clips with at least one platform URL
        query = (
            select(ClientClip, Client)
            .join(Client, ClientClip.client_id == Client.id)
            .where(Client.user_id == operator_user_id)
            .where(ClientClip.status == ClipStatus.POSTED)
        )
        if client_id:
            query = query.where(ClientClip.client_id == client_id)

        result = await db.execute(query)
        clips = result.all()

        logger.info("fetch_performance: checking %d posted clips", len(clips))

        for clip, client in clips:
            new_stats: dict = {}

            # YouTube — public API, works without OAuth
            if clip.youtube_url:
                vid_id = _extract_youtube_video_id(clip.youtube_url)
                if vid_id:
                    stats = _fetch_youtube_stats(vid_id)
                    if stats:
                        new_stats.update(stats)

            # TikTok — stubbed
            if clip.tiktok_url:
                stats = _fetch_tiktok_stats(clip.tiktok_url)
                if stats:
                    # Merge, taking the max (multiple platforms → add views)
                    new_stats["total_views"] = (
                        new_stats.get("total_views", 0) + stats.get("total_views", 0)
                    )
                    new_stats["total_likes"] = (
                        new_stats.get("total_likes", 0) + stats.get("total_likes", 0)
                    )

            # Instagram — stubbed
            if clip.instagram_url:
                stats = _fetch_instagram_stats(clip.instagram_url)
                if stats:
                    new_stats["total_views"] = (
                        new_stats.get("total_views", 0) + stats.get("total_views", 0)
                    )

            if new_stats:
                for key, value in new_stats.items():
                    setattr(clip, key, value)
                updated += 1
                logger.info(
                    "fetch_performance: updated clip %s — views=%s",
                    clip.id, new_stats.get("total_views"),
                )
            else:
                skipped += 1

        await db.commit()

    await engine.dispose()

    logger.info(
        "fetch_performance complete: %d updated, %d skipped, %d errors",
        updated, skipped, len(errors),
    )
    return {"updated": updated, "skipped": skipped, "errors": errors}


def fetch_performance(
    operator_user_id: str,
    client_id: Optional[str] = None,
) -> dict:
    """RQ entry point.

    Args:
        operator_user_id: UUID string of the operator whose clips to fetch stats for.
        client_id: Optional UUID string — if set, only fetch for this client.
    """
    return asyncio.run(_fetch_performance_async(operator_user_id, client_id))
