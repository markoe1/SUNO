"""
PHASES 2-8 Integration Test
============================
Complete upstream pipeline validation:
- Phase 2: Source Discovery (YouTube)
- Phase 3: Moment Detection
- Phase 4: Auto-Clipping
- Phase 5: Caption Generation
- Phase 6: Pipeline Integration
- Phase 7: Quality + Campaign Enforcement
- Phase 8: End-to-End Test

Tests the FULL autonomous pipeline: Discovery → Moments → Clips → Captions → Queue → Validation
"""

import logging
import asyncio
from pathlib import Path

from queue_manager import QueueManager, Campaign, Clip, ClipStatus
from campaign_requirements import CampaignRequirementsValidator
from creator_registry import CreatorRegistry
from youtube_discovery import YouTubeDiscovery
from moment_detector import MomentDetector
from auto_clipper import AutoClipper
from caption_generator import CaptionGenerator
from clip_pipeline import ClipPipeline
from quality_monitor import QualityMonitor

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)


async def test_full_upstream_pipeline():
    """PHASES 2-8: Complete upstream pipeline integration test."""
    logger.info("\n" + "="*80)
    logger.info("PHASES 2-8: UPSTREAM PIPELINE - INTEGRATION TEST")
    logger.info("="*80)

    # ─── SETUP ─────────────────────────────────────────────────────────────
    queue = QueueManager()
    registry = CreatorRegistry()
    validator = CampaignRequirementsValidator(allow_unverified_creators=True)
    quality_monitor = QualityMonitor()
    pipeline = ClipPipeline()

    logger.info("\n" + "─"*80)
    logger.info("SETUP: Create campaign with creator requirements")
    logger.info("─"*80)

    # Create test campaign
    campaign = Campaign(
        whop_id="upstream_test_001",
        name="Upstream Pipeline Test",
        cpm=5.0,
        budget_remaining=10000.0,
        is_free=True,
        active=True,
        content_type="general",
        source_types="youtube",
        min_duration=15,
        max_duration=120,
        creator_whitelist="",  # Empty = all creators allowed (discovery mode)
        creator_blacklist="",
        daily_clip_limit=50
    )
    queue.upsert_campaign(campaign)
    logger.info(f"✓ Campaign created: {campaign.name}")
    logger.info(f"  CPM: ${campaign.cpm}")
    logger.info(f"  Budget: ${campaign.budget_remaining}")
    logger.info(f"  Clip duration: {campaign.min_duration}-{campaign.max_duration}s")

    # ─── PHASE 2: SOURCE DISCOVERY ──────────────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 2: Source Discovery (YouTube)")
    logger.info("─"*80)

    discovery = YouTubeDiscovery(auto_register_creators=True)

    logger.info("\n[2a] Searching YouTube for test content")
    videos = discovery.search_query(
        "educational science",
        max_videos=1,
        min_duration_sec=60,
        max_duration_sec=900  # 15 minutes max for testing
    )

    if not videos:
        logger.warning("⚠ No videos found - skipping rest of pipeline")
        logger.warning("  (YouTube search requires working internet and yt-dlp)")
        return False

    logger.info(f"✓ Found {len(videos)} video(s)")
    video = videos[0]
    logger.info(f"  Title: {video.title}")
    logger.info(f"  Channel: {video.channel}")
    logger.info(f"  Duration: {video.duration}s")

    logger.info("\n[2b] Downloading video")
    downloaded = discovery.download_videos([video])

    if not downloaded:
        logger.warning("⚠ Could not download video - skipping rest of pipeline")
        return False

    video = downloaded[0]
    logger.info(f"✓ Downloaded: {Path(video.local_path).name}")
    logger.info(f"✓ Creator auto-registered: {video.channel} (youtube)")

    # Verify creator was registered
    creator = queue.get_creator(video.channel, "youtube")
    assert creator is not None
    logger.info(f"  Creator in registry: {creator.name} ({creator.platform})")
    logger.info(f"  Status: {creator.verification_status}")

    # ─── PHASE 3: MOMENT DETECTION ──────────────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 3: Moment Detection (Heuristic)")
    logger.info("─"*80)

    logger.info("\n[3a] Detecting moments in video")
    detector = MomentDetector()
    moments = detector.detect_moments(
        video.local_path,
        config={
            'scene_change_threshold': 0.3,
            'audio_threshold': 8.0,
            'min_duration': 3,
            'max_duration': 60
        }
    )

    if not moments:
        logger.warning("⚠ No moments detected - skipping clip extraction")
        logger.info("  (This is normal for videos without scene changes or audio variation)")
        return False

    logger.info(f"✓ Detected {len(moments)} moment(s)")
    for i, moment in enumerate(moments[:3], 1):  # Show first 3
        logger.info(
            f"  [{i}] {moment.start_sec:.1f}-{moment.end_sec:.1f}s "
            f"({moment.duration:.1f}s) - {moment.reason} (score: {moment.score:.0f})"
        )

    # ─── PHASE 4: AUTO-CLIPPING ────────────────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 4: Auto-Clipping (FFmpeg)")
    logger.info("─"*80)

    logger.info("\n[4a] Extracting clips from moments")
    clipper = AutoClipper()
    clip_paths = clipper.extract_clips_from_moments(
        video.local_path,
        moments[:3],  # Extract first 3 moments only for testing
        padding_sec=0.5,
        target_duration_sec=(15, 60)
    )

    if not clip_paths:
        logger.warning("⚠ No clips extracted - skipping rest of pipeline")
        return False

    logger.info(f"✓ Extracted {len(clip_paths)} clip(s)")
    for clip_path in clip_paths:
        size_mb = clip_path.stat().st_size / (1024 * 1024)
        logger.info(f"  - {clip_path.name} ({size_mb:.1f}MB)")

    logger.info("\n[4b] Validating clips")
    valid_clips = clipper.validate_clips(clip_paths)
    logger.info(f"✓ Validated {len(valid_clips)}/{len(clip_paths)} clips")

    if not valid_clips:
        logger.warning("⚠ No valid clips - skipping rest of pipeline")
        return False

    # ─── PHASE 5: CAPTION GENERATION ───────────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 5: Caption Generation (Claude Vision)")
    logger.info("─"*80)

    logger.info("\n[5a] Generating captions for clips")
    generator = CaptionGenerator()
    captions_data = []

    for i, clip_path in enumerate(valid_clips, 1):
        logger.info(f"\n  Generating caption [{i}/{len(valid_clips)}]: {clip_path.name}")

        caption_obj = generator.generate(
            clip_path=str(clip_path),
            source_title=video.title,
            moment_type="scene_change",
            creator_preferences={
                "style": "engaging, educational",
                "tone": "informative, friendly"
            }
        )

        if caption_obj:
            captions_data.append({
                'clip_path': clip_path,
                'caption': caption_obj.caption,
                'hashtags': caption_obj.hashtags,
            })
            logger.info(f"  ✓ Caption: {caption_obj.caption[:60]}...")
            logger.info(f"  ✓ Hashtags: {' '.join(caption_obj.hashtags)}")
        else:
            logger.warning(f"  ✗ Failed to generate caption")

    if not captions_data:
        logger.warning("⚠ No captions generated - skipping queue ingestion")
        return False

    logger.info(f"\n✓ Generated {len(captions_data)} caption(s)")

    # ─── PHASE 6: PIPELINE INTEGRATION ─────────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 6: Pipeline Integration (Queue Ingestion)")
    logger.info("─"*80)

    logger.info("\n[6a] Ingesting clips into queue")
    queued_count = 0

    for i, caption_data in enumerate(captions_data, 1):
        clip_path = caption_data['clip_path']
        logger.info(f"\n  Ingesting [{i}/{len(captions_data)}]: {clip_path.name}")

        # Create Clip object
        clip = Clip(
            filename=clip_path.name,
            filepath=str(clip_path),
            campaign_name=campaign.name,
            campaign_id=campaign.whop_id,
            creator_name=video.channel,
            source_platform="youtube",
            source_url=video.url,
            clip_duration=int(clip_path.stat().st_size / (1024 * 50)),  # Rough estimate
            caption=caption_data['caption'],
            hashtags=" ".join(caption_data['hashtags']),
            status=ClipStatus.PENDING.value
        )

        clip_id = queue.add_clip(clip)
        if clip_id:
            queued_count += 1
            logger.info(f"  ✓ Queued with ID: {clip_id}")
        else:
            logger.warning(f"  ✗ Failed to queue")

    logger.info(f"\n✓ Ingested {queued_count}/{len(captions_data)} clips into queue")

    # ─── PHASE 7: QUALITY + CAMPAIGN ENFORCEMENT ───────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 7: Quality Gate & Campaign Enforcement")
    logger.info("─"*80)

    logger.info("\n[7a] Getting pending clips from queue")
    pending = queue.get_pending_clips(limit=10)
    logger.info(f"✓ Found {len(pending)} pending clips")

    logger.info("\n[7b] Running quality validation")
    passed_quality = 0
    for clip in pending:
        score = quality_monitor.calculate_quality_score(clip)
        status = "✓ PASS" if score >= 70 else "✗ FAIL"
        logger.info(f"  {clip.filename}: {score:.0f}% {status}")

        if score >= 70:
            passed_quality += 1

    logger.info(f"\n✓ Quality validation: {passed_quality}/{len(pending)} passed (≥70%)")

    logger.info("\n[7c] Running campaign requirement validation")
    validator.refresh_requirements()
    campaign_valid = 0

    for clip in pending:
        approved, reasons = validator.validate_clip_for_campaign(
            campaign_id=campaign.whop_id,
            creator_name=clip.creator_name,
            source_platform=clip.source_platform,
            clip_duration=clip.clip_duration or 30
        )

        if approved:
            logger.info(f"  ✓ {clip.filename}: Meets campaign requirements")
            campaign_valid += 1
        else:
            logger.warning(f"  ✗ {clip.filename}: {reasons[0] if reasons else 'Unknown'}")

    logger.info(f"\n✓ Campaign validation: {campaign_valid}/{len(pending)} approved")

    # ─── PHASE 8: END-TO-END VALIDATION ────────────────────────────────────
    logger.info("\n" + "─"*80)
    logger.info("PHASE 8: End-to-End Validation")
    logger.info("─"*80)

    logger.info("\n[8a] Summary of upstream pipeline execution:")
    logger.info(f"  Videos discovered: 1")
    logger.info(f"  Videos downloaded: 1")
    logger.info(f"  Moments detected: {len(moments)}")
    logger.info(f"  Clips extracted: {len(valid_clips)}")
    logger.info(f"  Captions generated: {len(captions_data)}")
    logger.info(f"  Clips queued: {queued_count}")
    logger.info(f"  Quality passed: {passed_quality}/{len(pending)}")
    logger.info(f"  Campaign valid: {campaign_valid}/{len(pending)}")

    logger.info("\n[8b] Creator workflow validation:")
    creator_final = queue.get_creator(video.channel, "youtube")
    logger.info(f"  Creator: {creator_final.name} ({creator_final.platform})")
    logger.info(f"  Status: {creator_final.verification_status}")
    logger.info(f"  Clips extracted: {creator_final.clips_extracted}")

    # ─── COMPLETION ────────────────────────────────────────────────────────
    logger.info("\n" + "="*80)
    logger.info("PHASES 2-8 TEST COMPLETE")
    logger.info("="*80)

    success = (
        len(videos) > 0 and
        len(moments) > 0 and
        len(valid_clips) > 0 and
        len(captions_data) > 0 and
        queued_count > 0 and
        passed_quality > 0
    )

    if success:
        logger.info("\n🎉 UPSTREAM PIPELINE VALIDATED")
        logger.info("✓ Discovery → Moments → Clips → Captions → Queue → Quality → Ready for posting")
    else:
        logger.warning("\n⚠ Pipeline incomplete (network/dependencies issue)")
        logger.info("  See README for setup requirements (ffmpeg, yt-dlp, opencv, librosa)")

    return success


async def main():
    """Run integration test."""
    try:
        success = await test_full_upstream_pipeline()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
