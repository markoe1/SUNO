"""
Bluesky Platform Adapter
Posts to Bluesky via AT Protocol API.
"""

import logging
import requests
import base64
from typing import Dict, Any
from suno.posting.adapters.base import PlatformAdapter, PostingResult, PostingStatus

logger = logging.getLogger(__name__)


class BlueSkyAdapter(PlatformAdapter):
    """Bluesky posting adapter using AT Protocol API."""

    @property
    def platform_name(self) -> str:
        return "bluesky"

    def validate_account(self, account_credentials: Dict[str, str]) -> bool:
        """Validate Bluesky account credentials."""
        pds_url = account_credentials.get("pds_url", "https://bsky.social")
        access_token = account_credentials.get("access_token")

        if not access_token:
            logger.warning("Bluesky: Missing access_token")
            return False

        try:
            response = requests.get(
                f"{pds_url}/xrpc/com.atproto.server.getSession",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Bluesky account validation failed: {e}")
            return False

    def prepare_payload(
        self,
        clip_url: str,
        caption: str,
        hashtags: list,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prepare Bluesky post payload."""
        # Build caption with hashtags
        full_text = caption
        if hashtags:
            full_text += "\n\n" + " ".join(hashtags)

        # Bluesky limit: 300 chars
        if len(full_text) > 300:
            full_text = full_text[:297] + "..."

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
        Post to Bluesky.

        Flow:
        1. Upload blob (video)
        2. Create record (post) with blob reference
        """
        pds_url = account_credentials.get("pds_url", "https://bsky.social")
        access_token = account_credentials.get("access_token")
        did = account_credentials.get("did")  # Decentralized ID

        if not all([access_token, did]):
            return PostingResult(
                status=PostingStatus.PERMANENT_ERROR,
                error_message="Missing credentials",
            )

        try:
            # Step 1: Upload media blob
            media_data = requests.get(payload.get("media_url")).content
            blob_response = requests.post(
                f"{pds_url}/xrpc/com.atproto.repo.uploadBlob",
                data=media_data,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "video/mp4",
                },
                timeout=30,
            )

            if blob_response.status_code != 200:
                error_msg = blob_response.json().get("message", "Blob upload failed")
                return PostingResult(
                    status=PostingStatus.RETRYABLE_ERROR,
                    error_message=error_msg,
                )

            blob_ref = blob_response.json().get("blob")

            # Step 2: Create post record
            from datetime import datetime, timezone

            post_response = requests.post(
                f"{pds_url}/xrpc/com.atproto.repo.createRecord",
                json={
                    "repo": did,
                    "collection": "app.bsky.feed.post",
                    "record": {
                        "text": payload.get("text"),
                        "embed": {
                            "$type": "app.bsky.embed.video",
                            "video": blob_ref,
                        },
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                    },
                },
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )

            if post_response.status_code == 200:
                uri = post_response.json().get("uri")
                cid = post_response.json().get("cid")
                posted_url = f"https://bsky.app/profile/{did}/post/{cid.split('/')[-1]}"

                logger.info(f"Bluesky: Posted {uri}")
                return PostingResult(
                    status=PostingStatus.SUCCESS,
                    posted_url=posted_url,
                    post_id=uri,
                )
            else:
                error_msg = post_response.json().get("message", "Post creation failed")
                error_status = self._classify_error(post_response.status_code, error_msg)

                return PostingResult(
                    status=error_status,
                    error_message=error_msg,
                )

        except Exception as e:
            logger.error(f"Bluesky: Error posting: {e}")
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
        """Bluesky doesn't support back-submission."""
        return True
