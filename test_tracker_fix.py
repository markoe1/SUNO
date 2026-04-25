#!/usr/bin/env python3
logger = logging.getLogger(__name__)
"""
Tracker Fix Verification
========================
Test that earnings tracker immediately records successful YouTube posts.
"""

from datetime import datetime
from queue_manager import QueueManager, Clip, ClipStatus
from earnings_tracker import EarningsTracker

def test_tracker_records_partial_posts():
    """Verify posted_at is set for PARTIAL status clips."""
    queue = QueueManager()
    tracker = EarningsTracker()

    # Create test clip
    clip = Clip(
        filename="test_clip.mp4",
        filepath="/tmp/test_clip.mp4",
        caption="Test clip",
        hashtags="#test",
        status=ClipStatus.PENDING.value,
        whop_clip_id=f"test_{int(datetime.now().timestamp() * 1000)}",
    )

    logger.info("[TEST] Adding clip to database...")
    clip_id = queue.add_clip(clip)
    logger.info(f"  OK: Clip created with ID {clip_id}")

    # Simulate successful YouTube post (PARTIAL status)
    logger.info("\n[TEST] Updating clip to PARTIAL (YouTube only)...")
    queue.update_clip_status(
        clip_id,
        ClipStatus.PARTIAL,
        youtube_url="https://www.youtube.com/shorts/test123"
    )

    # Verify posted_at is now set
    import sqlite3
    with sqlite3.connect(queue.db_path) as conn:
        conn.row_factory = sqlite3.Row
        clip_db = conn.execute(
            "SELECT id, status, posted_at, youtube_url FROM clips WHERE id = ?",
            (clip_id,)
        ).fetchone()

        logger.info(f"  Status: {clip_db['status']}")
        logger.info(f"  Posted_at: {clip_db['posted_at']}")
        logger.info(f"  YouTube URL: {clip_db['youtube_url']}")

        if clip_db['posted_at']:
            logger.info("  OK: posted_at is set for PARTIAL status")
        else:
            logger.info("  FAIL: posted_at is NULL for PARTIAL status")
            return False

        if clip_db['youtube_url']:
            logger.info("  OK: YouTube URL recorded")
        else:
            logger.info("  FAIL: YouTube URL not recorded")
            return False

    # Verify tracker immediately shows the post
    logger.info("\n[TEST] Checking tracker for today's stats...")
    today_stats = tracker.get_today_stats()

    logger.info(f"  Clips downloaded: {today_stats.get('clips_downloaded')}")
    logger.info(f"  Clips posted: {today_stats.get('clips_posted')}")
    logger.info(f"  Total views: {today_stats.get('total_views')}")
    logger.info(f"  Total earnings: ${today_stats.get('total_earnings'):.2f}")

    if today_stats.get('clips_posted', 0) >= 1:
        logger.info("  OK: Tracker shows clip was posted")
    else:
        logger.info("  FAIL: Tracker shows 0 clips posted")
        return False

    # Verify get_posted_clips includes PARTIAL clips
    logger.info("\n[TEST] Verifying get_posted_clips includes PARTIAL status...")
    posted = queue.get_posted_clips(since_hours=1)
    if any(c.id == clip_id for c in posted):
        logger.info(f"  OK: PARTIAL clip found in get_posted_clips ({len(posted)} total)")
    else:
        logger.info(f"  FAIL: PARTIAL clip not found in get_posted_clips")
        return False

    # Verify get_clips_needing_submission includes PARTIAL clips
    logger.info("\n[TEST] Verifying get_clips_needing_submission includes PARTIAL status...")
    for_submission = queue.get_clips_needing_submission()
    if any(c.id == clip_id for c in for_submission):
        logger.info(f"  OK: PARTIAL clip found in get_clips_needing_submission ({len(for_submission)} total)")
    else:
        logger.info(f"  FAIL: PARTIAL clip not found in get_clips_needing_submission")
        return False

    return True


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("TRACKER FIX VERIFICATION")
    logger.info("=" * 60)
    logger.info()

    success = test_tracker_records_partial_posts()

    logger.info()
    logger.info("=" * 60)
    if success:
        logger.info("RESULT: ALL TESTS PASSED - Tracker is working correctly")
        logger.info("  - posted_at is set for PARTIAL clips")
        logger.info("  - Tracker immediately shows posted clips")
        logger.info("  - get_posted_clips includes PARTIAL status")
        logger.info("  - get_clips_needing_submission includes PARTIAL status")
    else:
        logger.info("RESULT: TEST FAILED - Fix needed")
    logger.info("=" * 60)
