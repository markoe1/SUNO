"""Whop HTTP client using official Whop API with Bearer token authentication.

Uses WHOP_API_KEY from environment for all API calls.
"""

import logging
import os
import random
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

WHOP_API_BASE_URL = "https://api.whop.com/api/v1"
WHOP_API_KEY = os.getenv("WHOP_API_KEY", "")
REQUEST_DELAY_MIN = float(os.getenv("WHOP_REQUEST_DELAY_MIN", "0.5"))
REQUEST_DELAY_MAX = float(os.getenv("WHOP_REQUEST_DELAY_MAX", "1.5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = int(os.getenv("RETRY_BACKOFF_BASE", "60"))

class WhopAuthError(Exception):
    """Raised when the Whop session is expired or invalid (HTTP 401/403)."""


class WhopRateLimitError(Exception):
    """Raised when Whop rate limits us (HTTP 429)."""


def _random_delay():
    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    time.sleep(delay)


class WhopClient:
    """HTTP client for Whop using official API with Bearer token."""

    def __init__(self, cookies: dict[str, str] = None, api_key: str = None):
        # Support legacy cookies parameter for backward compatibility, but use API key
        self._api_key = api_key or WHOP_API_KEY
        if not self._api_key:
            raise WhopAuthError("WHOP_API_KEY environment variable not set")

        self._client = httpx.Client(
            base_url=WHOP_API_BASE_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
            follow_redirects=True,
        )

    def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                _random_delay()
                resp = self._client.request(method, url, **kwargs)
                if resp.status_code == 401 or resp.status_code == 403:
                    raise WhopAuthError(f"Whop auth failed: HTTP {resp.status_code}")
                if resp.status_code == 429:
                    wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning("Whop rate limit hit, waiting %ds (attempt %d)", wait, attempt + 1)
                    time.sleep(wait)
                    last_exc = WhopRateLimitError("Rate limited by Whop")
                    continue
                if resp.status_code >= 500:
                    wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning("Whop server error %d, retrying in %ds", resp.status_code, wait)
                    time.sleep(wait)
                    last_exc = Exception(f"Whop server error: {resp.status_code}")
                    continue
                return resp
            except (WhopAuthError, WhopRateLimitError):
                raise
            except httpx.HTTPError as exc:
                wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning("Whop HTTP error: %s, retrying in %ds", exc, wait)
                time.sleep(wait)
                last_exc = exc

        if last_exc:
            raise last_exc
        raise Exception("Max retries exceeded")

    def validate_session(self) -> bool:
        """Validate that API key is valid by fetching user info."""
        try:
            resp = self._request_with_retry("GET", "/users/me")
            return resp.status_code == 200
        except WhopAuthError:
            return False
        except Exception as exc:
            logger.error("validate_session error: %s", exc)
            return False

    def list_campaigns(self) -> list[dict]:
        """Fetch available ad campaigns from official Whop API.

        Calls GET /ad_campaigns to retrieve all campaigns available to the authenticated user.
        """
        try:
            # Official Whop API endpoint for ad campaigns
            resp = self._request_with_retry("GET", "/ad_campaigns?limit=100")
            if resp.status_code != 200:
                logger.error("list_campaigns: HTTP %d", resp.status_code)
                return []

            data = resp.json()
            campaigns = data.get("data", data.get("campaigns", []))
            if not isinstance(campaigns, list):
                campaigns = [campaigns] if campaigns else []

            logger.info("list_campaigns: found %d campaigns", len(campaigns))
            return [self._normalize_campaign(c) for c in campaigns]

        except WhopAuthError:
            raise
        except Exception as exc:
            logger.error("list_campaigns error: %s", exc)
            return []

    def submit_clip(self, campaign_id: str, clip_url: str) -> dict:
        """Submit a clip URL to a Whop campaign via official API."""
        payload = {
            "campaign_id": campaign_id,
            "clip_url": clip_url,
        }
        try:
            # Official Whop API endpoint for submissions
            resp = self._request_with_retry("POST", "/submissions", json=payload)
            body_text = resp.text[:1000]

            if resp.status_code in (200, 201):
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                return {
                    "success": True,
                    "submission_id": data.get("id") or data.get("submission_id"),
                    "error": None,
                }
            else:
                logger.warning("submit_clip HTTP %d body=%s", resp.status_code, body_text)
                return {
                    "success": False,
                    "submission_id": None,
                    "error": f"HTTP {resp.status_code}: {body_text}",
                }
        except WhopAuthError:
            raise
        except Exception as exc:
            return {"success": False, "submission_id": None, "error": str(exc)}

    def check_submission(self, submission_id: str) -> dict:
        """Check the status of a previously submitted clip via official API."""
        try:
            resp = self._request_with_retry("GET", f"/submissions/{submission_id}")
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "submission_id": submission_id,
                    "status": data.get("status", "unknown"),
                    "error": None,
                }
            else:
                return {
                    "submission_id": submission_id,
                    "status": "unknown",
                    "error": f"HTTP {resp.status_code}",
                }
        except WhopAuthError:
            raise
        except Exception as exc:
            return {"submission_id": submission_id, "status": "unknown", "error": str(exc)}

    @staticmethod
    def _normalize_campaign(raw: dict) -> dict:
        """Normalize a raw Whop campaign dict to our internal schema."""
        return {
            "whop_campaign_id": str(raw.get("id", raw.get("campaign_id", ""))),
            "name": raw.get("name", raw.get("title", "Unnamed Campaign")),
            "cpm": float(raw.get("cpm", 0) or 0),
            "budget_remaining": float(raw.get("budget_remaining", 0) or 0) if raw.get("budget_remaining") is not None else None,
            "is_free": bool(raw.get("is_free", False)),
            "drive_url": raw.get("drive_url") or raw.get("asset_url"),
            "youtube_url": raw.get("youtube_url") or raw.get("video_url"),
            "allowed_platforms": raw.get("allowed_platforms") or raw.get("platforms"),
            "active": bool(raw.get("active", raw.get("is_active", True))),
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._client.close()


class DryRunWhopClient:
    """Same interface as WhopClient but returns mock data and logs DRY RUN."""

    def __init__(self, cookies: dict = None, api_key: str = None):
        # Backward compatible with both cookies and api_key parameters
        self._api_key = api_key or ""

    def validate_session(self) -> bool:
        logger.info("DRY RUN: validate_session -> True")
        return True

    def list_campaigns(self) -> list[dict]:
        logger.info("DRY RUN: list_campaigns -> mock data")
        return [
            {
                "whop_campaign_id": "dry_run_camp_001",
                "name": "DRY RUN Campaign A",
                "cpm": 10.0,
                "budget_remaining": 999.0,
                "is_free": False,
                "drive_url": "https://drive.google.com/drive/folders/dryrun",
                "youtube_url": "https://www.youtube.com/watch?v=dryrun",
                "allowed_platforms": "TikTok,Instagram,YouTube",
                "active": True,
            }
        ]

    def submit_clip(self, campaign_id: str, clip_url: str) -> dict:
        logger.info("DRY RUN: submit_clip campaign=%s url=%s", campaign_id, clip_url)
        return {
            "success": True,
            "submission_id": f"dry_sub_{int(time.time())}",
            "error": None,
        }

    def check_submission(self, submission_id: str) -> dict:
        logger.info("DRY RUN: check_submission id=%s", submission_id)
        return {
            "submission_id": submission_id,
            "status": "submitted",
            "error": None,
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
