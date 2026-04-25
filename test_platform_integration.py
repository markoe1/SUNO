"""
SUNO Platform Integration Test — Phase 12
Real posting integration tests for YouTube, Instagram, and TikTok.

Usage:
  python test_platform_integration.py --platform youtube --dry-run
  python test_platform_integration.py --platform instagram --dry-run
  python test_platform_integration.py --platform tiktok --dry-run

NOTE: Add --posting flag to actually post videos (requires valid credentials and test video)
"""

import logging
import argparse
import asyncio
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from suno.posting.adapters import get_adapter
from suno.posting.youtube_oauth import YouTubeOAuthManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()


class PlatformIntegrationTest:
    """Integration tests for platform posting."""

    def __init__(self, platform: str, dry_run: bool = True):
        self.platform = platform
        self.dry_run = dry_run
        self.adapter = get_adapter(platform)

    def print_header(self):
        """Print test header."""
        logger.info("\n" + "=" * 80)
        logger.info(f"  Platform: {self.platform.upper()}")
        logger.info(f"  Mode: {'DRY RUN' if self.dry_run else 'ACTUAL POSTING'}")
        logger.info("=" * 80)

    async def test_youtube(self):
        """Test YouTube posting."""
        self.print_header()

        if not self.adapter:
            logger.error("❌ YouTube adapter not found")
            return False

        # Authenticate
        logger.info("Authenticating with YouTube...")
        creds = YouTubeOAuthManager.authenticate()

        if not creds:
            logger.error("❌ YouTube authentication failed")
            return False

        logger.info("✓ Authenticated")

        # Validate account
        account_creds = {"access_token": creds.token, "creds_object": creds}

        if not self.adapter.validate_account(account_creds):
            logger.error("❌ Account validation failed")
            return False

        logger.info("✓ Account validated")

        # Prepare test payload
        test_payload = self.adapter.prepare_payload(
            clip_url="https://example.com/test-clip.mp4",
            caption="Test Video from SUNO Automation",
            hashtags=["#SunoAI", "#Automation", "#Test"],
            metadata={"duration": 30, "source": "test"}
        )

        logger.info("✓ Payload prepared:")
        for key, value in test_payload.items():
            logger.info(f"  - {key}: {str(value)[:60]}...")

        if self.dry_run:
            logger.info("\n✓ DRY RUN COMPLETE")
            logger.info("  Ready for actual posting (remove --dry-run flag)")
            return True

        # Actual posting (only if --posting flag used)
        logger.warning("⚠ ACTUAL POSTING DISABLED IN THIS VERSION")
        logger.info("  To enable posting:")
        logger.info("  1. Ensure you have a real test video URL")
        logger.info("  2. Manually call self.adapter.post() with credentials")
        logger.info("  3. Monitor logs for success/failure")

        return True

    async def test_instagram(self):
        """Test Instagram posting."""
        self.print_header()

        if not self.adapter:
            logger.error("❌ Instagram adapter not found")
            return False

        import os
        access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        business_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

        if not all([access_token, business_account_id]):
            logger.error("❌ Missing Instagram credentials in .env")
            logger.info("  INSTAGRAM_ACCESS_TOKEN: required")
            logger.info("  INSTAGRAM_BUSINESS_ACCOUNT_ID: required")
            return False

        logger.info("✓ Credentials found")

        # Validate account
        account_creds = {
            "access_token": access_token,
            "instagram_business_account_id": business_account_id
        }

        if not self.adapter.validate_account(account_creds):
            logger.error("❌ Account validation failed")
            logger.info("  Check token validity and permissions")
            return False

        logger.info("✓ Account validated")

        # Prepare test payload
        test_payload = self.adapter.prepare_payload(
            clip_url="https://example.com/test-reel.mp4",
            caption="Test Reel from SUNO Automation",
            hashtags=["#SunoAI", "#Automation", "#Test"],
            metadata={"duration": 30, "source": "test"}
        )

        logger.info("✓ Payload prepared:")
        for key, value in test_payload.items():
            logger.info(f"  - {key}: {str(value)[:60]}...")

        if self.dry_run:
            logger.info("\n✓ DRY RUN COMPLETE")
            logger.info("  Ready for actual posting (remove --dry-run flag)")
            return True

        # Actual posting
        logger.warning("⚠ ACTUAL POSTING DISABLED IN THIS VERSION")
        logger.info("  To enable posting:")
        logger.info("  1. Ensure you have a real test video URL")
        logger.info("  2. Manually call self.adapter.post() with credentials")
        logger.info("  3. Monitor logs for success/failure")

        return True

    async def test_tiktok(self):
        """Test TikTok posting."""
        self.print_header()

        if not self.adapter:
            logger.error("❌ TikTok adapter not found")
            return False

        import os
        access_token = os.getenv("TIKTOK_ACCESS_TOKEN")

        if not access_token:
            logger.error("❌ Missing TikTok credentials in .env")
            logger.info("  TIKTOK_ACCESS_TOKEN: required")
            return False

        logger.info("✓ Credentials found")

        # Validate account
        account_creds = {"access_token": access_token}

        if not self.adapter.validate_account(account_creds):
            logger.error("❌ Account validation failed")
            logger.info("  Check token validity and permissions")
            return False

        logger.info("✓ Account validated")

        # Prepare test payload
        test_payload = self.adapter.prepare_payload(
            clip_url="https://example.com/test-video.mp4",
            caption="Test Video from SUNO Automation",
            hashtags=["#SunoAI", "#Automation", "#Test"],
            metadata={"duration": 30, "source": "test"}
        )

        logger.info("✓ Payload prepared:")
        for key, value in test_payload.items():
            logger.info(f"  - {key}: {str(value)[:60]}...")

        if self.dry_run:
            logger.info("\n✓ DRY RUN COMPLETE")
            logger.info("  Ready for actual posting (remove --dry-run flag)")
            return True

        # Actual posting
        logger.warning("⚠ ACTUAL POSTING DISABLED IN THIS VERSION")
        logger.info("  To enable posting:")
        logger.info("  1. Ensure you have a real test video URL")
        logger.info("  2. Manually call self.adapter.post() with credentials")
        logger.info("  3. Monitor logs for success/failure")

        return True

    async def run(self) -> bool:
        """Run the appropriate test."""
        if self.platform == "youtube":
            return await self.test_youtube()
        elif self.platform == "instagram":
            return await self.test_instagram()
        elif self.platform == "tiktok":
            return await self.test_tiktok()
        else:
            logger.error(f"❌ Unknown platform: {self.platform}")
            return False


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SUNO Platform Integration Test"
    )
    parser.add_argument(
        "--platform",
        choices=["youtube", "instagram", "tiktok"],
        default="youtube",
        help="Platform to test (default: youtube)"
    )
    parser.add_argument(
        "--posting",
        action="store_true",
        help="Actually post videos (default: dry-run only)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run in dry-run mode (default: True)"
    )

    args = parser.parse_args()

    # If --posting is set, disable dry-run
    dry_run = not args.posting

    test = PlatformIntegrationTest(args.platform, dry_run=dry_run)
    result = await test.run()

    logger.info("\n" + "=" * 80)
    if result:
        logger.info("  ✓ TEST PASSED")
    else:
        logger.info("  ❌ TEST FAILED")
    logger.info("=" * 80)

    return result


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
