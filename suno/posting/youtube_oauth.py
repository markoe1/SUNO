"""
YouTube OAuth Handler — Gets proper access tokens with upload scopes.
"""

import logging
import pickle
import os
from pathlib import Path
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError

logger = logging.getLogger(__name__)

# OAuth 2.0 scopes for YouTube upload
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

CREDENTIALS_FILE = Path(__file__).parent.parent.parent / "youtube_uploader" / "credentials.json"
TOKEN_FILE = Path(__file__).parent.parent.parent / "youtube_uploader" / "token.pickle"


class YouTubeOAuthManager:
    """Manages YouTube OAuth tokens with proper scopes."""

    @staticmethod
    def authenticate(force_refresh: bool = False) -> Optional[Credentials]:
        """
        Authenticate with YouTube API.

        Args:
            force_refresh: If True, forces re-authorization even if token exists

        Returns:
            Credentials object if successful, None otherwise
        """
        # Try to load existing token
        if not force_refresh and TOKEN_FILE.exists():
            try:
                with open(TOKEN_FILE, "rb") as f:
                    creds = pickle.load(f)

                # Check if token needs refresh
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Token expired, refreshing...")
                    try:
                        request = Request()
                        creds.refresh(request)
                        logger.info("Token refreshed successfully")
                    except RefreshError as e:
                        logger.warning(f"Token refresh failed: {e}")
                        logger.info("Will re-authorize with fresh OAuth flow")
                        return YouTubeOAuthManager._oauth_flow()

                return creds
            except Exception as e:
                logger.warning(f"Failed to load existing token: {e}")
                return YouTubeOAuthManager._oauth_flow()

        # Fresh OAuth flow
        return YouTubeOAuthManager._oauth_flow()

    @staticmethod
    def _oauth_flow() -> Optional[Credentials]:
        """
        Execute OAuth flow to get new token.
        Opens browser for user to authorize.
        """
        if not CREDENTIALS_FILE.exists():
            logger.error(f"Credentials file not found: {CREDENTIALS_FILE}")
            logger.error("Download OAuth credentials from Google Cloud Console")
            return None

        try:
            logger.info(f"Starting OAuth flow...")
            logger.info(f"Credentials file: {CREDENTIALS_FILE}")

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE),
                scopes=SCOPES
            )

            # Run local server for OAuth callback
            creds = flow.run_local_server(port=0)

            # Save token
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(creds, f)

            logger.info(f"Token saved to {TOKEN_FILE}")
            return creds

        except Exception as e:
            logger.error(f"OAuth flow failed: {e}")
            return None

    @staticmethod
    def get_access_token(force_refresh: bool = False) -> Optional[str]:
        """Get valid access token for YouTube API."""
        creds = YouTubeOAuthManager.authenticate(force_refresh=force_refresh)
        if creds and creds.token:
            return creds.token
        return None

    @staticmethod
    def validate_scopes() -> bool:
        """Check if current token has proper scopes."""
        if not TOKEN_FILE.exists():
            logger.warning("No token file found")
            return False

        try:
            with open(TOKEN_FILE, "rb") as f:
                creds = pickle.load(f)

            if not creds.scopes:
                logger.warning("Token has no scopes information")
                return False

            has_upload = "https://www.googleapis.com/auth/youtube.upload" in creds.scopes
            has_readonly = "https://www.googleapis.com/auth/youtube.readonly" in creds.scopes

            if has_upload and has_readonly:
                logger.info("Token has proper scopes")
                return True
            else:
                logger.warning(f"Token scopes: {creds.scopes}")
                logger.warning("Missing youtube.upload or youtube.readonly")
                return False

        except Exception as e:
            logger.error(f"Failed to check scopes: {e}")
            return False

    @staticmethod
    def delete_token():
        """Delete the stored token (forces re-authorization on next use)."""
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
            logger.info(f"Deleted token file: {TOKEN_FILE}")
        else:
            logger.info("No token file to delete")

    @staticmethod
    def reset():
        """Force complete re-authorization."""
        YouTubeOAuthManager.delete_token()
        return YouTubeOAuthManager.authenticate(force_refresh=True)
