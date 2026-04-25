"""
Twitter Platform Adapter
Posts videos to Twitter/X via Twitter API v2.
"""

import logging
import requests
from typing import Dict, Any
from suno.posting.adapters.base import PlatformAdapter, PostingResult, PostingStatus

logger = logging.getLogger(__name__)


class TwitterAdapter(PlatformAdapter):
    """Twitter/X posting adapter using Twitter API v2."""

    @property
    def platform_name(self) -> str:
        return "twitter"

    def validate_account(self, account_credentials: Dict[str, str]) -> bool:
        """Validate Twitter account credentials."""
        access_token = account_credentials.get("access_token")
        if not access_token:
            logger.warning("Twitter: Missing access_token")
            return False

        try:
            response = requests.get(
                "https://api.twitter.com/2/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Twitter account validation failed: {e}")
            return False

    def prepare_payload(
        self,
        clip_url: str,
        caption: str,
        hashtags: list,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prepare Twitter post payload."""
        # Build caption with hashtags (280 char limit)
        full_text = caption
        if hashtags:
            tags_text = " ".join(hashtags)
            if len(full_text) + len(tags_text) + 2 <= 280:
                full_text += "\n\n" + tags_text
            else:
                full_text = full_text[:280 - len(tags_text) - 2] + "\n\n" + tags_text[:100]

        full_text = full_text[:280]

        return {
            "text": full_text,
            "media_url": clip_url,
        }

    def post(
        self,
        account_credentials: Dict[str, str],
        payload: Dict[str, Any],
    ) -> PostingResult:
        """
        Post tweet with video to Twitter.

        Flow:
        1. Upload media (video)
        2. Create tweet with media ID
        """
        access_token = account_credentials.get("access_token")
        if not access_token:
            return PostingResult(
                status=PostingStatus.PERMANENT_ERROR,
                error_message="Missing access_token",
            )

        try:
            # Step 1: Upload media
            media_response = requests.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                files={"media": requests.get(payload.get("media_url")).content},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )

            if media_response.status_code != 200:
                error_msg = media_response.json().get("errors", [{}])[0].get("message", "Media upload failed")
                return PostingResult(
                    status=PostingStatus.RETRYABLE_ERROR,
                    error_message=error_msg,
                )

            media_id = media_response.json().get("media_id_string")

            # Step 2: Create tweet with media
            tweet_response = requests.post(
                "https://api.twitter.com/2/tweets",
                json={
                    "text": payload.get("text"),
                    "media": {"media_ids": [media_id]},
                },
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )

            if tweet_response.status_code == 201:
                tweet_id = tweet_response.json().get("data", {}).get("id")
                posted_url = f"https://twitter.com/user/status/{tweet_id}"

                logger.info(f"Twitter: Posted tweet {tweet_id}")
                return PostingResult(
                    status=PostingStatus.SUCCESS,
                    posted_url=posted_url,
                    post_id=tweet_id,
                )
            else:
                error_msg = tweet_response.json().get("errors", [{}])[0].get("message", "Tweet creation failed")
                error_status = self._classify_error(tweet_response.status_code, error_msg)

                return PostingResult(
                    status=error_status,
                    error_message=error_msg,
                )

        except Exception as e:
            logger.error(f"Twitter: Error posting: {e}")
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
        """Twitter doesn't support back-submission."""
        return True
