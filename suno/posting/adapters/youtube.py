"""
YouTube Platform Adapter
Posts Shorts/videos to YouTube via YouTube Data API.
"""

import logging
import requests
from typing import Dict, Any, Optional
from suno.posting.adapters.base import PlatformAdapter, PostingResult, PostingStatus

logger = logging.getLogger(__name__)


class YouTubeAdapter(PlatformAdapter):
    """YouTube posting adapter using YouTube Data API v3."""

    @property
    def platform_name(self) -> str:
        return "youtube"

    def validate_account(self, account_credentials: Dict[str, str]) -> bool:
        """Validate YouTube account credentials."""
        access_token = account_credentials.get("access_token")
        creds_object = account_credentials.get("creds_object")

        if not access_token and not creds_object:
            logger.warning("YouTube: Missing access_token and creds_object")
            return False

        try:
            # If we have a credentials object (from token.pickle), refresh if needed
            if creds_object:
                try:
                    from google.auth.transport.requests import Request
                    if creds_object.expired and creds_object.refresh_token:
                        logger.info("YouTube: Token expired, refreshing...")
                        request = Request()
                        creds_object.refresh(request)
                        access_token = creds_object.token
                        logger.info("YouTube: Token refreshed successfully")
                except Exception as e:
                    logger.warning(f"YouTube: Token refresh failed: {e}")

            if not access_token:
                logger.warning("YouTube: No valid access token after refresh attempt")
                return False

            response = requests.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "id", "mine": "true", "access_token": access_token},
                timeout=5,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"YouTube account validation failed: {e}")
            return False

    def prepare_payload(
        self,
        clip_url: str,
        caption: str,
        hashtags: list,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prepare YouTube video upload payload."""
        full_caption = caption
        if hashtags:
            full_caption += "\n\n" + " ".join(hashtags)

        # YouTube title: caption truncated to 100 chars
        title = caption[:100] if caption else "Untitled"

        return {
            "video_url": clip_url,
            "title": title,
            "description": full_caption,
            "tags": hashtags,
            "privacyStatus": "public",
        }

    def post(
        self,
        account_credentials: Dict[str, str],
        payload: Dict[str, Any],
    ) -> PostingResult:
        """
        Post video to YouTube.

        NOTE: YouTube Data API requires resumable uploads for video files.
        This is a simplified implementation.
        """
        access_token = account_credentials.get("access_token")
        if not access_token:
            return PostingResult(
                status=PostingStatus.PERMANENT_ERROR,
                error_message="Missing access_token",
            )

        try:
            # Simplified: In production, would use resumable upload
            response = requests.post(
                "https://www.googleapis.com/youtube/v3/videos",
                json={
                    "snippet": {
                        "title": payload.get("title"),
                        "description": payload.get("description"),
                        "tags": payload.get("tags"),
                    },
                    "status": {"privacyStatus": payload.get("privacyStatus")},
                },
                params={"part": "snippet,status", "access_token": access_token},
                timeout=30,
            )

            if response.status_code == 200:
                video_id = response.json().get("id")
                posted_url = f"https://www.youtube.com/watch?v={video_id}"

                logger.info(f"YouTube: Posted video {video_id}")
                return PostingResult(
                    status=PostingStatus.SUCCESS,
                    posted_url=posted_url,
                    post_id=video_id,
                )
            else:
                error_msg = response.json().get("error", {}).get("message", "Unknown error")
                error_status = self._classify_error(response.status_code, error_msg)

                return PostingResult(
                    status=error_status,
                    error_message=error_msg,
                )

        except Exception as e:
            logger.error(f"YouTube: Error posting: {e}")
            return PostingResult(
                status=PostingStatus.RETRYABLE_ERROR,
                error_message=str(e),
            )

    def submit_result(
        self,
        account_credentials: Dict[str, str],
        posted_url: str,
        source_clip_url: str,
    ) -> bool:
        """YouTube doesn't support back-submission."""
        return True
