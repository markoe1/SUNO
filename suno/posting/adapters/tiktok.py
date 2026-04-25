"""
TikTok Platform Adapter
Posts videos to TikTok via Open API.
"""

import logging
import requests
from typing import Dict, Any, Optional
from suno.posting.adapters.base import PlatformAdapter, PostingResult, PostingStatus

logger = logging.getLogger(__name__)


class TikTokAdapter(PlatformAdapter):
    """TikTok posting adapter using TikTok Open API v1."""

    @property
    def platform_name(self) -> str:
        return "tiktok"

    def validate_account(self, account_credentials: Dict[str, str]) -> bool:
        """
        Validate TikTok account.

        Credentials expected:
        - access_token: OAuth access token for user
        - client_id: TikTok app client ID
        """
        access_token = account_credentials.get("access_token")
        if not access_token:
            logger.warning("TikTok: Missing access_token")
            return False

        try:
            # Call TikTok API to verify token is valid
            response = requests.get(
                "https://open-api.tiktok.com/v1/oauth/user/info",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"TikTok account validation failed: {e}")
            return False

    def prepare_payload(
        self,
        clip_url: str,
        caption: str,
        hashtags: list,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepare TikTok posting payload.

        TikTok accepts:
        - video_url: Direct URL to video file (MP4, MOV, etc.)
        - caption: Post text (max 2200 chars)
        - hashtags: List of hashtags
        """
        # Build caption with hashtags
        full_caption = caption
        if hashtags:
            full_caption += "\n\n" + " ".join(hashtags)

        # Track if truncation occurs
        was_truncated = False
        if len(full_caption) > 2200:
            logger.warning(f"TikTok caption truncated from {len(full_caption)} to 2200 chars")
            full_caption = full_caption[:2197] + "..."
            was_truncated = True

        return {
            "video_url": clip_url,
            "caption": full_caption,
            "privacy_level": "PUBLIC",  # PUBLIC, FRIEND, PRIVATE
            "caption_was_truncated": was_truncated,  # Track truncation
        }

    def post(
        self,
        account_credentials: Dict[str, str],
        payload: Dict[str, Any],
    ) -> PostingResult:
        """
        Post video to TikTok.

        Calls TikTok Open API video/upload endpoint.
        """
        access_token = account_credentials.get("access_token")
        if not access_token:
            return PostingResult(
                status=PostingStatus.PERMANENT_ERROR,
                error_message="Missing access_token",
            )

        try:
            # Call TikTok API to upload video
            response = requests.post(
                "https://open-api.tiktok.com/v1/video/upload",
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                video_id = data.get("data", {}).get("video_id")
                posted_url = f"https://www.tiktok.com/@user/video/{video_id}"

                logger.info(f"TikTok: Posted video {video_id}")
                return PostingResult(
                    status=PostingStatus.SUCCESS,
                    posted_url=posted_url,
                    post_id=video_id,
                    metadata={"video_id": video_id},
                )
            else:
                # Classify error
                error_msg = response.json().get("message", "Unknown error")
                error_status = self._classify_error(response.status_code, error_msg)

                logger.warning(f"TikTok: Posting failed ({response.status_code}): {error_msg}")
                return PostingResult(
                    status=error_status,
                    error_message=error_msg,
                )

        except requests.Timeout:
            logger.warning("TikTok: Request timeout (retryable)")
            return PostingResult(
                status=PostingStatus.RETRYABLE_ERROR,
                error_message="Request timeout",
            )
        except Exception as e:
            logger.error(f"TikTok: Unexpected error: {e}")
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
        """
        Submit result back to source.

        TikTok doesn't have a built-in way to submit results back,
        but we could use webhooks or analytics later.
        For now, return True (result stored in SUNO database).
        """
        logger.debug(f"TikTok: Result tracking would send to analytics: {posted_url}")
        return True
