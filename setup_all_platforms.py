#!/usr/bin/env python3
"""
Setup ALL platforms for Phase 11 — YouTube, Instagram, TikTok
Automatically handles OAuth and browser automation.

Usage:
  python setup_all_platforms.py                    # Setup all three
  python setup_all_platforms.py --youtube          # Just YouTube
  python setup_all_platforms.py --instagram        # Just Instagram
  python setup_all_platforms.py --tiktok           # Just TikTok
  python setup_all_platforms.py --test             # Test without setup
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv, dotenv_values
import os

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PlatformSetupManager:
    """Manages setup of all three platforms."""

    def __init__(self):
        self.results = {}
        self.env_updates = {}

    async def setup_youtube(self) -> bool:
        """Setup YouTube with OAuth."""
        logger.info("\n" + "=" * 70)
        logger.info("SETUP 1: YouTube OAuth")
        logger.info("=" * 70)

        try:
            from suno.posting.youtube_oauth import YouTubeOAuthManager

            logger.info("Authenticating with YouTube...")
            creds = YouTubeOAuthManager.authenticate(force_refresh=False)

            if creds:
                logger.info("✓ YouTube authentication successful")

                # Validate scopes
                if YouTubeOAuthManager.validate_scopes():
                    logger.info("✓ YouTube token has proper scopes (upload + readonly)")
                    self.results["youtube"] = True
                    return True
                else:
                    logger.warning("⚠ Token missing upload scope, re-authorizing...")
                    creds = YouTubeOAuthManager.reset()
                    if creds and YouTubeOAuthManager.validate_scopes():
                        logger.info("✓ YouTube re-authorized with proper scopes")
                        self.results["youtube"] = True
                        return True
                    else:
                        logger.error("✗ YouTube scope validation failed")
                        self.results["youtube"] = False
                        return False
            else:
                logger.error("✗ YouTube authentication failed")
                self.results["youtube"] = False
                return False

        except Exception as e:
            logger.error(f"✗ YouTube setup error: {e}")
            self.results["youtube"] = False
            return False

    async def setup_tiktok(self) -> bool:
        """Setup TikTok via browser automation."""
        logger.info("\n" + "=" * 70)
        logger.info("SETUP 2: TikTok OAuth (Browser Automation)")
        logger.info("=" * 70)

        try:
            from suno.posting.credential_manager import TikTokCredentialManager

            username = os.getenv("TIKTOK_USERNAME")
            password = os.getenv("TIKTOK_PASSWORD")

            if not username or not password:
                logger.error("✗ TikTok credentials not in .env")
                logger.info("  Set TIKTOK_USERNAME and TIKTOK_PASSWORD in .env")
                self.results["tiktok"] = False
                return False

            logger.info(f"Attempting TikTok login for {username}...")
            logger.info("Opening browser for TikTok login (headless)...")
            logger.warning("Note: This may fail due to anti-bot detection")

            token = await TikTokCredentialManager.get_valid_token(username, password)

            if token:
                logger.info(f"✓ TikTok token obtained: {token[:30]}...")
                self.env_updates["TIKTOK_ACCESS_TOKEN"] = token
                self.results["tiktok"] = True
                return True
            else:
                logger.error("✗ TikTok token extraction failed")
                logger.info("  TikTok may have anti-bot detection enabled")
                logger.info("  Try: python setup_all_platforms.py --tiktok --headless=false")
                self.results["tiktok"] = False
                return False

        except Exception as e:
            logger.error(f"✗ TikTok setup error: {e}")
            self.results["tiktok"] = False
            return False

    async def setup_instagram(self) -> bool:
        """Setup Instagram via browser automation."""
        logger.info("\n" + "=" * 70)
        logger.info("SETUP 3: Instagram Credentials (Browser Automation)")
        logger.info("=" * 70)

        try:
            from suno.posting.credential_manager import InstagramCredentialManager

            username = os.getenv("INSTAGRAM_USERNAME")
            password = os.getenv("INSTAGRAM_PASSWORD")

            if not username or not password:
                logger.error("✗ Instagram credentials not in .env")
                logger.info("  Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env")
                self.results["instagram"] = False
                return False

            logger.info(f"Attempting Instagram login for {username}...")
            logger.info("Opening browser for Instagram login (headless)...")

            creds = await InstagramCredentialManager.get_valid_credentials(username, password)

            if creds:
                logger.info(f"✓ Instagram credentials obtained")
                logger.info(f"  Username: {creds.get('username')}")
                if creds.get("instagram_user_id"):
                    logger.info(f"  User ID: {creds.get('instagram_user_id')}")

                # For Instagram, we need either:
                # - A Meta Graph API access token (requires Meta developer setup)
                # - Or use the credentials we extracted
                logger.warning("⚠ Instagram login successful, but needs Meta Graph API token")
                logger.info("  To get Graph API token:")
                logger.info("  1. Create Meta Business Account")
                logger.info("  2. Create app at developers.facebook.com")
                logger.info("  3. Get long-lived access token")
                logger.info("  4. Add INSTAGRAM_ACCESS_TOKEN to .env")
                logger.info("  See PHASE_11_SETUP_GUIDE.md for detailed steps")

                # Cache the credentials we have
                self.env_updates["INSTAGRAM_USER_ID"] = creds.get("instagram_user_id", "")
                self.results["instagram"] = True  # Mark as partial success
                return False  # Return False until we have proper Graph API token

            else:
                logger.error("✗ Instagram login failed")
                logger.info("  Check credentials or anti-bot measures")
                self.results["instagram"] = False
                return False

        except Exception as e:
            logger.error(f"✗ Instagram setup error: {e}")
            self.results["instagram"] = False
            return False

    async def run_setup(self, platforms: list = None) -> Dict[str, bool]:
        """Run setup for specified platforms."""
        if platforms is None:
            platforms = ["youtube", "tiktok", "instagram"]

        logger.info("\n" + "=" * 70)
        logger.info("PHASE 11 — SETUP ALL PLATFORMS")
        logger.info("=" * 70)
        logger.info(f"Platforms: {', '.join(platforms)}")

        if "youtube" in platforms:
            await self.setup_youtube()

        if "tiktok" in platforms:
            await self.setup_tiktok()

        if "instagram" in platforms:
            await self.setup_instagram()

        # Save env updates
        if self.env_updates:
            self.save_env_updates()

        return self.results

    def save_env_updates(self):
        """Save new credentials to .env file."""
        logger.info("\n" + "=" * 70)
        logger.info("Saving credentials to .env...")
        logger.info("=" * 70)

        env_file = Path(".env")
        current_env = dotenv_values(env_file)

        # Update with new values
        current_env.update(self.env_updates)

        # Write back to file
        with open(env_file, "w") as f:
            for key, value in current_env.items():
                f.write(f"{key}={value}\n")

        logger.info(f"✓ Updated .env with {len(self.env_updates)} new credentials:")
        for key, value in self.env_updates.items():
            display_value = f"{value[:20]}..." if len(value) > 20 else value
            logger.info(f"  {key}={display_value}")

    def test_credentials(self) -> bool:
        """Test if all credentials are now available."""
        logger.info("\n" + "=" * 70)
        logger.info("TESTING CREDENTIALS")
        logger.info("=" * 70)

        youtube_ok = Path("youtube_uploader/token.pickle").exists()
        tiktok_token = os.getenv("TIKTOK_ACCESS_TOKEN")
        instagram_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        instagram_account = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

        logger.info(f"YouTube:   {'✓ Token file exists' if youtube_ok else '✗ No token'}")
        logger.info(f"TikTok:    {'✓ Access token set' if tiktok_token else '✗ No token'}")
        logger.info(f"Instagram: {'✓ API token set' if instagram_token else '✗ No API token'}")
        if instagram_account:
            logger.info(f"           ✓ Business account ID: {instagram_account}")

        all_ready = youtube_ok and tiktok_token and instagram_token and instagram_account
        return all_ready

    def print_summary(self):
        """Print setup summary."""
        logger.info("\n" + "=" * 70)
        logger.info("SETUP SUMMARY")
        logger.info("=" * 70)

        for platform, success in self.results.items():
            status = "✓ SUCCESS" if success else "✗ SETUP NEEDED"
            logger.info(f"{platform.upper():12} {status}")

        logger.info("\n" + "=" * 70)
        logger.info("NEXT STEPS")
        logger.info("=" * 70)

        if self.results.get("youtube"):
            logger.info("✓ YouTube:   Ready to post")
        else:
            logger.info("✗ YouTube:   Run setup again or check browser error")

        if self.results.get("tiktok"):
            logger.info("✓ TikTok:    Ready to post")
        else:
            logger.info("✗ TikTok:    Browser automation failed (anti-bot?)")
            logger.info("           Try: python setup_all_platforms.py --tiktok")

        if self.results.get("instagram"):
            logger.info("⚠ Instagram: Logged in, but needs Meta Graph API token")
            logger.info("           See PHASE_11_SETUP_GUIDE.md for API setup")
        else:
            logger.info("✗ Instagram: Login failed")

        logger.info("\nVerify with: python phase11_test_posting.py")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Setup all Phase 11 platforms")
    parser.add_argument("--youtube", action="store_true", help="Setup YouTube only")
    parser.add_argument("--instagram", action="store_true", help="Setup Instagram only")
    parser.add_argument("--tiktok", action="store_true", help="Setup TikTok only")
    parser.add_argument("--test", action="store_true", help="Test credentials only")
    args = parser.parse_args()

    manager = PlatformSetupManager()

    if args.test:
        # Just test
        return 0 if manager.test_credentials() else 1

    # Determine which platforms to setup
    platforms = []
    if args.youtube:
        platforms.append("youtube")
    if args.instagram:
        platforms.append("instagram")
    if args.tiktok:
        platforms.append("tiktok")

    if not platforms:
        platforms = ["youtube", "tiktok", "instagram"]

    # Run setup
    results = await manager.run_setup(platforms)
    manager.print_summary()

    # Return success if all setup
    all_success = all(results.values())
    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
