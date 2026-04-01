#!/usr/bin/env python3
"""
SUNO MVP Status Verification
=============================
Quick check that all core MVP pieces are in place and working.
No browser automation, no external dependencies.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import config
from queue_manager import QueueManager, Clip, ClipStatus
from earnings_tracker import EarningsTracker
from services.whop_client import WhopClient


def verify_database():
    """Verify database schema is correct."""
    print("\n[DATABASE SCHEMA]")
    queue = QueueManager()

    with sqlite3.connect(queue.db_path) as conn:
        cursor = conn.cursor()

        # Check clips table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clips'")
        if cursor.fetchone():
            print("  OK: clips table exists")
        else:
            print("  FAIL: clips table missing")
            return False

        # Check columns
        cursor.execute("PRAGMA table_info(clips)")
        columns = {row[1] for row in cursor.fetchall()}
        required_cols = {'posted_at', 'youtube_url', 'status', 'downloaded_at'}
        if required_cols.issubset(columns):
            print(f"  OK: All required columns present")
        else:
            print(f"  FAIL: Missing columns: {required_cols - columns}")
            return False

    return True


def verify_tracker_tracking():
    """Verify tracker can record clips correctly."""
    print("\n[TRACKER FUNCTIONALITY]")
    queue = QueueManager()
    tracker = EarningsTracker()

    # Create a test clip
    clip = Clip(
        filename="verify_test.mp4",
        filepath="/tmp/verify_test.mp4",
        caption="Verification test",
        hashtags="#test",
        status=ClipStatus.PENDING.value,
        whop_clip_id=f"verify_{int(datetime.now().timestamp() * 1000)}",
    )

    clip_id = queue.add_clip(clip)
    print(f"  Created clip ID {clip_id}")

    # Update to PARTIAL (YouTube success)
    queue.update_clip_status(
        clip_id,
        ClipStatus.PARTIAL,
        youtube_url="https://www.youtube.com/shorts/verify_test"
    )

    # Verify posted_at is set
    with sqlite3.connect(queue.db_path) as conn:
        conn.row_factory = sqlite3.Row
        clip_db = conn.execute(
            "SELECT posted_at, status FROM clips WHERE id = ?",
            (clip_id,)
        ).fetchone()

        if clip_db['posted_at']:
            print(f"  OK: posted_at set for PARTIAL status")
        else:
            print(f"  FAIL: posted_at is NULL")
            return False

    # Verify tracker counts it
    today_stats = tracker.get_today_stats()
    if today_stats.get('clips_posted', 0) > 0:
        print(f"  OK: Tracker counts clips_posted = {today_stats['clips_posted']}")
    else:
        print(f"  FAIL: Tracker shows clips_posted = 0")
        return False

    return True


def verify_submission_pipeline():
    """Verify clips can be retrieved for Whop submission."""
    print("\n[WHOP SUBMISSION PIPELINE]")
    queue = QueueManager()

    # Check if any PARTIAL clips exist
    partial_clips = queue.get_clips_needing_submission()
    if partial_clips:
        print(f"  OK: Found {len(partial_clips)} clips ready for submission")
        print(f"      (includes PARTIAL status)")
    else:
        print(f"  INFO: No clips ready for submission (create one first)")

    return True


def verify_whop_connection():
    """Verify Whop API connection works."""
    print("\n[WHOP API CONNECTION]")

    if not config.WHOP_API_KEY:
        print("  FAIL: WHOP_API_KEY not set in .env")
        return False

    try:
        client = WhopClient()
        campaigns = client.list_campaigns()
        print(f"  OK: Whop API connected")
        print(f"      Campaigns: {len(campaigns)}")

        if len(campaigns) == 0:
            print(f"      Status: No campaigns yet (expected for first launch)")
            print(f"      Action: Create campaign in Whop dashboard")
        else:
            print(f"      Status: Ready for submissions")

        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def verify_config():
    """Verify configuration is set up."""
    print("\n[CONFIGURATION]")

    checks = [
        ("CLIPS_INBOX", config.CLIPS_INBOX),
        ("CLIPS_POSTED", config.CLIPS_POSTED),
        ("DB_PATH", config.DB_PATH),
        ("CPM_RATE", f"${config.CPM_RATE:.2f}"),
    ]

    for name, value in checks:
        print(f"  {name}: {value}")

    if config.CLIPS_INBOX.exists():
        clips = list(config.CLIPS_INBOX.glob("*.mp4"))
        print(f"  Clips in inbox: {len(clips)}")

    return True


def main():
    """Run all verifications."""
    print("=" * 70)
    print("SUNO MVP STATUS VERIFICATION")
    print("=" * 70)

    results = {
        "Database Schema": verify_database(),
        "Tracker Tracking": verify_tracker_tracking(),
        "Submission Pipeline": verify_submission_pipeline(),
        "Whop Connection": verify_whop_connection(),
        "Configuration": verify_config(),
    }

    print("\n" + "=" * 70)
    print("VERIFICATION RESULTS")
    print("=" * 70)

    for check, passed in results.items():
        status = "PASS" if passed else "FAIL"
        symbol = "Y" if passed else "N"
        print(f"  [{symbol}] {check:<30} [{status}]")

    all_passed = all(results.values())
    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)

    print(f"\nResult: {passed_count}/{total_count} checks passed")
    print()

    if all_passed:
        print("*** SUNO IS MVP-READY ***")
        print("    All core components verified and functional")
        print("    Ready for deployment\n")
        return 0
    else:
        print("!!! SOME CHECKS FAILED !!!")
        print("    See above for details\n")
        return 1


if __name__ == "__main__":
    exit(main())
