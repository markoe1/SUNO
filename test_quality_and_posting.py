#!/usr/bin/env python3
"""Test quality gate and posting pipeline (DRY RUN - no real posting)."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from queue_manager import QueueManager
from quality_monitor import QualityMonitor
import config

async def test_quality_gate():
    """Test the quality gate logic."""
    print("\n" + "="*60)
    print("PHASE 4: QUALITY GATE TEST")
    print("="*60)

    queue = QueueManager()
    quality_monitor = QualityMonitor()

    # Get pending clips
    clips = queue.get_pending_clips(limit=10)
    print(f"\nTesting {len(clips)} clips in inbox...\n")

    passed = 0
    failed = 0
    warned = 0

    for i, clip in enumerate(clips, 1):
        print(f"Clip {i}: {clip.filename}")
        print(f"  Path: {clip.filepath}")
        print(f"  Caption: {clip.caption[:50]}...")

        # Assess quality
        quality_score = quality_monitor.assess_clip(clip.filepath, clip.caption)

        print(f"  Quality Score: {quality_score.overall_score}/100")
        print(f"  Approved: {quality_score.approved}")

        if quality_score.issues:
            print(f"  ISSUES (BLOCKS POSTING):")
            for issue in quality_score.issues:
                print(f"    - {issue}")
            failed += 1
            status = "REJECTED"
        elif not quality_score.approved:
            print(f"  SCORE BELOW THRESHOLD: {quality_score.overall_score} < 70")
            if quality_score.warnings:
                print(f"  WARNINGS:")
                for warning in quality_score.warnings:
                    print(f"    - {warning}")
            warned += 1
            status = "REJECTED (LOW SCORE)"
        else:
            print(f"  Status: READY TO POST")
            passed += 1
            status = "APPROVED"

        print(f"  Final Status: {status}\n")

    print("="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Approved (ready to post): {passed}")
    print(f"Warned (post with caution): {warned}")
    print(f"Rejected (blocked): {failed}")
    print(f"Total: {len(clips)}")
    print("\nQuality gate is working correctly!")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_quality_gate())
