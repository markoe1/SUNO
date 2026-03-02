"""
Whop Scraper
============
Discovers clipping campaigns on Whop, stores them in the DB,
and submits posted clip URLs back to Whop for payout tracking.

Flow:
  1. Login (manual once, session saved to whop_session.json)
  2. Scrape whop.com/discover/clipping
  3. Filter campaigns: CPM >= MIN_CPM, budget >= MIN_BUDGET_REMAINING, free-only
  4. Extract Google Drive + YouTube source links per campaign
  5. Store / update campaign records in DB
  6. After posting: submit clip URLs back atomically
"""

import asyncio
import random
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

import config
from queue_manager import QueueManager, Campaign, Clip, ClipStatus

logger = logging.getLogger(__name__)


class WhopScraper:
    def __init__(self):
        self.queue        = QueueManager()
        self.browser: Optional[Browser]          = None
        self.context: Optional[BrowserContext]   = None
        self.page: Optional[Page]                = None
        self._logged_in   = False
        self.playwright   = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ── Browser lifecycle ─────────────────────────────────────────────────────

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=config.HEADLESS,  # Must be False — Cloudflare blocks headless
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-dev-shm-usage",
            ],
        )

        # Always load session first if it exists — before any navigation
        storage_state = None
        if config.WHOP_SESSION_FILE.exists():
            storage_state = str(config.WHOP_SESSION_FILE)
            logger.info("Loading saved Whop session...")

        self.context = await self.browser.new_context(
            user_agent=random.choice(config.USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            storage_state=storage_state,
        )

        # Hide automation signals from JS
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        self.page = await self.context.new_page()
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Browser started")

    async def close(self):
        if self.context and self._logged_in:
            try:
                await self.context.storage_state(path=str(config.WHOP_SESSION_FILE))
                logger.info("Whop session saved")
            except Exception as e:
                logger.warning(f"Could not save session: {e}")
        try:
            if self.page:    await self.page.close()
            if self.context: await self.context.close()
            if self.browser: await self.browser.close()
            if self.playwright: await self.playwright.stop()
            logger.info("Browser closed")
        except Exception as e:
            logger.debug(f"Cleanup: {e}")

    # ── Login ─────────────────────────────────────────────────────────────────

    async def login(self) -> bool:
        """
        Session-first login flow:
          1. Navigate to whop.com/hub (low-friction landing, CF-friendly)
          2. Human delay — let Cloudflare see a real browser
          3. Check if session is valid (not redirected to /login)
          4. If not logged in, navigate to login and wait for manual completion
        Session is saved automatically on close.
        """
        if self._logged_in:
            return True

        try:
            logger.info("Checking Whop session via hub page...")

            # Step 1: land on hub first — less aggressive than hitting /discover directly
            await self.page.goto(
                "https://whop.com/hub",
                timeout=config.BROWSER_TIMEOUT * 1000,
                wait_until="domcontentloaded",
            )
            # Human-realistic pause — give CF time to fingerprint the browser
            await asyncio.sleep(random.uniform(3, 5))

            url = self.page.url
            logger.info(f"  Landing URL: {url}")

            if "login" not in url and "whop.com" in url:
                self._logged_in = True
                logger.info("Session valid — already logged in")
                return True

            # Session expired or no session — manual login required
            logger.info("")
            logger.info("=" * 60)
            logger.info("MANUAL LOGIN REQUIRED")
            logger.info("=" * 60)
            logger.info("Browser window is open. Log into Whop:")
            logger.info("  1. Enter your email / use social login")
            logger.info("  2. Complete OTP or any verification")
            logger.info("  3. Wait until you see the Whop hub/dashboard")
            logger.info("Session will be saved — you only do this once.")
            logger.info("=" * 60)

            await self.page.goto(
                config.WHOP_LOGIN_URL,
                timeout=config.BROWSER_TIMEOUT * 1000,
                wait_until="domcontentloaded",
            )

            # Poll up to 5 minutes for successful login
            for _ in range(60):
                await asyncio.sleep(5)
                url = self.page.url
                if "login" not in url and "whop.com" in url:
                    self._logged_in = True
                    logger.info("Login successful — session will be saved on close.")
                    return True

            logger.error("Login timed out after 5 minutes.")
            return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    # ── Campaign discovery ────────────────────────────────────────────────────

    async def discover_campaigns(self) -> List[Campaign]:
        """
        Scrape whop.com/discover/clipping and return Campaign objects
        that pass the CPM / budget / free filters.
        """
        if not await self.login():
            return []

        campaigns: List[Campaign] = []

        try:
            # Confirm session on hub first, then navigate to discover
            logger.info("Confirming session on hub before scraping...")
            await self.page.goto(
                "https://whop.com/hub",
                timeout=config.BROWSER_TIMEOUT * 1000,
                wait_until="domcontentloaded",
            )
            await asyncio.sleep(random.uniform(2, 4))

            if "login" in self.page.url:
                logger.error("Session invalid — run --mode login first")
                return []

            logger.info(f"Navigating to {config.WHOP_DISCOVER_URL} ...")
            await asyncio.sleep(random.uniform(1.5, 3))  # human pause before next nav
            await self.page.goto(
                config.WHOP_DISCOVER_URL,
                timeout=config.BROWSER_TIMEOUT * 1000,
                wait_until="domcontentloaded",
            )
            await asyncio.sleep(random.uniform(3, 5))  # let page and CF settle

            # ── scroll to load all campaign cards ──
            for _ in range(5):
                await self.page.keyboard.press("End")
                await asyncio.sleep(random.uniform(1.2, 2.0))

            # ── try to grab campaign card elements ──
            # Whop renders a grid of cards — we try multiple selectors
            card_selectors = [
                "a[href*='/hub/']",
                "a[href*='/clipping/']",
                "[data-testid*='product-card']",
                "article",
                "div[class*='ProductCard']",
                "div[class*='product-card']",
                "div[class*='Card']",
            ]

            card_elements = []
            for sel in card_selectors:
                els = await self.page.query_selector_all(sel)
                if len(els) > 2:
                    card_elements = els
                    logger.info(f"Found {len(els)} cards with selector: {sel}")
                    break

            if not card_elements:
                await self._save_debug_snapshot("no_cards")
                logger.warning("No campaign cards found — debug snapshot saved")
                return []

            # ── parse each card ──
            seen_hrefs = set()
            for el in card_elements:
                try:
                    href = await el.get_attribute("href") or ""
                    if not href or href in seen_hrefs:
                        continue
                    seen_hrefs.add(href)

                    # Build full URL
                    if href.startswith("/"):
                        full_url = f"{config.WHOP_BASE_URL}{href}"
                    elif href.startswith("http"):
                        full_url = href
                    else:
                        continue

                    # Get card text for name
                    text = (await el.inner_text() or "").strip()
                    name = text.split("\n")[0][:80] if text else href

                    # Parse CPM from card text if visible ("$X.XX CPM" or "$X/1K")
                    cpm = self._parse_cpm_from_text(text)

                    # Parse budget
                    budget = self._parse_budget_from_text(text)

                    # Free detection
                    is_free = "free" in text.lower() or "$0" in text

                    # Apply filters
                    if cpm > 0 and cpm < config.MIN_CPM:
                        logger.debug(f"Skip (CPM ${cpm:.2f} < min): {name}")
                        continue
                    if budget > 0 and budget < config.MIN_BUDGET_REMAINING:
                        logger.debug(f"Skip (budget ${budget:.0f} < min): {name}")
                        continue
                    if config.FREE_ONLY and not is_free:
                        logger.debug(f"Skip (paid): {name}")
                        continue

                    # Derive a whop_id from the URL slug
                    slug = full_url.rstrip("/").split("/")[-1]

                    c = Campaign(
                        whop_id=slug,
                        name=name,
                        cpm=cpm,
                        budget_remaining=budget,
                        is_free=is_free,
                        allowed_platforms="tiktok,instagram,youtube",
                    )
                    campaigns.append(c)

                except Exception as e:
                    logger.debug(f"Card parse error: {e}")
                    continue

            logger.info(f"Found {len(campaigns)} qualifying campaigns")

        except Exception as e:
            logger.error(f"discover_campaigns failed: {e}")
            await self._save_debug_snapshot("discover_error")

        return campaigns

    async def enrich_campaign(self, campaign: Campaign) -> Campaign:
        """
        Visit the campaign's Whop page to pull:
          - Google Drive folder URL
          - YouTube channel / playlist URL
          - Confirmed CPM / budget if not parsed from card
        """
        try:
            url = f"{config.WHOP_BASE_URL}/hub/{campaign.whop_id}/"
            await asyncio.sleep(random.uniform(2, 4))  # human pace between pages
            await self.page.goto(
                url,
                timeout=config.BROWSER_TIMEOUT * 1000,
                wait_until="domcontentloaded",
            )
            await asyncio.sleep(random.uniform(2, 3))

            page_text = await self.page.content()

            # Google Drive
            drive_match = re.search(
                r'https://drive\.google\.com/[^\s\'"<>]+', page_text
            )
            if drive_match:
                campaign.drive_url = drive_match.group(0).rstrip("\\")
                logger.info(f"  Drive: {campaign.drive_url[:60]}")

            # YouTube channel / playlist
            yt_match = re.search(
                r'https://(?:www\.)?youtube\.com/(?:channel|@|playlist)[^\s\'"<>]+',
                page_text
            )
            if yt_match:
                campaign.youtube_url = yt_match.group(0).rstrip("\\")
                logger.info(f"  YouTube: {campaign.youtube_url[:60]}")

            # Refine CPM from page text if still 0
            if campaign.cpm == 0:
                campaign.cpm = self._parse_cpm_from_text(page_text)

        except Exception as e:
            logger.warning(f"enrich_campaign({campaign.name}): {e}")

        return campaign

    async def refresh_campaigns(self) -> List[Campaign]:
        """
        Full campaign refresh: discover → enrich → upsert to DB.
        Called by the daemon on WHOP_CHECK_INTERVAL.
        """
        raw = await self.discover_campaigns()
        enriched = []
        for c in raw:
            c = await self.enrich_campaign(c)
            self.queue.upsert_campaign(c)
            enriched.append(c)
            logger.info(f"Saved campaign: {c.name} (CPM ${c.cpm:.2f})")
        return enriched

    # ── URL Submission (atomic, called right after posting) ───────────────────

    async def submit_clip_to_whop(self, clip: Clip) -> bool:
        """
        Submit the posted clip's platform URLs to the Whop campaign
        so views are tracked and the payout window opens.
        Called atomically by platform_poster after every successful post.
        """
        if not await self.login():
            return False

        if not any([clip.tiktok_url, clip.instagram_url, clip.youtube_url]):
            logger.warning(f"No URLs to submit for clip {clip.id}")
            return False

        try:
            # Navigate to the campaign's submission page
            # Common Whop pattern: /hub/<slug>/submit  or  /hub/<slug>/upload
            submit_candidates = [
                f"{config.WHOP_BASE_URL}/hub/{clip.campaign_id}/submit",
                f"{config.WHOP_BASE_URL}/hub/{clip.campaign_id}/upload",
                f"{config.WHOP_BASE_URL}/hub/{clip.campaign_id}/",
            ]

            page_loaded = False
            for url in submit_candidates:
                try:
                    await self.page.goto(url, timeout=30_000)
                    await self.page.wait_for_load_state("networkidle")
                    await asyncio.sleep(2)
                    # Check for a submission form
                    form = await self.page.query_selector(
                        "form, input[type='url'], input[placeholder*='tiktok'], "
                        "input[placeholder*='link'], input[placeholder*='URL']"
                    )
                    if form:
                        page_loaded = True
                        break
                except Exception:
                    continue

            if not page_loaded:
                logger.warning(
                    f"Could not find submission form for campaign {clip.campaign_id} — "
                    "saving debug snapshot"
                )
                await self._save_debug_snapshot(f"submit_{clip.campaign_id}")
                return False

            # Fill in platform URLs
            url_inputs = await self.page.query_selector_all(
                "input[type='url'], input[placeholder*='link'], "
                "input[placeholder*='URL'], input[placeholder*='tiktok'], "
                "input[placeholder*='instagram'], input[placeholder*='youtube']"
            )

            urls_to_submit = [
                u for u in [clip.tiktok_url, clip.instagram_url, clip.youtube_url] if u
            ]

            for i, inp in enumerate(url_inputs[:len(urls_to_submit)]):
                await inp.fill(urls_to_submit[i])

            # Click submit
            submit_btn = await self.page.query_selector(
                "button[type='submit'], button:has-text('Submit'), "
                "button:has-text('Upload'), button:has-text('Send')"
            )
            if submit_btn:
                await submit_btn.click()
                await asyncio.sleep(3)

            # Mark as submitted in DB
            self.queue.update_clip_status(clip.id, ClipStatus.SUBMITTED)
            logger.info(f"Submitted clip {clip.id} to Whop campaign {clip.campaign_id}")
            return True

        except Exception as e:
            logger.error(f"submit_clip_to_whop failed for clip {clip.id}: {e}")
            return False

    async def submit_batch(self, clips: List[Clip]) -> int:
        """Submit multiple clips. Returns count of successful submissions."""
        submitted = 0
        for clip in clips:
            if await self.submit_clip_to_whop(clip):
                submitted += 1
            await asyncio.sleep(random.uniform(2, 5))
        logger.info(f"Submitted {submitted}/{len(clips)} clips to Whop")
        return submitted

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_cpm_from_text(self, text: str) -> float:
        """Extract a CPM value from free-form text like '$3.00 CPM' or '$3/1K'."""
        patterns = [
            r'\$(\d+(?:\.\d+)?)\s*(?:CPM|cpm)',
            r'\$(\d+(?:\.\d+)?)\s*/\s*1[Kk]',
            r'(\d+(?:\.\d+)?)\s*(?:CPM|cpm)',
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return float(m.group(1))
        return 0.0

    def _parse_budget_from_text(self, text: str) -> float:
        """Extract remaining budget from text like '$5,000 remaining'."""
        m = re.search(
            r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:remaining|left|budget)',
            text, re.IGNORECASE
        )
        if m:
            return float(m.group(1).replace(",", ""))
        return 0.0

    async def _save_debug_snapshot(self, label: str):
        """Save screenshot + HTML for debugging selector issues."""
        try:
            png  = config.DATA_DIR / f"whop_debug_{label}.png"
            html = config.DATA_DIR / f"whop_debug_{label}.html"
            await self.page.screenshot(path=str(png))
            html.write_text(await self.page.content(), encoding="utf-8")
            logger.info(f"Debug snapshot saved: {label} (see data/)")
        except Exception as e:
            logger.debug(f"Could not save snapshot: {e}")


# ── Standalone test ───────────────────────────────────────────────────────────

async def main():
    logging.basicConfig(level=logging.INFO)
    async with WhopScraper() as scraper:
        campaigns = await scraper.refresh_campaigns()
        print(f"\nFound {len(campaigns)} campaigns:")
        for c in campaigns:
            print(f"  {c.name} | CPM ${c.cpm:.2f} | Drive: {bool(c.drive_url)} | YT: {bool(c.youtube_url)}")


if __name__ == "__main__":
    asyncio.run(main())
