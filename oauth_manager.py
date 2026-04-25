"""
OAuth Token Management for Social Media Platforms
Handles token acquisition, refresh, and storage
"""

import logging
import json
import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()

logger = logging.getLogger(__name__)

TOKENS_FILE = "data/oauth_tokens.json"


class OAuthManager:
    """Manages OAuth tokens for TikTok, Instagram, and YouTube."""

    def __init__(self):
        Path("data").mkdir(exist_ok=True)
        self.tokens_file = TOKENS_FILE
        self.tokens = self._load_tokens()

    def _load_tokens(self) -> Dict:
        """Load stored tokens from file."""
        if os.path.exists(self.tokens_file):
            try:
                with open(self.tokens_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load tokens: {e}")
        return {}

    def _save_tokens(self):
        """Save tokens to file."""
        try:
            with open(self.tokens_file, 'w') as f:
                json.dump(self.tokens, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")

    # =========================================================================
    # TIKTOK OAUTH
    # =========================================================================

    def get_tiktok_access_token(self) -> Optional[str]:
        """
        Get TikTok access token.

        Uses client_key + client_secret to get OAuth token.
        Expected env vars:
        - TIKTOK_KEY (or TIKTOK_CLIENT_ID)
        - TIKTOK_SECRET (or TIKTOK_CLIENT_SECRET)
        """
        # Check if we already have a valid token
        if "tiktok" in self.tokens:
            token_info = self.tokens["tiktok"]
            if token_info.get("access_token") and not self._is_token_expired(token_info):
                return token_info["access_token"]

        # Get new token - try both naming conventions
        client_key = os.getenv("TIKTOK_KEY") or os.getenv("TIKTOK_CLIENT_ID") or os.getenv("TIKTOK_CLIENT_KEY")
        client_secret = os.getenv("TIKTOK_SECRET") or os.getenv("TIKTOK_CLIENT_SECRET")

        if not client_key or not client_secret:
            logger.warning("TikTok: Missing credentials. Expected one of:\n"
                          "  - TIKTOK_KEY + TIKTOK_SECRET\n"
                          "  - TIKTOK_CLIENT_ID + TIKTOK_CLIENT_SECRET\n"
                          "  - TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET")
            return None

        try:
            response = requests.post(
                "https://open-api.tiktok.com/v1/oauth/token/",
                data={
                    "client_key": client_key,
                    "client_secret": client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                access_token = data.get("data", {}).get("access_token")

                if access_token:
                    # Store token with expiry
                    self.tokens["tiktok"] = {
                        "access_token": access_token,
                        "expires_at": (
                            datetime.now() + timedelta(seconds=data.get("data", {}).get("expires_in", 7200))
                        ).isoformat(),
                    }
                    self._save_tokens()
                    logger.info("TikTok: OAuth token acquired")
                    return access_token
            else:
                logger.error(f"TikTok OAuth failed: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"TikTok OAuth error: {e}")

        return None

    # =========================================================================
    # INSTAGRAM OAUTH (Meta Graph API)
    # =========================================================================

    def get_instagram_credentials(self) -> Optional[Dict]:
        """
        Get Instagram/Meta credentials.

        For now, returns placeholder. In production, would implement:
        1. OAuth flow to get user access token
        2. Get business account ID from user
        3. Get Instagram account ID from business account
        """
        access_token = os.getenv("META_ACCESS_TOKEN")
        ig_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

        if not access_token or not ig_account_id:
            logger.warning("Instagram: Missing META_ACCESS_TOKEN or INSTAGRAM_BUSINESS_ACCOUNT_ID")
            return None

        return {
            "access_token": access_token,
            "instagram_business_account_id": ig_account_id,
        }

    # =========================================================================
    # YOUTUBE OAUTH (Google OAuth)
    # =========================================================================

    def get_youtube_credentials(self) -> Optional[Dict]:
        """
        Get YouTube credentials.

        Supports two methods:
        1. Direct access token
        2. Google auth credentials object (from google-auth library)
        """
        # Method 1: Direct access token
        access_token = os.getenv("YOUTUBE_ACCESS_TOKEN")
        if access_token:
            return {"access_token": access_token}

        # Method 2: Cached credentials from token.pickle
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            token_file = "data/youtube_token.pickle"
            if os.path.exists(token_file):
                import pickle
                with open(token_file, 'rb') as f:
                    creds = pickle.load(f)

                if creds.expired and creds.refresh_token:
                    logger.info("YouTube: Refreshing expired token")
                    request = Request()
                    creds.refresh(request)

                    # Save refreshed token
                    with open(token_file, 'wb') as f:
                        pickle.dump(creds, f)

                return {"creds_object": creds, "access_token": creds.token}
        except ImportError:
            logger.debug("google-auth not installed, skipping YouTube token.pickle")
        except Exception as e:
            logger.warning(f"YouTube token.pickle load failed: {e}")

        logger.warning("YouTube: No valid credentials found")
        return None

    # =========================================================================
    # UTILITY
    # =========================================================================

    def _is_token_expired(self, token_info: Dict) -> bool:
        """Check if token is expired."""
        if "expires_at" not in token_info:
            return True

        try:
            expires_at = datetime.fromisoformat(token_info["expires_at"])
            return datetime.now() >= expires_at
        except Exception:
            return True

    def clear_tokens(self):
        """Clear all stored tokens."""
        self.tokens = {}
        self._save_tokens()
        logger.info("All tokens cleared")

    def get_all_tokens(self) -> Dict:
        """Get all stored tokens (for debugging)."""
        return {
            k: {
                "access_token": v.get("access_token", "")[:20] + "...",
                "expires_at": v.get("expires_at"),
            }
            for k, v in self.tokens.items()
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    oauth = OAuthManager()

    print("Testing OAuth Manager...")

    # Test TikTok
    tiktok_token = oauth.get_tiktok_access_token()
    print(f"TikTok token: {tiktok_token[:20] + '...' if tiktok_token else 'MISSING'}")

    # Test Instagram
    ig_creds = oauth.get_instagram_credentials()
    print(f"Instagram credentials: {bool(ig_creds)}")

    # Test YouTube
    yt_creds = oauth.get_youtube_credentials()
    print(f"YouTube credentials: {bool(yt_creds)}")

    print(f"Stored tokens: {oauth.get_all_tokens()}")
