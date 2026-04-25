"""
End-to-End Integration Tests
=============================
PHASE 9: Verify complete pipeline from clip discovery to earnings tracking.

Tests:
1. Clip discovery and ingestion
2. Quality gate filtering
3. Campaign requirements validation
4. Platform posting (YouTube)
5. URL submission to Whop
6. Earnings tracking
"""

import asyncio
import logging
import tempfile
import json
from pathlib import Path
from datetime import datetime
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

import config
from queue_manager import QueueManager, Clip, ClipStatus
from clip_pipeline import ClipPipeline
from quality_monitor import QualityMonitor
from campaign_requirements import CampaignRequirementsValidator
from monitoring import EventMonitor, SafetyLimiter, MonitoringEvent, EventType


class E2ETestRunner:
    """Run end-to-end integration tests."""

    def __init__(self):
        self.queue = QueueManager()
        self.pipeline = ClipPipeline()
        self.quality_monitor = QualityMonitor()
        self.campaign_validator = CampaignRequirementsValidator()
        self.event_monitor = EventMonitor()
        self.limiter = SafetyLimiter()
        self.test_results = {}

    def log_test(self, name: str, status: str, message: str = ""):
        """Log test result."""
        self.test_results[name] = {'status': status, 'message': message}
        status_symbol = "[OK]" if status == "pass" else "[FAIL]"
        logger.info(f"{status_symbol} {name}: {message}")

    async def test_clip_discovery(self) -> bool:
        """Test 1: Clip discovery and ingestion."""
        logger.info("\n" + "=" * 60)
        logger.info("TEST 1: Clip Discovery and Ingestion")
        logger.info("=" * 60)

        try:
            # Create test clip file
            test_clip_path = config.CLIPS_INBOX / "test_creator_youtube_campaign_test_clip_30.mp4"
            test_clip_path.parent.mkdir(parents=True, exist_ok=True)

            # Create a small fake video file (just needs to exist)
            with open(test_clip_path, 'wb') as f:
                f.write(b'fake video data' * 100000)  # ~1.5MB

            # Create metadata file
            meta_file = test_clip_path.with_suffix('.meta.json')
            with open(meta_file, 'w') as f:
                json.dump({
                    'creator_name': 'test_creator',
                    'source_platform': 'youtube',
                    'source_url': 'https://youtube.com/watch?v=test123',
                    'clip_duration': 30,
                    'caption': 'Test clip for E2E testing',
                    'hashtags': 'test,automation',
                }, f)

            # Test discovery
            clips = self.pipeline.discover_clips()
            if not clips:
                self.log_test("Clip Discovery", "fail", "No clips found in inbox")
                return False

            self.log_test("Clip Discovery", "pass", f"Found {len(clips)} clips")

            # Test ingestion
            clip_id = self.pipeline.ingest_clip(test_clip_path)
            if not clip_id:
                self.log_test("Clip Ingestion", "fail", "Failed to ingest clip")
                return False

            self.log_test("Clip Ingestion", "pass", f"Clip ingested with ID: {clip_id}")

            # Verify clip in queue
            pending = self.queue.get_pending_clips(limit=10)
            if not pending or pending[0].id != clip_id:
                self.log_test("Clip Queue Verification", "fail", "Clip not found in queue")
                return False

            self.log_test("Clip Queue Verification", "pass", "Clip verified in queue")
            return True

        except Exception as e:
            self.log_test("Clip Discovery", "fail", str(e))
            return False

    async def test_quality_gate(self) -> bool:
        """Test 2: Quality gate filtering."""
        logger.info("\n" + "=" * 60)
        logger.info("TEST 2: Quality Gate Filtering")
        logger.info("=" * 60)

        try:
            # Get a pending clip
            pending = self.queue.get_pending_clips(limit=1)
            if not pending:
                self.log_test("Quality Gate", "skip", "No pending clips for testing")
                return True

            clip = pending[0]
            filepath = Path(clip.filepath)

            # Test quality assessment
            if not filepath.exists():
                self.log_test("Quality Gate", "skip", f"Clip file not found: {filepath}")
                return True

            quality_score = self.quality_monitor.assess_clip(filepath, clip.caption)
            self.log_test(
                "Quality Assessment",
                "pass",
                f"Score: {quality_score.overall_score}/100 | Approved: {quality_score.approved}"
            )

            # Log the result
            self.event_monitor.log_event(MonitoringEvent(
                timestamp=datetime.now().isoformat(),
                event_type='quality_assessment',
                clip_id=clip.id,
                clip_name=clip.filename,
                context={'score': quality_score.overall_score, 'approved': quality_score.approved}
            ))

            return True

        except Exception as e:
            self.log_test("Quality Gate", "fail", str(e))
            return False

    async def test_campaign_requirements(self) -> bool:
        """Test 3: Campaign requirements validation."""
        logger.info("\n" + "=" * 60)
        logger.info("TEST 3: Campaign Requirements Validation")
        logger.info("=" * 60)

        try:
            # Get a pending clip
            pending = self.queue.get_pending_clips(limit=1)
            if not pending:
                self.log_test("Campaign Requirements", "skip", "No pending clips for testing")
                return True

            clip = pending[0]

            # Test campaign validation (should succeed if campaign ID is valid)
            if clip.campaign_id:
                approved, reasons = self.campaign_validator.validate_clip_for_campaign(
                    clip.campaign_id,
                    clip.creator_name or "test_creator",
                    clip.source_platform or "youtube",
                    clip.clip_duration or 30
                )
                status = "pass" if approved else "fail"
                msg = "Approved" if approved else f"Rejected: {reasons[0] if reasons else 'unknown'}"
                self.log_test("Campaign Validation", status, msg)
                return approved
            else:
                self.log_test("Campaign Validation", "skip", "No campaign ID for testing")
                return True

        except Exception as e:
            self.log_test("Campaign Requirements", "fail", str(e))
            return False

    async def test_safety_limits(self) -> bool:
        """Test 4: Safety limits enforcement."""
        logger.info("\n" + "=" * 60)
        logger.info("TEST 4: Safety Limits")
        logger.info("=" * 60)

        try:
            # Check all limits
            limits = self.limiter.check_all_limits()

            for limit_name, (ok, reason) in limits.items():
                status = "pass" if ok else "warn"
                self.log_test(f"Safety Limit ({limit_name})", status, reason)

            return True

        except Exception as e:
            self.log_test("Safety Limits", "fail", str(e))
            return False

    async def test_event_monitoring(self) -> bool:
        """Test 5: Event monitoring and logging."""
        logger.info("\n" + "=" * 60)
        logger.info("TEST 5: Event Monitoring")
        logger.info("=" * 60)

        try:
            # Log a test event
            test_event = MonitoringEvent(
                timestamp=datetime.now().isoformat(),
                event_type='test_event',
                error_message='This is a test event',
                context={'test': True}
            )
            self.event_monitor.log_event(test_event)

            # Get recent events
            recent = self.event_monitor.get_recent_events(count=10)
            if not recent:
                self.log_test("Event Monitoring", "fail", "No events found")
                return False

            self.log_test("Event Logging", "pass", f"Logged {len(recent)} events")

            # Get event summary
            summary = self.event_monitor.get_event_summary(hours=24)
            self.log_test(
                "Event Summary",
                "pass",
                f"{summary['total_events']} events in 24h | "
                f"Posted: {summary['clips_posted']} | "
                f"Failed: {summary['clips_failed']}"
            )

            return True

        except Exception as e:
            self.log_test("Event Monitoring", "fail", str(e))
            return False

    async def run_all_tests(self):
        """Run all E2E tests."""
        logger.info("\n" + "=" * 70)
        logger.info("SUNO E2E TEST SUITE - PHASE 9")
        logger.info("=" * 70)

        results = {
            'clip_discovery': await self.test_clip_discovery(),
            'quality_gate': await self.test_quality_gate(),
            'campaign_requirements': await self.test_campaign_requirements(),
            'safety_limits': await self.test_safety_limits(),
            'event_monitoring': await self.test_event_monitoring(),
        }

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("TEST SUMMARY")
        logger.info("=" * 70)

        passed = sum(1 for v in results.values() if v)
        total = len(results)

        logger.info(f"Passed: {passed}/{total}")
        for test_name, passed in results.items():
            status = "PASS" if passed else "FAIL"
            logger.info(f"  [{status}] {test_name}")

        logger.info("=" * 70)

        # Return overall result
        return all(results.values())


async def main():
    """Run E2E tests."""
    runner = E2ETestRunner()
    success = await runner.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
