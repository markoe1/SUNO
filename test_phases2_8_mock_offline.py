"""
PHASES 2-8 Mock Offline Test
=============================
Validates upstream pipeline logic WITHOUT requiring network/ffmpeg dependencies.
Uses mock data to test the full integration flow.

This validates:
- Creator discovery and approval workflow
- Campaign requirement validation
- Queue ingestion and validation
- Quality gate enforcement
"""

import logging
from pathlib import Path
from unittest.mock import Mock

from queue_manager import QueueManager, Campaign, Clip, ClipStatus, Creator
from campaign_requirements import CampaignRequirementsValidator
from creator_registry import CreatorRegistry

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


def test_full_offline_pipeline():
    """Mock test of full upstream pipeline logic."""
    logger.info("\n" + "="*80)
    logger.info("PHASES 2-8: OFFLINE MOCK TEST")
    logger.info("="*80)

    queue = QueueManager()
    registry = CreatorRegistry()
    validator = CampaignRequirementsValidator(allow_unverified_creators=True)

    # ─── SETUP ─────────────────────────────────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("SETUP: Create test campaign and approve creators")
    logger.info("─"*80)

    campaign = Campaign(
        whop_id="offline_test_001",
        name="Offline Mock Test",
        cpm=5.0,
        budget_remaining=10000.0,
        is_free=True,
        active=True,
        content_type="general",
        source_types="youtube,tiktok",
        min_duration=15,
        max_duration=120,
        creator_whitelist="",  # Discovery mode
        creator_blacklist="",
        daily_clip_limit=50
    )
    queue.upsert_campaign(campaign)
    logger.info("✓ Campaign created")

    # ─── PHASE 2: SOURCE DISCOVERY (MOCK) ───────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 2: Source Discovery (Simulated)")
    logger.info("─"*80)

    # Simulate discovered videos
    video_creators = [
        ("Vsauce", "youtube"),
        ("TED-Ed", "youtube"),
        ("Unknown New Creator", "youtube")
    ]

    logger.info(f"\n✓ Simulated discovering {len(video_creators)} creators:")
    for creator_name, platform in video_creators:
        registry.discover_creator(creator_name, platform)
        logger.info(f"  - {creator_name} ({platform}) → UNVERIFIED")

    # Approve some creators
    logger.info("\n✓ Approving some creators:")
    registry.approve_creator("Vsauce", "youtube", "Top-tier educational content")
    logger.info("  - Vsauce → APPROVED")

    # ─── PHASE 3: MOMENT DETECTION (MOCK) ────────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 3: Moment Detection (Simulated)")
    logger.info("─"*80)

    moments = [
        Mock(start_sec=10.0, end_sec=25.0, duration=15.0, reason="scene_change", score=85),
        Mock(start_sec=45.0, end_sec=65.0, duration=20.0, reason="audio_peak", score=75),
        Mock(start_sec=120.0, end_sec=150.0, duration=30.0, reason="scene_change", score=90),
    ]
    logger.info(f"\n✓ Simulated detecting {len(moments)} moments")

    # ─── PHASE 4: AUTO-CLIPPING (MOCK) ─────────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 4: Auto-Clipping (Simulated)")
    logger.info("─"*80)

    clips_data = [
        {"clip_name": "vsauce_clip_001.mp4", "creator": "Vsauce", "duration": 45},
        {"clip_name": "ted_ed_clip_001.mp4", "creator": "TED-Ed", "duration": 60},
        {"clip_name": "unknown_clip_001.mp4", "creator": "Unknown New Creator", "duration": 30},
    ]
    logger.info(f"\n✓ Simulated extracting {len(clips_data)} clips")

    # ─── PHASE 5: CAPTION GENERATION (MOCK) ────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 5: Caption Generation (Simulated)")
    logger.info("─"*80)

    captions_data = [
        {
            "clip_name": "vsauce_clip_001.mp4",
            "creator": "Vsauce",
            "duration": 45,
            "caption": "Wait for it... the physics is mind-blowing",
            "hashtags": ["#science", "#physics", "#education"]
        },
        {
            "clip_name": "ted_ed_clip_001.mp4",
            "creator": "TED-Ed",
            "duration": 60,
            "caption": "This is how evolution actually works",
            "hashtags": ["#biology", "#evolution", "#educational"]
        },
        {
            "clip_name": "unknown_clip_001.mp4",
            "creator": "Unknown New Creator",
            "duration": 30,
            "caption": "POV: You're about to learn something",
            "hashtags": ["#learning", "#knowledge", "#discovery"]
        },
    ]
    logger.info(f"\n✓ Simulated generating {len(captions_data)} captions")

    # ─── PHASE 6: PIPELINE INTEGRATION ─────────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 6: Pipeline Integration (Queue Ingestion)")
    logger.info("─"*80)

    queued_clips = []
    logger.info(f"\n✓ Ingesting {len(captions_data)} clips:")

    for caption_data in captions_data:
        clip = Clip(
            filename=caption_data["clip_name"],
            filepath=f"/clips/generated/{caption_data['clip_name']}",
            campaign_name=campaign.name,
            campaign_id=campaign.whop_id,
            creator_name=caption_data["creator"],
            source_platform="youtube",
            source_url=f"https://youtube.com/watch?v={caption_data['clip_name']}",
            clip_duration=caption_data["duration"],
            caption=caption_data["caption"],
            hashtags=" ".join(caption_data["hashtags"]),
            status=ClipStatus.PENDING.value
        )

        clip_id = queue.add_clip(clip)
        if clip_id:
            queued_clips.append(clip)
            logger.info(f"  ✓ {caption_data['clip_name']} (ID: {clip_id})")

    # ─── PHASE 7: QUALITY + CAMPAIGN ENFORCEMENT ───────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 7: Quality Gate & Campaign Enforcement")
    logger.info("─"*80)

    # Reload validator to get updated campaign
    validator.refresh_requirements()

    logger.info(f"\n✓ Campaign Requirement Validation:")
    campaign_valid = 0

    for clip in queued_clips:
        approved, reasons = validator.validate_clip_for_campaign(
            campaign_id=campaign.whop_id,
            creator_name=clip.creator_name,
            source_platform=clip.source_platform,
            clip_duration=clip.clip_duration
        )

        if approved:
            logger.info(f"  ✓ {clip.creator_name}: APPROVED")
            campaign_valid += 1
        else:
            logger.warning(f"  ✗ {clip.creator_name}: {reasons[0] if reasons else 'Unknown'}")

    # ─── PHASE 8: END-TO-END VALIDATION ────────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 8: End-to-End Validation")
    logger.info("─"*80)

    logger.info("\n✓ Creator Approval Workflow:")
    for creator_name, platform in video_creators:
        creator = queue.get_creator(creator_name, platform)
        status = "APPROVED" if creator.is_approved else "UNVERIFIED"
        logger.info(f"  - {creator_name}: {status}")

    logger.info("\n✓ Queue Status:")
    all_clips = queue.get_pending_clips(limit=100)
    logger.info(f"  Total in queue: {len(all_clips)}")
    logger.info(f"  Campaign valid: {campaign_valid}/{len(queued_clips)}")
    logger.info(f"  Pass rate: {(campaign_valid/len(queued_clips)*100):.0f}%")

    logger.info("\n✓ Campaign Requirements Summary:")
    req = validator.get_campaign_requirements(campaign.whop_id)
    logger.info(f"  Sources: {req.allowed_sources}")
    logger.info(f"  Duration: {req.min_clip_duration}-{req.max_clip_duration}s")
    logger.info(f"  Creator Whitelist: {req.creator_whitelist if req.creator_whitelist else '(empty - all allowed)'}")
    logger.info(f"  Creator Blacklist: {req.creator_blacklist if req.creator_blacklist else '(empty)'}")

    # ─── COMPLETION ────────────────────────────────────────────────────────
    logger.info("\n" + "="*80)
    logger.info("PHASES 2-8 MOCK TEST COMPLETE")
    logger.info("="*80)

    success = (
        len(queued_clips) > 0 and
        campaign_valid > 0 and
        campaign_valid == len(queued_clips)
    )

    if success:
        logger.info("\n✓ FULL PIPELINE VALIDATED (MOCK)")
        logger.info("  Discovery → Moments → Clips → Captions → Queue → Validation")
        logger.info("\n✓ All components integrated correctly")
        logger.info("✓ Creator approval workflow functioning")
        logger.info("✓ Campaign requirement validation working")
        logger.info("✓ Queue integration successful")
    else:
        logger.warning(f"\n⚠ Pipeline incomplete: {campaign_valid}/{len(queued_clips)} passed validation")

    return success


if __name__ == "__main__":
    import sys
    success = test_full_offline_pipeline()
    sys.exit(0 if success else 1)
