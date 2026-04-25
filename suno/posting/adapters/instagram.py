"""
Instagram Platform Adapter
Posts Reels/videos to Instagram via Meta Graph API.
"""

import logging
import requests
from typing import Dict, Any, Optional
from suno.posting.adapters.base import PlatformAdapter, PostingResult, PostingStatus

logger = logging.getLogger(__name__)


class InstagramAdapter(PlatformAdapter):
    """Instagram posting adapter using Meta Graph API."""

    @property
    def platform_name(self) -> str:
        return "instagram"

    def validate_account(self, account_credentials: Dict[str, str]) -> bool:
        """
        Validate Instagram account.

        Credentials expected:
        - access_token: Meta Graph API access token
        - instagram_business_account_id: Business account ID
        """
        access_token = account_credentials.get("access_token")
        ig_account_id = account_credentials.get("instagram_business_account_id")

        if not all([access_token, ig_account_id]):
            logger.warning("Instagram: Missing required credentials")
            return False

        try:
            # Verify access token with simple API call
            response = requests.get(
                f"https://graph.instagram.com/v18.0/{ig_account_id}",
                params={"access_token": access_token},
                timeout=5,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Instagram account validation failed: {e}")
            return False

    def prepare_payload(
        self,
        clip_url: str,
        caption: str,
        hashtags: list,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepare Instagram Reels payload.

        Instagram accepts:
        - video_url: Direct URL to video file
        - caption: Post text (max 2200 chars)
        - hashtags: Included in caption
        """
        # Build caption with hashtags
        full_caption = caption
        if hashtags:
            full_caption += "\n\n" + " ".join(hashtags)

        # Enforce Instagram limits
        if len(full_caption) > 2200:
            full_caption = full_caption[:2197] + "..."

        return {
            "video_url": clip_url,
            "caption": full_caption,
            "media_type": "REELS",  # REELS, VIDEO, CAROUSEL
        }

    def post(
        self,
        account_credentials: Dict[str, str],
        payload: Dict[str, Any],
    ) -> PostingResult:
        """
        Post Reel to Instagram.

        Uses Meta Graph API to create media container and publish.
        """
        access_token = account_credentials.get("access_token")
        ig_account_id = account_credentials.get("instagram_business_account_id")

        if not all([access_token, ig_account_id]):
            return PostingResult(
                status=PostingStatus.PERMANENT_ERROR,
                error_message="Missing credentials",
            )

        try:
            # Step 1: Create media container
            container_response = requests.post(
                f"https://graph.instagram.com/v18.0/{ig_account_id}/media",
                json={
                    "media_type": payload.get("media_type"),
                    "video_url": payload.get("video_url"),
                    "caption": payload.get("caption"),
                },
                params={"access_token": access_token},
                timeout=30,
            )

            if container_response.status_code != 201:
                error_msg = container_response.json().get("error", {}).get("message", "Unknown error")
                error_status = self._classify_error(container_response.status_code, error_msg)

                logger.warning(f"Instagram: Container creation failed: {error_msg}")
                return PostingResult(
                    status=error_status,
                    error_message=error_msg,
                )

            container_id = container_response.json().get("id")

            # Step 2: Publish (finish publishing)
            publish_response = requests.post(
                f"https://graph.instagram.com/v18.0/{ig_account_id}/media_publish",
                json={"creation_id": container_id},
                params={"access_token": access_token},
                timeout=30,
            )

            if publish_response.status_code == 200:
                media_id = publish_response.json().get("id")
                posted_url = f"https://www.instagram.com/p/{media_id}/"

                logger.info(f"Instagram: Posted Reel {media_id}")
                return PostingResult(
                    status=PostingStatus.SUCCESS,
                    posted_url=posted_url,
                    post_id=media_id,
                    metadata={"media_id": media_id},
                )
            else:
                error_msg = publish_response.json().get("error", {}).get("message", "Unknown error")
                error_status = self._classify_error(publish_response.status_code, error_msg)

                logger.warning(f"Instagram: Publishing failed: {error_msg}")
                return PostingResult(
                    status=error_status,
                    error_message=error_msg,
                )

        except requests.Timeout:
            logger.warning("Instagram: Request timeout (retryable)")
            return PostingResult(
                status=PostingStatus.RETRYABLE_ERROR,
                error_message="Request timeout",
            )
        except Exception as e:
            logger.error(f"Instagram: Unexpected error: {e}")
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
        """Instagram doesn't support back-submission."""
        logger.debug(f"Instagram: Result stored in database: {posted_url}")
        return True
