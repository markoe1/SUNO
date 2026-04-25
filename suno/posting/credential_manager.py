"""
Platform Credential Manager
Handles obtaining and refreshing OAuth tokens for platforms.
Currently focuses on TikTok and Instagram OAuth via browser automation.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path
from playwright.async_api import async_playwright, Page
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

CREDENTIALS_DIR = Path(__file__).parent.parent.parent / "data" / "platform_credentials"
CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)


class TikTokCredentialManager:
    """Manages TikTok OAuth token acquisition and refresh."""

    CREDENTIALS_FILE = CREDENTIALS_DIR / "tiktok_tokens.json"
    TOKEN_EXPIRY_BUFFER = timedelta(hours=1)  # Refresh if expires within 1 hour

    @staticmethod
    async def login_and_get_token(username: str, password: str) -> Optional[Dict[str, str]]:
        """
        Log in to TikTok using Playwright and obtain OAuth token.

        Args:
            username: TikTok username/email
            password: TikTok password

        Returns:
            Dict with access_token, or None if failed
        """
        logger.info(f"Attempting TikTok login for {username}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                # Navigate to TikTok
                await page.goto("https://www.tiktok.com", wait_until="networkidle")

                # Click login button
                await page.click("text='Log in'", timeout=5000)
                await asyncio.sleep(1)

                # Handle login modal
                # TikTok usually shows login options - try email/password
                try:
                    await page.click("text='Use phone / email / username'", timeout=3000)
                except:
                    pass

                # Wait for input field and enter username
                await page.wait_for_selector("input[name='username']", timeout=5000)
                await page.fill("input[name='username']", username)
                await asyncio.sleep(0.5)

                # Enter password
                await page.wait_for_selector("input[name='password']", timeout=5000)
                await page.fill("input[name='password']", password)
                await asyncio.sleep(0.5)

                # Click login button
                await page.click("button:has-text('Log in')", timeout=5000)

                # Wait for redirect to home or dashboard
                await page.wait_for_url("**/home**", timeout=30000)

                logger.info("TikTok login successful")

                # Try to extract token from localStorage or cookies
                # Check localStorage for auth_token or similar
                local_storage = await page.evaluate("() => JSON.stringify(localStorage)")
                local_storage_dict = json.loads(local_storage)

                # Check for common TikTok token keys
                token = None
                for key in ["auth_token", "tiktok_access_token", "access_token"]:
                    if key in local_storage_dict:
                        token = local_storage_dict[key]
                        break

                if token:
                    credentials = {
                        "access_token": token,
                        "username": username,
                        "obtained_at": datetime.utcnow().isoformat(),
                        "expires_in": 7776000,  # 90 days (typical)
                    }
                    logger.info(f"Extracted TikTok token for {username}")
                    return credentials

                # If no token in localStorage, check cookies
                cookies = await page.context.cookies()
                for cookie in cookies:
                    if "token" in cookie.get("name", "").lower():
                        logger.info(f"Found token cookie: {cookie.get('name')}")

                logger.warning("Could not extract TikTok token from browser")
                return None

            except Exception as e:
                logger.error(f"TikTok login failed: {e}")
                return None

            finally:
                await browser.close()

    @staticmethod
    async def get_valid_token(username: str, password: str) -> Optional[str]:
        """
        Get valid TikTok token, using cached token if still valid.

        Args:
            username: TikTok username/email
            password: TikTok password

        Returns:
            Access token or None if cannot obtain
        """
        # Check cached credentials
        if TikTokCredentialManager.CREDENTIALS_FILE.exists():
            with open(TikTokCredentialManager.CREDENTIALS_FILE) as f:
                cached = json.load(f)
                if cached.get("username") == username:
                    # Check if still valid
                    obtained_at = datetime.fromisoformat(cached["obtained_at"])
                    expires_in = cached.get("expires_in", 7776000)
                    expires_at = obtained_at + timedelta(seconds=expires_in)

                    if expires_at - TikTokCredentialManager.TOKEN_EXPIRY_BUFFER > datetime.utcnow():
                        logger.info("Using cached TikTok token")
                        return cached["access_token"]

        # Get new token
        credentials = await TikTokCredentialManager.login_and_get_token(username, password)
        if credentials:
            # Cache it
            with open(TikTokCredentialManager.CREDENTIALS_FILE, "w") as f:
                json.dump(credentials, f, indent=2)
            return credentials["access_token"]

        return None


class InstagramCredentialManager:
    """Manages Instagram OAuth token acquisition and refresh."""

    CREDENTIALS_FILE = CREDENTIALS_DIR / "instagram_tokens.json"
    TOKEN_EXPIRY_BUFFER = timedelta(hours=1)

    @staticmethod
    async def login_and_get_token(username: str, password: str) -> Optional[Dict[str, str]]:
        """
        Log in to Instagram using Playwright and obtain credentials.

        Args:
            username: Instagram username/email
            password: Instagram password

        Returns:
            Dict with instagram_business_account_id and related credentials
        """
        logger.info(f"Attempting Instagram login for {username}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                # Navigate to Instagram
                await page.goto("https://www.instagram.com", wait_until="networkidle")

                # Wait for login form
                await page.wait_for_selector("input[name='username']", timeout=10000)

                # Enter username
                await page.fill("input[name='username']", username)
                await asyncio.sleep(0.5)

                # Enter password
                await page.fill("input[name='password']", password)
                await asyncio.sleep(0.5)

                # Submit login
                await page.click("button[type='button']:has-text('Log in')", timeout=5000)

                # Wait for redirect to home
                await page.wait_for_url("**/", timeout=30000)

                logger.info("Instagram login successful")

                # Try to get account info from localStorage or API calls
                local_storage = await page.evaluate("() => JSON.stringify(localStorage)")
                local_storage_dict = json.loads(local_storage)

                # Look for Instagram account data
                credentials = {
                    "username": username,
                    "obtained_at": datetime.utcnow().isoformat(),
                }

                # Try to extract user ID or business account info
                if "ig_user" in local_storage_dict:
                    try:
                        user_data = json.loads(local_storage_dict["ig_user"])
                        if "pk" in user_data:
                            credentials["instagram_user_id"] = str(user_data["pk"])
                    except:
                        pass

                logger.warning(
                    "Instagram login successful but cannot extract OAuth token via browser. "
                    "Consider using Meta Business App credentials instead."
                )
                return credentials

            except Exception as e:
                logger.error(f"Instagram login failed: {e}")
                return None

            finally:
                await browser.close()

    @staticmethod
    async def get_valid_credentials(username: str, password: str) -> Optional[Dict[str, str]]:
        """
        Get valid Instagram credentials, using cached if still valid.

        Args:
            username: Instagram username/email
            password: Instagram password

        Returns:
            Credentials dict or None if cannot obtain
        """
        # Check cached credentials
        if InstagramCredentialManager.CREDENTIALS_FILE.exists():
            with open(InstagramCredentialManager.CREDENTIALS_FILE) as f:
                cached = json.load(f)
                if cached.get("username") == username:
                    logger.info("Using cached Instagram credentials")
                    return cached

        # Get new credentials
        credentials = await InstagramCredentialManager.login_and_get_token(username, password)
        if credentials:
            # Cache it
            with open(InstagramCredentialManager.CREDENTIALS_FILE, "w") as f:
                json.dump(credentials, f, indent=2)
            return credentials

        return None


class YouTubeCredentialManager:
    """Manages YouTube OAuth token (currently uses google-auth-oauthlib)."""

    # Implementation delegated to google-auth-oauthlib
    # Tokens stored in youtube_uploader/token.pickle

    @staticmethod
    def get_token_path() -> Path:
        """Get path to YouTube token file."""
        return Path(__file__).parent.parent.parent / "youtube_uploader" / "token.pickle"

    @staticmethod
    def token_exists() -> bool:
        """Check if YouTube token exists."""
        return YouTubeCredentialManager.get_token_path().exists()


async def test_tiktok_login(username: str = None, password: str = None):
    """Test TikTok login and credential extraction."""
    if not username:
        username = os.getenv("TIKTOK_USERNAME")
    if not password:
        password = os.getenv("TIKTOK_PASSWORD")

    if not username or not password:
        logger.error("TikTok credentials not found in environment")
        return False

    token = await TikTokCredentialManager.get_valid_token(username, password)
    if token:
        logger.info(f"✓ TikTok token obtained: {token[:20]}...")
        return True
    else:
        logger.error("✗ Failed to obtain TikTok token")
        return False


async def test_instagram_login(username: str = None, password: str = None):
    """Test Instagram login and credential extraction."""
    if not username:
        username = os.getenv("INSTAGRAM_USERNAME")
    if not password:
        password = os.getenv("INSTAGRAM_PASSWORD")

    if not username or not password:
        logger.error("Instagram credentials not found in environment")
        return False

    creds = await InstagramCredentialManager.get_valid_credentials(username, password)
    if creds:
        logger.info(f"✓ Instagram credentials obtained for {creds.get('username')}")
        return True
    else:
        logger.error("✗ Failed to obtain Instagram credentials")
        return False


async def main():
    """Test both platforms."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Testing platform credential extraction...")

    tiktok_ok = await test_tiktok_login()
    instagram_ok = await test_instagram_login()

    logger.info(f"\nResults:")
    logger.info(f"  TikTok: {'✓ PASS' if tiktok_ok else '✗ FAIL'}")
    logger.info(f"  Instagram: {'✓ PASS' if instagram_ok else '✗ FAIL'}")

    return tiktok_ok and instagram_ok


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
