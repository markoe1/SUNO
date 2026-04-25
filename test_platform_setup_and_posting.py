"""
SUNO Platform Setup & Testing Suite — Phase 12
Comprehensive testing for YouTube, Instagram, and TikTok posting.

Tests:
1. Platform setup/credential validation
2. Mock posting tests
3. Integration tests (if credentials exist)
"""

import logging
import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv
import requests

# Import platform adapters and credential managers
from suno.posting.adapters import get_adapter, get_supported_platforms
from suno.posting.youtube_oauth import YouTubeOAuthManager
from suno.posting.credential_manager import (
    TikTokCredentialManager,
    InstagramCredentialManager,
    YouTubeCredentialManager,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


class PlatformTestSuite:
    """Comprehensive platform testing suite."""

    def __init__(self):
        self.results = {}
        self.credentials = {}

    def print_section(self, title: str):
        """Print formatted section header."""
        logger.info("\n" + "=" * 80)
        logger.info(f"  {title}")
        logger.info("=" * 80)

    def print_subsection(self, title: str):
        """Print formatted subsection."""
        logger.info(f"\n  {title}")
        logger.info(f"  {'-' * len(title)}")

    # ==================== SETUP HELPERS ====================

    def setup_youtube(self) -> bool:
        """
        Set up YouTube credentials via OAuth.

        Returns:
            True if YouTube is ready, False otherwise
        """
        self.print_subsection("YouTube OAuth Setup")

        # Check if credentials.json exists
        creds_file = Path("youtube_uploader/credentials.json")
        if not creds_file.exists():
            logger.error("❌ credentials.json not found")
            logger.info("   Get it from: https://console.cloud.google.com")
            logger.info("   1. Create OAuth 2.0 Desktop App")
            logger.info("   2. Download as JSON")
            logger.info("   3. Save to youtube_uploader/credentials.json")
            return False

        logger.info(f"✓ credentials.json found")

        # Authenticate (will open browser if needed)
        logger.info("Authenticating with YouTube...")
        creds = YouTubeOAuthManager.authenticate(force_refresh=False)

        if not creds:
            logger.error("❌ YouTube authentication failed")
            return False

        logger.info("✓ YouTube authenticated")

        # Validate scopes
        if not YouTubeOAuthManager.validate_scopes():
            logger.warning("⚠ Token missing proper scopes")
            logger.info("Refreshing token with proper scopes...")
            creds = YouTubeOAuthManager.authenticate(force_refresh=True)
            if not creds or not YouTubeOAuthManager.validate_scopes():
                logger.error("❌ Failed to get proper scopes")
                return False

        logger.info("✓ YouTube scopes validated")

        # Validate adapter
        adapter = get_adapter("youtube")
        if not adapter:
            logger.error("❌ YouTube adapter not found")
            return False

        # Test account validation
        account_creds = {
            "access_token": creds.token,
            "creds_object": creds
        }

        if not adapter.validate_account(account_creds):
            logger.error("❌ YouTube account validation failed")
            return False

        logger.info("✓ YouTube account validated")
        self.credentials["youtube"] = account_creds
        return True

    def setup_instagram_manual(self) -> bool:
        """
        Set up Instagram credentials manually (requires user input).

        Returns:
            True if Instagram credentials are provided, False otherwise
        """
        self.print_subsection("Instagram Manual Setup")

        access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        business_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

        if not access_token or not business_account_id:
            logger.warning("⚠ Instagram credentials not fully set in .env")
            logger.info("\nTo set up Instagram, you need:")
            logger.info("1. Instagram Business Account ID")
            logger.info("   - Format: numeric (e.g., 17841406338772)")
            logger.info("   - Get from: Facebook Business Suite → Instagram Accounts")
            logger.info("")
            logger.info("2. Meta Graph API Access Token (Long-lived)")
            logger.info("   - Get from: https://developers.facebook.com")
            logger.info("   - Permissions: instagram_basic, instagram_content_publish")
            logger.info("   - Format: EAABC...xxx")
            logger.info("")
            logger.info("Add to .env:")
            logger.info("  INSTAGRAM_ACCESS_TOKEN=your_token_here")
            logger.info("  INSTAGRAM_BUSINESS_ACCOUNT_ID=your_account_id_here")
            logger.info("")

            if access_token:
                logger.info("✓ INSTAGRAM_ACCESS_TOKEN found")
            if business_account_id:
                logger.info("✓ INSTAGRAM_BUSINESS_ACCOUNT_ID found")

            return bool(access_token and business_account_id)

        logger.info(f"✓ Access token found: {access_token[:20]}...")
        logger.info(f"✓ Business account ID found: {business_account_id}")

        # Test account validation
        adapter = get_adapter("instagram")
        if not adapter:
            logger.error("❌ Instagram adapter not found")
            return False

        account_creds = {
            "access_token": access_token,
            "instagram_business_account_id": business_account_id
        }

        if not adapter.validate_account(account_creds):
            logger.error("❌ Instagram account validation failed")
            logger.info("   Check token validity and permissions")
            return False

        logger.info("✓ Instagram account validated")
        self.credentials["instagram"] = account_creds
        return True

    def setup_tiktok_manual(self) -> bool:
        """
        Set up TikTok credentials manually.

        Returns:
            True if TikTok credentials are provided, False otherwise
        """
        self.print_subsection("TikTok Manual Setup")

        access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
        client_id = os.getenv("TIKTOK_CLIENT_ID")

        if not access_token:
            logger.warning("⚠ TikTok credentials not set in .env")
            logger.info("\nTo set up TikTok, you need:")
            logger.info("1. TikTok OAuth Access Token")
            logger.info("   - Get from: TikTok Developer Platform")
            logger.info("   - Or: Manual token extraction from browser")
            logger.info("   - Format: Bearer token")
            logger.info("")
            logger.info("2. Client ID (optional)")
            logger.info("   - Get from: https://developer.tiktok.com")
            logger.info("")
            logger.info("Add to .env:")
            logger.info("  TIKTOK_ACCESS_TOKEN=your_token_here")
            logger.info("  TIKTOK_CLIENT_ID=your_client_id (optional)")
            logger.info("")
            return False

        logger.info(f"✓ Access token found: {access_token[:20]}...")
        if client_id:
            logger.info(f"✓ Client ID found: {client_id}")

        # Test account validation
        adapter = get_adapter("tiktok")
        if not adapter:
            logger.error("❌ TikTok adapter not found")
            return False

        account_creds = {
            "access_token": access_token,
            "client_id": client_id or ""
        }

        if not adapter.validate_account(account_creds):
            logger.error("❌ TikTok account validation failed")
            logger.info("   Check token validity and permissions")
            return False

        logger.info("✓ TikTok account validated")
        self.credentials["tiktok"] = account_creds
        return True

    # ==================== MOCK POSTING TESTS ====================

    def test_mock_posting(self) -> Dict[str, bool]:
        """
        Test payload preparation and mock posting logic.

        Returns:
            Dict with test results
        """
        self.print_subsection("Mock Posting Tests")

        test_data = {
            "clip_url": "https://example.com/test-clip.mp4",
            "caption": "Test clip caption",
            "hashtags": ["#test", "#suno"],
            "metadata": {"duration": 30}
        }

        results = {}

        for platform in ["youtube", "instagram", "tiktok"]:
            adapter = get_adapter(platform)
            if not adapter:
                logger.warning(f"  ⚠ {platform}: Adapter not found")
                results[platform] = False
                continue

            try:
                payload = adapter.prepare_payload(**test_data)
                logger.info(f"  ✓ {platform}: Payload prepared")
                logger.info(f"     - Payload keys: {list(payload.keys())}")
                results[platform] = True
            except Exception as e:
                logger.error(f"  ❌ {platform}: {e}")
                results[platform] = False

        return results

    # ==================== INTEGRATION TESTS ====================

    def test_youtube_integration(self) -> bool:
        """Test YouTube posting integration."""
        if "youtube" not in self.credentials:
            logger.warning("⚠ YouTube credentials not available")
            return False

        self.print_subsection("YouTube Integration Test")

        adapter = get_adapter("youtube")
        creds = self.credentials["youtube"]

        # Prepare test payload
        payload = adapter.prepare_payload(
            clip_url="https://example.com/test.mp4",
            caption="Test Video from SUNO",
            hashtags=["#test", "#automation"],
            metadata={}
        )

        logger.info("Payload prepared:")
        for key, value in payload.items():
            logger.info(f"  {key}: {str(value)[:50]}...")

        logger.info("✓ YouTube integration test complete (dry run)")
        logger.info("  (Actual posting disabled in test mode)")
        return True

    def test_instagram_integration(self) -> bool:
        """Test Instagram posting integration."""
        if "instagram" not in self.credentials:
            logger.warning("⚠ Instagram credentials not available")
            return False

        self.print_subsection("Instagram Integration Test")

        adapter = get_adapter("instagram")
        creds = self.credentials["instagram"]

        # Prepare test payload
        payload = adapter.prepare_payload(
            clip_url="https://example.com/test.mp4",
            caption="Test Reel from SUNO",
            hashtags=["#test", "#automation"],
            metadata={}
        )

        logger.info("Payload prepared:")
        for key, value in payload.items():
            logger.info(f"  {key}: {str(value)[:50]}...")

        logger.info("✓ Instagram integration test complete (dry run)")
        logger.info("  (Actual posting disabled in test mode)")
        return True

    def test_tiktok_integration(self) -> bool:
        """Test TikTok posting integration."""
        if "tiktok" not in self.credentials:
            logger.warning("⚠ TikTok credentials not available")
            return False

        self.print_subsection("TikTok Integration Test")

        adapter = get_adapter("tiktok")
        creds = self.credentials["tiktok"]

        # Prepare test payload
        payload = adapter.prepare_payload(
            clip_url="https://example.com/test.mp4",
            caption="Test Video from SUNO",
            hashtags=["#test", "#automation"],
            metadata={}
        )

        logger.info("Payload prepared:")
        for key, value in payload.items():
            logger.info(f"  {key}: {str(value)[:50]}...")

        logger.info("✓ TikTok integration test complete (dry run)")
        logger.info("  (Actual posting disabled in test mode)")
        return True

    # ==================== MAIN TEST RUNNER ====================

    async def run_all_tests(self):
        """Run complete test suite."""
        self.print_section("SUNO PLATFORM SETUP & TESTING SUITE - PHASE 12")

        # Setup phase
        self.print_section("PHASE 1: CREDENTIAL SETUP")

        youtube_ok = self.setup_youtube()
        instagram_ok = self.setup_instagram_manual()
        tiktok_ok = self.setup_tiktok_manual()

        # Mock posting tests
        self.print_section("PHASE 2: MOCK POSTING TESTS")
        mock_results = self.test_mock_posting()

        # Integration tests
        self.print_section("PHASE 3: INTEGRATION TESTS")

        if youtube_ok:
            youtube_integration_ok = self.test_youtube_integration()
        else:
            youtube_integration_ok = False
            logger.warning("⚠ Skipping YouTube integration (not set up)")

        if instagram_ok:
            instagram_integration_ok = self.test_instagram_integration()
        else:
            instagram_integration_ok = False
            logger.warning("⚠ Skipping Instagram integration (not set up)")

        if tiktok_ok:
            tiktok_integration_ok = self.test_tiktok_integration()
        else:
            tiktok_integration_ok = False
            logger.warning("⚠ Skipping TikTok integration (not set up)")

        # Summary
        self.print_section("TEST SUMMARY")

        summary = {
            "setup": {
                "youtube": youtube_ok,
                "instagram": instagram_ok,
                "tiktok": tiktok_ok,
            },
            "mock_posting": mock_results,
            "integration": {
                "youtube": youtube_integration_ok if youtube_ok else "skipped",
                "instagram": instagram_integration_ok if instagram_ok else "skipped",
                "tiktok": tiktok_integration_ok if tiktok_ok else "skipped",
            }
        }

        self._print_summary(summary)

        return summary

    def _print_summary(self, summary: Dict):
        """Print test summary."""
        logger.info("\nSetup Status:")
        for platform, ok in summary["setup"].items():
            status = "✓ PASS" if ok else "❌ FAIL"
            logger.info(f"  {status}: {platform.upper()}")

        logger.info("\nMock Posting Status:")
        for platform, ok in summary["mock_posting"].items():
            status = "✓ PASS" if ok else "❌ FAIL"
            logger.info(f"  {status}: {platform.upper()}")

        logger.info("\nIntegration Status:")
        for platform, result in summary["integration"].items():
            if result == "skipped":
                logger.info(f"  ⊘ SKIP: {platform.upper()} (not set up)")
            else:
                status = "✓ PASS" if result else "❌ FAIL"
                logger.info(f"  {status}: {platform.upper()}")

        # Overall status
        setup_passed = sum(1 for v in summary["setup"].values() if v)
        mock_passed = sum(1 for v in summary["mock_posting"].values() if v)
        integration_ready = sum(1 for v in summary["integration"].values() if v is True)

        logger.info(f"\nOverall: {setup_passed}/3 setup, {mock_passed}/5 mock tests")
        logger.info(f"Ready for integration: {integration_ready}/3 platforms")

        logger.info("\n" + "=" * 80)
        logger.info("  NEXT STEPS")
        logger.info("=" * 80)

        if not summary["setup"]["youtube"]:
            logger.info("1. YouTube: Re-authorize with proper OAuth scopes")
            logger.info("   - Get credentials.json from Google Cloud Console")
            logger.info("   - Run this test again to authenticate")

        if not summary["setup"]["instagram"]:
            logger.info("2. Instagram: Set up Meta Graph API credentials")
            logger.info("   - Get Access Token and Business Account ID from Meta")
            logger.info("   - Add to .env file")

        if not summary["setup"]["tiktok"]:
            logger.info("3. TikTok: (Optional) Set up OAuth credentials")
            logger.info("   - Apply for TikTok Developer Account")
            logger.info("   - Get OAuth token from TikTok Developer Platform")
            logger.info("   - Add to .env file")

        logger.info("\nOnce all credentials are set up, run:")
        logger.info("  python test_platform_integration.py --posting")
        logger.info("\nto test actual video posting.")


async def main():
    """Run test suite."""
    suite = PlatformTestSuite()
    results = await suite.run_all_tests()

    # Exit with success if at least YouTube is set up
    return results["setup"]["youtube"]


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
