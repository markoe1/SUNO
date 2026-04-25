#!/usr/bin/env python3
"""Analyze why a clip scored low on quality."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from quality_monitor import QualityMonitor

def analyze_clip():
    quality_monitor = QualityMonitor()
    clip_path = Path("clips/inbox/test_clip_01.mp4")
    caption = "This is an amazing moment you need to see! #viral #trending"

    print("\nCLIP QUALITY ANALYSIS")
    print("="*60)
    print(f"File: {clip_path}")
    print(f"Caption: {caption}\n")

    # Run assessment
    score = quality_monitor.assess_clip(str(clip_path), caption)

    print("QUALITY BREAKDOWN:")
    print(f"  File Integrity:  {score.file_integrity}/100")
    print(f"  Video Specs:     {score.video_specs}/100")
    print(f"  Caption Quality: {score.caption_quality}/100")
    print(f"  Metadata:        {score.metadata}/100")
    print(f"\n  Overall Score:   {score.overall_score}/100 (weighted avg)")
    print(f"  Approved:        {score.approved} (needs >= 70)\n")

    if score.issues:
        print("BLOCKING ISSUES:")
        for issue in score.issues:
            print(f"  - {issue}")

    if score.warnings:
        print("\nWARNINGS:")
        for warn in score.warnings:
            print(f"  - {warn}")

    print("\n" + "="*60)

if __name__ == "__main__":
    analyze_clip()
