#!/usr/bin/env python3
"""
SUNO End-to-End Validation Test
================================
Validates that SUNO automation works through all 5 critical steps:
1. ✅ Log into Whop (API validation)
2. ✅ Access actual clips (fetch from queue/inbox)
3. ✅ Post ONE clip successfully
4. ✅ Submit link back to Whop
5. ✅ See it tracked/accepted/monetized

This is the REALITY TEST before launching on Whop marketplace.
If this passes, SUNO is PROVEN. If not, it's scaffolding.
"""

import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

import config
from services.whop_client import WhopClient, WhopAuthError
from queue_manager import QueueManager, Clip, ClipStatus
from platform_poster import PlatformPoster
from earnings_tracker import EarningsTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


class SUNOValidation:
    """Run the 5-step SUNO reality test."""

    def __init__(self):
        self.results = {}
        self.test_clip_id = None
        self.posted_urls = {}
        self.submission_result = None

    async def run(self):
        """Execute all 5 validation steps."""
        print("\n" + "=" * 70)
        print("  SUNO END-TO-END VALIDATION TEST")
        print("  Reality Test: Prove automation works before launch")
        print("=" * 70 + "\n")

        # Step 1: Whop API Connection
        await self._step_1_whop_connection()

        # Step 2: Fetch Clips
        await self._step_2_fetch_clips()

        # Step 3: Post Clip
        if self.test_clip_id:
            await self._step_3_post_clip()

        # Step 4: Submit to Whop
        if self.posted_urls:
            await self._step_4_submit_whop()

        # Step 5: Track Earnings
        await self._step_5_track_earnings()

        # Summary
        self._print_summary()

    async def _step_1_whop_connection(self):
        """Step 1: Log into Whop (API validation)."""
        print("[STEP 1/5] Validating Whop API connection...\n")

        try:
            if not config.WHOP_API_KEY:
                print("  [FAIL] WHOP_API_KEY not set in .env")
                print("       Action: Add WHOP_API_KEY to .env file")
                self.results['step1_whop'] = False
                return

            client = WhopClient()

            # Test: Try to reach Whop campaigns endpoint (primary integration point)
            try:
                import httpx

                resp = client._request_with_retry("GET", "/ad_campaigns?limit=100")

                if resp.status_code == 200:
                    data = resp.json()
                    campaigns = data.get("data", data.get("campaigns", []))
                    print(f"  [PASS] Whop API reachable and authenticated")
                    print(f"       Campaigns endpoint: OK (found {len(campaigns)} campaigns)")
                    self.results['step1_whop'] = True

                elif resp.status_code == 401:
                    print(f"  [FAIL] HTTP 401: API key is not authorized")
                    print("       Action: Verify WHOP_API_KEY in .env is correct")
                    self.results['step1_whop'] = False

                elif resp.status_code == 403:
                    print(f"  [FAIL] HTTP 403: API key lacks required permissions")
                    print("       Action: Check that API key has 'campaigns' scope in Whop dashboard")
                    self.results['step1_whop'] = False

                elif resp.status_code == 404:
                    print(f"  [FAIL] HTTP 404: Endpoint not found")
                    print(f"       Attempted: GET /campaigns?limit=100")
                    print("       This suggests: incorrect API path, outdated Whop API version, or")
                    print("                       endpoint doesn't exist for this API key's account type")
                    print("       Action: Verify correct Whop API endpoint in official docs")
                    try:
                        error_detail = resp.json()
                        print(f"       Response: {error_detail}")
                    except:
                        pass
                    self.results['step1_whop'] = False

                else:
                    print(f"  [FAIL] HTTP {resp.status_code}: Unexpected response from Whop")
                    try:
                        print(f"       Response: {resp.json()}")
                    except:
                        print(f"       Response: {resp.text[:200]}")
                    self.results['step1_whop'] = False

            except Exception as e:
                print(f"  [FAIL] Could not reach Whop API: {e}")
                self.results['step1_whop'] = False

        except WhopAuthError as e:
            print(f"  [FAIL] Whop auth error: {e}")
            print("       Action: Verify WHOP_API_KEY is correct in .env")
            self.results['step1_whop'] = False
        except Exception as e:
            print(f"  [FAIL] Whop validation error: {e}")
            print("       Check: Network connection? API endpoint available?")
            self.results['step1_whop'] = False

        print()

    async def _step_2_fetch_clips(self):
        """Step 2: Access actual clips from queue/inbox."""
        print("[STEP 2/5] Checking clips in inbox...\n")

        try:
            queue = QueueManager()

            # Check inbox for clips
            if not config.CLIPS_INBOX.exists():
                config.CLIPS_INBOX.mkdir(parents=True, exist_ok=True)

            clip_files = list(config.CLIPS_INBOX.glob("*.mp4"))

            if clip_files:
                print(f"  [PASS] Found {len(clip_files)} clips in inbox")
                test_file = clip_files[0]

                # Create test clip in queue
                test_clip = Clip(
                    id=f"test_{datetime.now().timestamp()}",
                    filename=test_file.name,
                    filepath=str(test_file),
                    caption="SUNO Validation Test Clip",
                    hashtags="#test #validation #suno",
                    status=ClipStatus.PENDING.value,
                )

                # This would normally be saved to DB
                # For validation, we just track it
                self.test_clip_id = test_clip.id
                self.test_clip = test_clip

                print(f"  [PASS] Test clip prepared: {test_file.name}")
                self.results['step2_clips'] = True
            else:
                print(f"  [FAIL] No .mp4 files in {config.CLIPS_INBOX}")
                print(f"       Action: Add test video to clips/inbox/")
                self.results['step2_clips'] = False

        except Exception as e:
            print(f"  [FAIL] Error checking clips: {e}")
            self.results['step2_clips'] = False

        print()

    async def _step_3_post_clip(self):
        """Step 3: Post ONE clip successfully."""
        print("[STEP 3/5] Posting clip to platforms...\n")

        if not self.test_clip_id:
            print("  [SKIP] No clip to post (see step 2)")
            self.results['step3_post'] = False
            return

        try:
            # Verify platform credentials
            has_creds = (
                config.TIKTOK_USERNAME and
                config.INSTAGRAM_USERNAME and
                config.YOUTUBE_EMAIL
            )

            if not has_creds:
                missing = []
                if not config.TIKTOK_USERNAME:
                    missing.append("TIKTOK_USERNAME")
                if not config.INSTAGRAM_USERNAME:
                    missing.append("INSTAGRAM_USERNAME")
                if not config.YOUTUBE_EMAIL:
                    missing.append("YOUTUBE_EMAIL")

                print(f"  [FAIL] Missing credentials: {', '.join(missing)}")
                print(f"       Action: Set in .env file")
                self.results['step3_post'] = False
                return

            print(f"  Credentials verified: {config.PLATFORMS}")

            # Run platform poster (THIS IS THE REAL TEST)
            async with PlatformPoster() as poster:
                results = await poster.post_to_all_platforms(self.test_clip)

                success_count = sum(1 for r in results.values() if r.success)
                total_platforms = len(config.PLATFORMS)

                # Required platforms for launch
                required_platforms = set(config.PLATFORMS)  # All are required
                successful_platforms = {p for p, r in results.items() if r.success}
                failed_platforms = required_platforms - successful_platforms

                if success_count == total_platforms:
                    print(f"  [PASS] Posted to all {total_platforms} platforms")
                    self.posted_urls = {
                        p: r.url for p, r in results.items() if r.success
                    }
                    self.results['step3_post'] = True
                elif success_count > 0:
                    print(f"  [PARTIAL] Posted to {success_count}/{total_platforms} platforms")
                    print(f"       Success: {', '.join(successful_platforms)}")
                    print(f"       Failed: {', '.join(failed_platforms)}")
                    for platform in failed_platforms:
                        if platform in results:
                            print(f"         - {platform}: {results[platform].error}")
                    self.posted_urls = {
                        p: r.url for p, r in results.items() if r.success
                    }
                    self.results['step3_post'] = False  # Strict: partial = fail
                else:
                    print(f"  [FAIL] Failed to post to any platform")
                    for platform, result in results.items():
                        print(f"       {platform}: {result.error}")
                    self.results['step3_post'] = False

        except Exception as e:
            print(f"  [FAIL] Posting error: {e}")
            self.results['step3_post'] = False

        print()

    async def _step_4_submit_whop(self):
        """Step 4: Submit link back to Whop."""
        print("[STEP 4/5] Submitting clip URL back to Whop...\n")

        if not self.posted_urls:
            print("  [SKIP] No posted URLs to submit (see step 3)")
            self.results['step4_submit'] = False
            return

        try:
            client = WhopClient()

            # Get first active campaign (for testing)
            campaigns = client.list_campaigns()
            if not campaigns:
                print("  [FAIL] No active campaigns found on Whop")
                self.results['step4_submit'] = False
                return

            test_campaign = campaigns[0]
            print(f"  Submitting to campaign: {test_campaign['name']}")

            # Submit first posted URL
            first_url = next(iter(self.posted_urls.values()))
            result = client.submit_clip(test_campaign['whop_campaign_id'], first_url)

            if result['success']:
                print(f"  [PASS] Submission successful")
                print(f"       Campaign: {test_campaign['name']}")
                print(f"       URL: {first_url}")
                self.submission_result = result
                self.results['step4_submit'] = True
            else:
                print(f"  [FAIL] Submission failed: {result['error']}")
                self.results['step4_submit'] = False

        except Exception as e:
            print(f"  [FAIL] Submit error: {e}")
            self.results['step4_submit'] = False

        print()

    async def _step_5_track_earnings(self):
        """Step 5: Check that posted clips are actually tracked."""
        print("[STEP 5/5] Verifying posted clips are tracked...\n")

        try:
            if not self.posted_urls:
                print(f"  [SKIP] No posted clips to track (see step 3)")
                self.results['step5_tracking'] = False
                return

            tracker = EarningsTracker()
            today = tracker.get_today_stats()
            clips_posted = today.get('clips_posted', 0) if today else 0

            # Step 5 should verify the posted clip is actually in the tracker
            if clips_posted > 0:
                print(f"  [PASS] Posted clips are being tracked")
                print(f"       Clips posted today: {clips_posted}")
                print(f"       Total views: {today.get('total_views', 0):,}")
                print(f"       Estimated earnings: ${today.get('total_earnings', 0):.2f}")
                self.results['step5_tracking'] = True
            else:
                print(f"  [PARTIAL] Tracker exists but posted clip not yet recorded")
                print(f"       Action: Check if tracker needs to be updated after posting")
                print(f"       Expected: clips_posted >= {len(self.posted_urls)}")
                print(f"       Actual: clips_posted = {clips_posted}")
                # This is partial - tracker works but didn't capture our posted clip
                self.results['step5_tracking'] = False

        except Exception as e:
            print(f"  [FAIL] Tracking verification error: {e}")
            self.results['step5_tracking'] = False

        print()

    def _print_summary(self):
        """Print final validation summary."""
        print("=" * 70)
        print("  VALIDATION SUMMARY")
        print("=" * 70 + "\n")

        steps = [
            ('step1_whop', '1. Whop API Connection'),
            ('step2_clips', '2. Fetch Clips'),
            ('step3_post', '3. Post Clip'),
            ('step4_submit', '4. Submit to Whop'),
            ('step5_tracking', '5. Track Earnings'),
        ]

        passed = sum(1 for step, _ in steps if self.results.get(step, False))
        total = len(steps)

        for step_key, step_label in steps:
            status = "PASS" if self.results.get(step_key, False) else "FAIL"
            symbol = "Y" if self.results.get(step_key, False) else "N"
            print(f"  [{symbol}] {step_label:<30} [{status}]")

        print(f"\nResult: {passed}/{total} steps passed\n")

        if passed == total:
            print("*** SUNO IS PROVEN - END-TO-END AUTOMATION WORKS ***")
            print("    Ready to launch on Whop marketplace!\n")
            return True
        else:
            print("!!! SUNO IS NOT YET READY !!!")
            failing = [label for key, label in steps if not self.results.get(key, False)]
            print(f"   Failing steps: {', '.join([l.split('. ')[1] for l in failing])}\n")
            return False


async def main():
    """Run validation."""
    validator = SUNOValidation()
    result = await validator.run()
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    asyncio.run(main())
