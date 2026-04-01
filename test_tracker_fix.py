#!/usr/bin/env python3
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

    print("[TEST] Adding clip to database...")
    clip_id = queue.add_clip(clip)
    print(f"  OK: Clip created with ID {clip_id}")

    # Simulate successful YouTube post (PARTIAL status)
    print("\n[TEST] Updating clip to PARTIAL (YouTube only)...")
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

        print(f"  Status: {clip_db['status']}")
        print(f"  Posted_at: {clip_db['posted_at']}")
        print(f"  YouTube URL: {clip_db['youtube_url']}")

        if clip_db['posted_at']:
            print("  OK: posted_at is set for PARTIAL status")
        else:
            print("  FAIL: posted_at is NULL for PARTIAL status")
            return False

        if clip_db['youtube_url']:
            print("  OK: YouTube URL recorded")
        else:
            print("  FAIL: YouTube URL not recorded")
            return False

    # Verify tracker immediately shows the post
    print("\n[TEST] Checking tracker for today's stats...")
    today_stats = tracker.get_today_stats()

    print(f"  Clips downloaded: {today_stats.get('clips_downloaded')}")
    print(f"  Clips posted: {today_stats.get('clips_posted')}")
    print(f"  Total views: {today_stats.get('total_views')}")
    print(f"  Total earnings: ${today_stats.get('total_earnings'):.2f}")

    if today_stats.get('clips_posted', 0) >= 1:
        print("  OK: Tracker shows clip was posted")
    else:
        print("  FAIL: Tracker shows 0 clips posted")
        return False

    # Verify get_posted_clips includes PARTIAL clips
    print("\n[TEST] Verifying get_posted_clips includes PARTIAL status...")
    posted = queue.get_posted_clips(since_hours=1)
    if any(c.id == clip_id for c in posted):
        print(f"  OK: PARTIAL clip found in get_posted_clips ({len(posted)} total)")
    else:
        print(f"  FAIL: PARTIAL clip not found in get_posted_clips")
        return False

    # Verify get_clips_needing_submission includes PARTIAL clips
    print("\n[TEST] Verifying get_clips_needing_submission includes PARTIAL status...")
    for_submission = queue.get_clips_needing_submission()
    if any(c.id == clip_id for c in for_submission):
        print(f"  OK: PARTIAL clip found in get_clips_needing_submission ({len(for_submission)} total)")
    else:
        print(f"  FAIL: PARTIAL clip not found in get_clips_needing_submission")
        return False

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("TRACKER FIX VERIFICATION")
    print("=" * 60)
    print()

    success = test_tracker_records_partial_posts()

    print()
    print("=" * 60)
    if success:
        print("RESULT: ALL TESTS PASSED - Tracker is working correctly")
        print("  - posted_at is set for PARTIAL clips")
        print("  - Tracker immediately shows posted clips")
        print("  - get_posted_clips includes PARTIAL status")
        print("  - get_clips_needing_submission includes PARTIAL status")
    else:
        print("RESULT: TEST FAILED - Fix needed")
    print("=" * 60)
