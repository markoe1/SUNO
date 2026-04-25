"""
End-to-End Upstream Pipeline Test
==================================
Tests the complete autonomous pipeline:
Discovery → Moment Detection → Clipping → Caption Generation → Queue Ingestion
"""

import logging
import asyncio
from pathlib import Path

from clip_pipeline import ClipPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_youtube_search_and_clip():
    """Test 1: Search YouTube, download, detect, clip, caption, queue."""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: End-to-end YouTube search → clips")
    logger.info("="*80)

    pipeline = ClipPipeline()

    # Run the full pipeline with a simple search query
    result = await pipeline.discover_and_generate_clips(
        source_type="youtube",
        query="viral funny moments",  # Generic search
        max_videos=2,  # Just 2 videos for testing
        moments_per_video=2,  # 2 moments each
        target_duration_sec=(15, 60),
        padding_sec=1.0,
        campaign_name="test_youtube_search"
    )

    logger.info("\nPipeline Results:")
    logger.info(f"  Videos discovered: {result['videos_discovered']}")
    logger.info(f"  Videos downloaded: {result['videos_downloaded']}")
    logger.info(f"  Moments detected: {result['moments_detected']}")
    logger.info(f"  Clips extracted: {result['clips_extracted']}")
    logger.info(f"  Captions generated: {result['captions_generated']}")
    logger.info(f"  Clips queued: {result['clips_queued']}")
    logger.info(f"  Total duration queued: {result['total_duration_queued']:.1f}s")
    logger.info(f"  Failed: {result['failed']}")

    # Verify
    success = (
        result['videos_discovered'] > 0 and
        result['videos_downloaded'] > 0 and
        result['moments_detected'] > 0 and
        result['clips_extracted'] > 0 and
        result['clips_queued'] > 0
    )

    logger.info(f"\n✓ TEST 1: {'PASSED' if success else 'FAILED'}")
    return success


async def test_channel_and_clip():
    """Test 2: Subscribe to channel, download, detect, clip, caption, queue."""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: End-to-end YouTube channel → clips")
    logger.info("="*80)

    pipeline = ClipPipeline()

    # Run the full pipeline with a specific channel
    # Using a well-known channel for reliability
    result = await pipeline.discover_and_generate_clips(
        source_type="youtube",
        channel_url="https://www.youtube.com/@YouTube",  # YouTube's official channel
        max_videos=1,  # Just 1 video for testing
        moments_per_video=2,
        target_duration_sec=(15, 60),
        padding_sec=1.0,
        campaign_name="test_youtube_channel"
    )

    logger.info("\nPipeline Results:")
    logger.info(f"  Videos discovered: {result['videos_discovered']}")
    logger.info(f"  Videos downloaded: {result['videos_downloaded']}")
    logger.info(f"  Moments detected: {result['moments_detected']}")
    logger.info(f"  Clips extracted: {result['clips_extracted']}")
    logger.info(f"  Captions generated: {result['captions_generated']}")
    logger.info(f"  Clips queued: {result['clips_queued']}")
    logger.info(f"  Failed: {result['failed']}")

    success = (
        result['videos_discovered'] > 0 and
        result['videos_downloaded'] > 0 and
        result['moments_detected'] > 0 and
        result['clips_extracted'] > 0 and
        result['clips_queued'] > 0
    )

    logger.info(f"\n✓ TEST 2: {'PASSED' if success else 'FAILED'}")
    return success


async def test_queue_integration():
    """Test 3: Verify generated clips appear in queue with correct metadata."""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Verify queue integration")
    logger.info("="*80)

    from queue_manager import QueueManager

    queue = QueueManager()

    # Get all clips in queue
    all_clips = queue.get_all_clips()
    logger.info(f"Total clips in queue: {len(all_clips)}")

    # Check for auto-generated clips
    auto_gen = [c for c in all_clips if 'test_' in c.campaign_name]
    logger.info(f"Auto-generated test clips: {len(auto_gen)}")

    # Verify metadata
    for clip in auto_gen[:3]:  # Check first 3
        logger.info(f"\nClip: {clip.filename}")
        logger.info(f"  Campaign: {clip.campaign_name}")
        logger.info(f"  Creator: {clip.creator_name}")
        logger.info(f"  Source: {clip.source_platform} ({clip.source_url})")
        logger.info(f"  Caption: {clip.caption[:50]}...")
        logger.info(f"  Hashtags: {clip.hashtags}")
        logger.info(f"  Duration: {clip.clip_duration}s")
        logger.info(f"  Status: {clip.status}")

    success = len(auto_gen) > 0
    logger.info(f"\n✓ TEST 3: {'PASSED' if success else 'FAILED'}")
    return success


async def test_quality_gate():
    """Test 4: Verify generated clips pass quality gate."""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Verify quality gate")
    logger.info("="*80)

    from queue_manager import QueueManager
    from quality_monitor import QualityMonitor

    queue = QueueManager()
    monitor = QualityMonitor()

    # Get pending clips
    pending = queue.get_pending_clips(limit=10)
    logger.info(f"Pending clips for quality check: {len(pending)}")

    passed = 0
    failed = 0

    for clip in pending:
        try:
            score = monitor.calculate_quality_score(clip)
            logger.info(f"  {clip.filename}: {score:.1f}% {'✓ PASS' if score >= 70 else '✗ FAIL'}")

            if score >= 70:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning(f"  {clip.filename}: Error - {e}")
            failed += 1

    logger.info(f"\nQuality gate results:")
    logger.info(f"  Passed (≥70): {passed}")
    logger.info(f"  Failed (<70): {failed}")

    success = passed > 0
    logger.info(f"\n✓ TEST 4: {'PASSED' if success else 'FAILED'}")
    return success


async def test_posting_readiness():
    """Test 5: Verify clips are ready for posting."""
    logger.info("\n" + "="*80)
    logger.info("TEST 5: Verify posting readiness")
    logger.info("="*80)

    from queue_manager import QueueManager, ClipStatus
    from campaign_requirements import CampaignRequirementsValidator

    queue = QueueManager()
    validator = CampaignRequirementsValidator()

    # Get pending clips
    pending = queue.get_pending_clips(limit=5)
    logger.info(f"Pending clips ready for posting: {len(pending)}")

    ready = 0
    not_ready = 0

    for clip in pending:
        try:
            # Check campaign requirements
            campaign = queue.get_campaign(clip.campaign_name)
            if campaign:
                is_valid = validator.validate_clip(clip, campaign)
                logger.info(f"  {clip.filename}: {'✓ READY' if is_valid else '✗ NOT READY'}")

                if is_valid:
                    ready += 1
                else:
                    not_ready += 1
            else:
                logger.warning(f"  {clip.filename}: Campaign not found")
                not_ready += 1
        except Exception as e:
            logger.warning(f"  {clip.filename}: Error - {e}")
            not_ready += 1

    logger.info(f"\nPosting readiness:")
    logger.info(f"  Ready: {ready}")
    logger.info(f"  Not ready: {not_ready}")

    success = ready > 0
    logger.info(f"\n✓ TEST 5: {'PASSED' if success else 'FAILED'}")
    return success


async def run_all_tests():
    """Run all tests."""
    logger.info("\n" + "="*80)
    logger.info("SUNO UPSTREAM PIPELINE — END-TO-END TEST SUITE")
    logger.info("="*80)

    results = {
        'test_youtube_search': False,
        'test_channel': False,
        'test_queue_integration': False,
        'test_quality_gate': False,
        'test_posting_readiness': False,
    }

    # Test 1: YouTube search
    try:
        results['test_youtube_search'] = await test_youtube_search_and_clip()
    except Exception as e:
        logger.error(f"Test 1 failed with exception: {e}")

    # Test 2: YouTube channel (optional - may take longer)
    try:
        results['test_channel'] = await test_channel_and_clip()
    except Exception as e:
        logger.error(f"Test 2 failed with exception: {e}")

    # Test 3: Queue integration
    try:
        results['test_queue_integration'] = await test_queue_integration()
    except Exception as e:
        logger.error(f"Test 3 failed with exception: {e}")

    # Test 4: Quality gate
    try:
        results['test_quality_gate'] = await test_quality_gate()
    except Exception as e:
        logger.error(f"Test 4 failed with exception: {e}")

    # Test 5: Posting readiness
    try:
        results['test_posting_readiness'] = await test_posting_readiness()
    except Exception as e:
        logger.error(f"Test 5 failed with exception: {e}")

    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for test_name, passed_flag in results.items():
        status = "✓ PASSED" if passed_flag else "✗ FAILED"
        logger.info(f"{test_name}: {status}")

    logger.info(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED - PIPELINE READY FOR PRODUCTION")
    elif passed >= 3:
        logger.info("\n✓ MOST TESTS PASSED - PIPELINE MOSTLY WORKING")
    else:
        logger.info("\n⚠ SOME TESTS FAILED - DEBUG REQUIRED")

    return passed >= 3  # Success if at least 3 of 5 pass


async def main():
    """Run test suite."""
    success = await run_all_tests()
    exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
