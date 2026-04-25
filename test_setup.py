#!/usr/bin/env python3
"""Quick test setup: Add clip to database for testing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from queue_manager import QueueManager, Clip, ClipStatus

def setup_test_clip():
    """Add a test clip to the queue."""
    queue = QueueManager()

    # Create a test clip
    clip = Clip(
        whop_clip_id="test_001",
        campaign_name="Test Campaign",
        campaign_id="test_campaign",
        filename="test_clip_01.mp4",
        filepath=str(Path(__file__).parent / "clips" / "inbox" / "test_clip_01.mp4"),
        caption="This is an amazing moment you need to see! #viral #trending",
        hashtags="#fyp #foryou #viral #trending #mustwatch",
        status=ClipStatus.PENDING.value,
    )

    # Insert into DB
    queue.add_clip(clip)

    print("[OK] Test clip added to database")
    print(f"   File: {clip.filepath}")
    print(f"   Caption: {clip.caption}")
    print(f"   Status: PENDING (ready to post)")

if __name__ == "__main__":
    setup_test_clip()
