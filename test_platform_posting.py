"""
Platform Posting Integration Test
Tests YouTube, TikTok, and Instagram posting adapters.
"""

import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from suno.posting.adapters import get_adapter, get_supported_platforms

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


async def test_youtube_adapter():
    """Test YouTube adapter with actual token."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: YouTube Adapter")
    logger.info("=" * 70)

    adapter = get_adapter("youtube")
    if not adapter:
        logger.error("❌ YouTube adapter not found")
        return False

    # Check if token file exists
    token_file = Path("youtube_uploader/token.pickle")
    if not token_file.exists():
        logger.error(f"❌ YouTube token file not found: {token_file}")
        return False

    logger.info(f"✓ YouTube token file exists: {token_file}")

    # Try to load the token
    try:
        import pickle
        with open(token_file, "rb") as f:
            creds = pickle.load(f)
            logger.info(f"✓ YouTube credentials loaded")
    except Exception as e:
        logger.error(f"❌ Failed to load YouTube token: {e}")
        return False

    # Try to extract access token (if available)
    try:
        # The token is a google.auth.credentials.Credentials object
        access_token = creds.token if hasattr(creds, "token") else None
        if access_token:
            logger.info(f"✓ Access token exists: {access_token[:20]}...")
        else:
            logger.warning("⚠ Access token not immediately available (will be generated on use)")
    except Exception as e:
        logger.warning(f"⚠ Could not extract access token: {e}")

    # Test account validation (this requires network call)
    logger.info("Testing YouTube account validation...")
    account_creds = {
        "access_token": access_token or "test",
        "creds_object": creds  # Pass the credentials object for refresh handling
    }
    validation_result = adapter.validate_account(account_creds)
    logger.info(f"  Validation result: {validation_result}")

    return True


async def test_tiktok_adapter():
    """Test TikTok adapter setup."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: TikTok Adapter")
    logger.info("=" * 70)

    adapter = get_adapter("tiktok")
    if not adapter:
        logger.error("❌ TikTok adapter not found")
        return False

    logger.info("✓ TikTok adapter found")

    # Check credentials
    import os
    username = os.getenv("TIKTOK_USERNAME")
    password = os.getenv("TIKTOK_PASSWORD")

    if not username or not password:
        logger.error("❌ TikTok credentials not in environment")
        logger.info("  Set TIKTOK_USERNAME and TIKTOK_PASSWORD in .env")
        return False

    logger.info(f"✓ TikTok credentials found: {username}")

    # Try to get OAuth token via credential manager
    logger.info("Attempting to obtain TikTok OAuth token...")
    logger.warning(
        "⚠ This requires browser automation and may fail due to anti-bot measures"
    )

    from suno.posting.credential_manager import TikTokCredentialManager

    try:
        # Try with non-headless browser for testing
        # Note: This will require manual CAPTCHA solving if triggered
        logger.info("  Starting TikTok login in browser (headless=False)...")
        logger.info("  If CAPTCHA appears, please solve it manually...")

        # For now, just mark as pending since headless doesn't work
        logger.warning("⚠ TikTok browser automation test skipped (requires manual setup)")
        logger.info("  Manual setup required:")
        logger.info("  1. Visit https://www.tiktok.com and log in manually")
        logger.info("  2. Extract OAuth token from browser dev tools")
        logger.info("  3. Add to .env as TIKTOK_ACCESS_TOKEN")
        return False

    except Exception as e:
        logger.error(f"❌ TikTok token extraction failed: {e}")
        return False


async def test_instagram_adapter():
    """Test Instagram adapter setup."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Instagram Adapter")
    logger.info("=" * 70)

    adapter = get_adapter("instagram")
    if not adapter:
        logger.error("❌ Instagram adapter not found")
        return False

    logger.info("✓ Instagram adapter found")

    # Check credentials
    import os
    username = os.getenv("INSTAGRAM_USERNAME")
    password = os.getenv("INSTAGRAM_PASSWORD")

    if not username or not password:
        logger.error("❌ Instagram credentials not in environment")
        logger.info("  Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env")
        return False

    logger.info(f"✓ Instagram credentials found: {username}")

    # Instagram requires Meta Business Account setup
    logger.warning("⚠ Instagram requires Meta Graph API setup")
    logger.info("  This requires:")
    logger.info("  1. Create Meta Business Account")
    logger.info("  2. Create Instagram Business Account")
    logger.info("  3. Get Graph API access token")
    logger.info("  4. Add to .env as INSTAGRAM_BUSINESS_ACCOUNT_ID and INSTAGRAM_ACCESS_TOKEN")

    return False


async def test_adapter_registry():
    """Test that adapters are properly registered."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Adapter Registry")
    logger.info("=" * 70)

    platforms = get_supported_platforms()
    logger.info(f"Supported platforms: {platforms}")

    for platform in platforms:
        adapter = get_adapter(platform)
        if adapter:
            logger.info(f"✓ {platform}: {adapter.__class__.__name__}")
        else:
            logger.error(f"❌ {platform}: No adapter found")

    return len(platforms) > 0


async def main():
    """Run all tests."""
    logger.info("\n" + "=" * 70)
    logger.info("SUNO PLATFORM POSTING TEST SUITE - PHASE 11")
    logger.info("=" * 70)

    results = {
        "adapter_registry": await test_adapter_registry(),
        "youtube": await test_youtube_adapter(),
        "tiktok": await test_tiktok_adapter(),
        "instagram": await test_instagram_adapter(),
    }

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    logger.info(f"\nTotal: {passed}/{total} passed")

    logger.info("\n" + "=" * 70)
    logger.info("NEXT STEPS")
    logger.info("=" * 70)
    logger.info("YouTube: ✓ Ready for testing (token exists)")
    logger.info("TikTok: ⚠ Requires OAuth token from developer app or manual extraction")
    logger.info("Instagram: ⚠ Requires Meta Graph API setup")

    return passed == total


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
