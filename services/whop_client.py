"""Whop HTTP client using browser-exported session cookies.

The user exports their Whop cookies from DevTools → Application → Cookies
and pastes them into our settings UI. We encrypt them and use them here.

We never automate Whop login — Cloudflare + 2FA makes that unreliable.
"""

import asyncio
import logging
import os
import random
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

WHOP_BASE_URL = os.getenv("WHOP_BASE_URL", "https://whop.com")
REQUEST_DELAY_MIN = float(os.getenv("WHOP_REQUEST_DELAY_MIN", "2"))
REQUEST_DELAY_MAX = float(os.getenv("WHOP_REQUEST_DELAY_MAX", "5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = int(os.getenv("RETRY_BACKOFF_BASE", "60"))

# Clipping API paths — override via env if Whop changes their internal routes.
# These are undocumented internal endpoints discovered by inspecting browser traffic.
# If submissions return 404, capture the real path from DevTools Network tab and set here.
WHOP_CAMPAIGNS_PATH  = os.getenv("WHOP_CAMPAIGNS_PATH",  "/api/v5/clipping/campaigns")
WHOP_SUBMIT_PATH     = os.getenv("WHOP_SUBMIT_PATH",     "/api/v5/clipping/campaigns/{campaign_id}/submissions")
WHOP_CHECK_PATH      = os.getenv("WHOP_CHECK_PATH",      "/api/v5/clipping/submissions/{submission_id}")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class WhopAuthError(Exception):
    """Raised when the Whop session is expired or invalid (HTTP 401/403)."""


class WhopRateLimitError(Exception):
    """Raised when Whop rate limits us (HTTP 429)."""


def _random_delay():
    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    time.sleep(delay)


class WhopClient:
    """HTTP client for Whop using stored browser session cookies."""

    def __init__(self, cookies: dict[str, str]):
        self._cookies = cookies
        self._client = httpx.Client(
            base_url=WHOP_BASE_URL,
            cookies=cookies,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": WHOP_BASE_URL + "/",
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
        """Validate that stored cookies are still active."""
        try:
            resp = self._request_with_retry("GET", "/api/v5/me")
            return resp.status_code == 200
        except WhopAuthError:
            return False
        except Exception as exc:
            logger.error("validate_session error: %s", exc)
            return False

    def list_campaigns(self) -> list[dict]:
        """Fetch available clipping campaigns from Whop.

        Tries the configured WHOP_CAMPAIGNS_PATH first, then two fallback paths.
        All paths can be overridden via env vars if Whop changes their internal routes.
        """
        paths_to_try = [
            WHOP_CAMPAIGNS_PATH + "?limit=50",
            "/clipping/campaigns",
            "/api/v5/clipping/campaigns?limit=50",
        ]
        # Deduplicate while preserving order
        seen = set()
        unique_paths = []
        for p in paths_to_try:
            if p not in seen:
                seen.add(p)
                unique_paths.append(p)

        try:
            for path in unique_paths:
                try:
                    resp = self._request_with_retry("GET", path)
                    if resp.status_code == 404:
                        logger.warning("list_campaigns: 404 at %s — trying next path", path)
                        continue
                    if resp.status_code != 200:
                        logger.error("list_campaigns: HTTP %d at %s", resp.status_code, path)
                        continue
                    data = resp.json()
                    campaigns = data.get("campaigns", data.get("data", data if isinstance(data, list) else []))
                    if isinstance(campaigns, list) and campaigns:
                        logger.info("list_campaigns: found %d campaigns via %s", len(campaigns), path)
                        return [self._normalize_campaign(c) for c in campaigns]
                except WhopAuthError:
                    raise
                except Exception as exc:
                    logger.warning("list_campaigns: error at %s: %s", path, exc)
                    continue

            logger.warning(
                "list_campaigns: all paths returned empty or failed. "
                "Set WHOP_CAMPAIGNS_PATH env var to the correct internal endpoint."
            )
            return []
        except WhopAuthError:
            raise
        except Exception as exc:
            logger.error("list_campaigns error: %s", exc)
            return []

    def submit_clip(self, campaign_id: str, clip_url: str) -> dict:
        """Submit a clip URL to a Whop campaign."""
        path = WHOP_SUBMIT_PATH.format(campaign_id=campaign_id)
        payload = {
            "campaign_id": campaign_id,
            "clip_url": clip_url,
        }
        try:
            resp = self._request_with_retry("POST", path, json=payload)
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
            elif resp.status_code == 404:
                logger.error(
                    "submit_clip 404 — endpoint may be wrong. path=%s response=%s\n"
                    "To fix: capture the real path from DevTools Network tab while "
                    "submitting a clip manually on whop.com, then set WHOP_SUBMIT_PATH env var.",
                    path,
                    body_text,
                )
                return {
                    "success": False,
                    "submission_id": None,
                    "error": (
                        f"404 — endpoint not found ({path}). "
                        "Check logs for instructions to fix WHOP_SUBMIT_PATH."
                    ),
                }
            else:
                logger.warning("submit_clip HTTP %d path=%s body=%s", resp.status_code, path, body_text)
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
        """Check the status of a previously submitted clip."""
        path = WHOP_CHECK_PATH.format(submission_id=submission_id)
        try:
            resp = self._request_with_retry("GET", path)
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

    def __init__(self, cookies: dict = None):
        self._cookies = cookies or {}

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
