"""
Platform Poster
===============
Parallel posting to TikTok, Instagram Reels, and YouTube Shorts.
Uses browser automation for reliable uploads.
"""

import asyncio
import random
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

import config
from queue_manager import QueueManager, Clip, ClipStatus
from quality_monitor import QualityMonitor
from campaign_requirements import CampaignRequirementsValidator

logger = logging.getLogger(__name__)


@dataclass
class PostResult:
    platform: str
    success: bool
    url: str = ""
    error: str = ""



class LoginFailureError(Exception):
    """Raised when platform login fails."""
    pass

class CaptchaRequiredError(Exception):
    """Raised when CAPTCHA is required for login."""
    pass

class PlatformPoster:
    """Handles posting clips to all platforms."""
    
    def __init__(self):
        self.queue = QueueManager()
        self.browsers: Dict[str, Browser] = {}
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        self._logged_in: Dict[str, bool] = {}
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def start(self):
        """Initialize browsers for each platform."""
        self.playwright = await async_playwright().start()
        
        for platform in config.PLATFORMS:
            browser = await self.playwright.chromium.launch(
                headless=config.HEADLESS,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = await browser.new_context(
                user_agent=random.choice(config.USER_AGENTS),
                viewport={'width': 1920, 'height': 1080},
            )
            
            page = await context.new_page()
            
            self.browsers[platform] = browser
            self.contexts[platform] = context
            self.pages[platform] = page
            self._logged_in[platform] = False
        
        logger.info(f"Started browsers for {len(config.PLATFORMS)} platforms")
    
    async def close(self):
        """Close all browsers."""
        for platform, browser in self.browsers.items():
            try:
                await browser.close()
            except Exception:
                pass
        logger.info("All browsers closed")
    
    # =========================================================================
    # TIKTOK
    # =========================================================================
    async def login_tiktok(self) -> bool:
        """Login to TikTok."""
        if self._logged_in.get('tiktok'):
            return True
        
        page = self.pages['tiktok']
        
        try:
            logger.info("Logging into TikTok...")
            await page.goto('https://www.tiktok.com/login/phone-or-email/email', timeout=config.BROWSER_TIMEOUT * 1000)
            
            # Wait for login form
            await page.wait_for_selector('input[name="username"], input[placeholder*="email"]', timeout=15000)
            
            # Fill credentials
            await page.fill('input[name="username"], input[placeholder*="email"]', config.TIKTOK_USERNAME)
            await page.fill('input[type="password"]', config.TIKTOK_PASSWORD)
            
            # Click login
            await page.click('button[type="submit"]')

            # Wait for redirect (may need CAPTCHA handling)
            # If CAPTCHA appears, you will see it in the browser window
            logger.info("    Waiting for TikTok login (60s for CAPTCHA if needed)...")
            await asyncio.sleep(60)
            
            # Check if logged in
            if 'login' not in page.url:
                self._logged_in['tiktok'] = True
                logger.info("Successfully logged into TikTok")
                return True
            
            logger.warning("TikTok login may require manual verification")
            return False
            
        except Exception as e:
            logger.error(f"TikTok login failed: {e}")
            return False
    
    async def post_tiktok(self, clip: Clip) -> PostResult:
        """Post a clip to TikTok."""
        page = self.pages['tiktok']
        
        try:
            if not await self.login_tiktok():
                return PostResult('tiktok', False, error="Login failed")
            
            # Go to upload page
            await page.goto('https://www.tiktok.com/upload', timeout=config.BROWSER_TIMEOUT * 1000)
            await page.wait_for_load_state('networkidle')
            
            # Find file input and upload
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(clip.filepath)
            
            # Wait for upload to process
            await asyncio.sleep(10)
            
            # Fill caption
            caption_input = await page.query_selector('[data-text="true"], .DraftEditor-root, [contenteditable="true"]')
            if caption_input:
                full_caption = f"{clip.caption}\n{clip.hashtags}"
                await caption_input.fill(full_caption)
            
            # Click post button
            post_btn = await page.query_selector('button:has-text("Post"), button[data-e2e="post-button"]')
            if post_btn:
                await post_btn.click()
            
            # Wait for upload to complete
            await asyncio.sleep(15)
            
            # Try to get the post URL
            # TikTok usually redirects or shows success
            post_url = f"https://www.tiktok.com/@{config.TIKTOK_USERNAME}"
            
            logger.info(f"Posted to TikTok: {clip.filename}")
            return PostResult('tiktok', True, url=post_url)
            
        except Exception as e:
            logger.error(f"TikTok post failed: {e}")
            return PostResult('tiktok', False, error=str(e))
    
    # =========================================================================
    # INSTAGRAM
    # =========================================================================
    async def login_instagram(self) -> bool:
        """Login to Instagram."""
        if self._logged_in.get('instagram'):
            return True

        page = self.pages['instagram']

        try:
            logger.info("Logging into Instagram...")
            await page.goto('https://www.instagram.com/', timeout=config.BROWSER_TIMEOUT * 1000)
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)

            # Handle cookie consent
            try:
                await page.click('button:has-text("Allow")', timeout=3000)
            except:
                pass

            # Look for login link and click if needed
            try:
                login_link = await page.query_selector('a[href*="/accounts/login/"]')
                if login_link:
                    await login_link.click()
                    await asyncio.sleep(2)
            except:
                pass

            # Wait for any input field to appear (be flexible)
            for attempt in range(3):
                username_field = await page.query_selector('input[name="username"]')
                if username_field:
                    break
                await asyncio.sleep(2)

            # Fill credentials with flexible selectors
            if username_field:
                await username_field.fill(config.INSTAGRAM_USERNAME)

                password_field = await page.query_selector('input[name="password"]')
                if password_field:
                    await password_field.fill(config.INSTAGRAM_PASSWORD)

                    # Click login - try multiple button selectors
                    login_btn = await page.query_selector('button[type="submit"], button:has-text("Log in"), button:has-text("log in")')
                    if login_btn:
                        await login_btn.click()
                        # Wait for redirect (may need CAPTCHA handling)
                        # If CAPTCHA appears, you will see it in the browser window
                        logger.info("    Waiting for Instagram login (60s for CAPTCHA if needed)...")
                        await asyncio.sleep(60)

                        # Check if logged in
                        if '/accounts/login/' not in page.url and 'instagram.com' in page.url:
                            self._logged_in['instagram'] = True
                            logger.info("Successfully logged into Instagram")
                            return True

            return False

        except Exception as e:
            logger.error(f"Instagram login failed: {e}")
            return False
    
    async def post_instagram(self, clip: Clip) -> PostResult:
        """Post a Reel to Instagram."""
        page = self.pages['instagram']
        
        try:
            if not await self.login_instagram():
                return PostResult('instagram', False, error="Login failed")
            
            # Go to create page
            await page.goto('https://www.instagram.com/', timeout=config.BROWSER_TIMEOUT * 1000)
            await page.wait_for_load_state('networkidle')
            
            # Click create button (+ icon)
            create_btn = await page.query_selector('[aria-label="New post"], svg[aria-label="New post"]')
            if create_btn:
                await create_btn.click()
            else:
                # Try alternative selector
                await page.click('svg[aria-label="New post"]')
            
            await asyncio.sleep(2)
            
            # Select "Reel" option if available
            reel_option = await page.query_selector('button:has-text("Reel"), [role="menuitem"]:has-text("Reel")')
            if reel_option:
                await reel_option.click()
            
            # Find file input and upload
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(clip.filepath)
            
            # Wait for processing
            await asyncio.sleep(10)
            
            # Click Next buttons
            for _ in range(2):
                next_btn = await page.query_selector('button:has-text("Next")')
                if next_btn:
                    await next_btn.click()
                    await asyncio.sleep(2)
            
            # Fill caption
            caption_input = await page.query_selector('textarea[aria-label*="caption"], textarea[placeholder*="caption"]')
            if caption_input:
                full_caption = f"{clip.caption}\n{clip.hashtags}"
                await caption_input.fill(full_caption)
            
            # Click Share
            share_btn = await page.query_selector('button:has-text("Share")')
            if share_btn:
                await share_btn.click()
            
            # Wait for upload
            await asyncio.sleep(15)
            
            post_url = f"https://www.instagram.com/{config.INSTAGRAM_USERNAME}/reels/"
            
            logger.info(f"Posted to Instagram: {clip.filename}")
            return PostResult('instagram', True, url=post_url)
            
        except Exception as e:
            logger.error(f"Instagram post failed: {e}")
            return PostResult('instagram', False, error=str(e))
    
    # =========================================================================
    # YOUTUBE (Using YouTube Data API v3 with OAuth)
    # =========================================================================
    def _get_youtube_uploader(self):
        """Get or initialize YouTube uploader (lazy init)."""
        if not hasattr(self, '_youtube_uploader'):
            try:
                # Import here to avoid hard dependency if not used
                import sys
                from pathlib import Path
                youtube_uploader_path = Path(__file__).parent / 'youtube_uploader'
                if youtube_uploader_path not in sys.path:
                    sys.path.insert(0, str(youtube_uploader_path))

                from suno_integration import SUNOYouTubeIntegration
                self._youtube_uploader = SUNOYouTubeIntegration(
                    suno_clips_dir=str(config.CLIPS_INBOX),
                    credentials_file=str(Path(__file__).parent / 'youtube_uploader' / 'credentials.json'),
                    token_file=str(Path(__file__).parent / 'youtube_uploader' / 'token.pickle')
                )
            except Exception as e:
                logger.error(f"Failed to initialize YouTube uploader: {e}")
                self._youtube_uploader = None
        return self._youtube_uploader

    async def post_youtube(self, clip: Clip) -> PostResult:
        """
        Post a video to YouTube using YouTube Data API v3.
        Returns real video_id and proper watch URL.
        """
        try:
            uploader = self._get_youtube_uploader()
            if not uploader:
                return PostResult('youtube', False, error="YouTube uploader not initialized")

            logger.info(f"Uploading to YouTube: {clip.filename}")
            logger.info(f"  Title: {clip.caption[:100]}")
            logger.info(f"  File size: {Path(clip.filepath).stat().st_size / 1024 / 1024:.1f}MB")

            # Authenticate once (will reuse token if already cached)
            logger.info("Authenticating with YouTube...")
            uploader.authenticate_once()

            # Prepare metadata
            title = clip.caption[:100]  # YouTube title limit
            description = f"{clip.caption}\n\n{clip.hashtags}"
            tags = clip.hashtags.split() if clip.hashtags else ['suno', 'clips']

            # Upload using YouTube API
            logger.info("Starting upload...")
            video_id = uploader.upload_clip(
                clip_path=clip.filepath,
                title=title,
                description=description,
                tags=tags,
                privacy_status='unlisted'  # Start unlisted, user can change
            )

            if video_id:
                post_url = f"https://www.youtube.com/watch?v={video_id}"
                logger.info(f"UPLOAD SUCCESS: {video_id}")
                logger.info(f"URL: {post_url}")
                return PostResult('youtube', True, url=post_url)
            else:
                logger.error("YouTube upload returned no video_id")
                return PostResult('youtube', False, error="Upload succeeded but no video_id returned")

        except Exception as e:
            logger.error(f"YouTube post failed: {str(e)}")
            return PostResult('youtube', False, error=str(e))
    
    # =========================================================================
    # FACEBOOK
    # =========================================================================
    async def login_facebook(self) -> bool:
        """Login to Facebook."""
        if self._logged_in.get('facebook'):
            return True
        
        page = self.pages['facebook']
        
        try:
            logger.info("Logging into Facebook...")
            await page.goto('https://www.facebook.com/login', timeout=config.BROWSER_TIMEOUT * 1000)
            
            # Wait for login form
            await page.wait_for_selector('#email', timeout=15000)
            
            # Fill credentials
            await page.fill('#email', config.FACEBOOK_EMAIL)
            await page.fill('#pass', config.FACEBOOK_PASSWORD)
            
            # Click login
            await page.click('button[name="login"]')
            
            # Wait for redirect
            await asyncio.sleep(5)
            
            # Check if logged in
            if 'login' not in page.url:
                self._logged_in['facebook'] = True
                logger.info("Successfully logged into Facebook")
                return True
            
            logger.warning("Facebook login may require manual verification")
            return False
            
        except Exception as e:
            logger.error(f"Facebook login failed: {e}")
            return False
    
    async def post_facebook(self, clip: Clip) -> PostResult:
        """Post a Reel to Facebook."""
        page = self.pages['facebook']
        
        try:
            if not await self.login_facebook():
                return PostResult('facebook', False, error="Login failed")
            
            # Go to Reels creation page
            await page.goto('https://www.facebook.com/reels/create', timeout=config.BROWSER_TIMEOUT * 1000)
            await page.wait_for_load_state('networkidle')
            
            await asyncio.sleep(3)
            
            # Find file input and upload
            file_input = await page.query_selector('input[type="file"][accept*="video"]')
            if file_input:
                await file_input.set_input_files(clip.filepath)
            else:
                # Try alternative: click add video button first
                add_btn = await page.query_selector('[aria-label*="Add video"], [aria-label*="Upload"]')
                if add_btn:
                    await add_btn.click()
                    await asyncio.sleep(2)
                    file_input = await page.query_selector('input[type="file"]')
                    if file_input:
                        await file_input.set_input_files(clip.filepath)
            
            # Wait for upload to process
            await asyncio.sleep(15)
            
            # Click Next if present
            next_btn = await page.query_selector('div[aria-label="Next"], button:has-text("Next")')
            if next_btn:
                await next_btn.click()
                await asyncio.sleep(3)
            
            # Fill description/caption
            caption_input = await page.query_selector('[aria-label*="description"], [aria-label*="caption"], [contenteditable="true"]')
            if caption_input:
                full_caption = f"{clip.caption}\n{clip.hashtags}"
                await caption_input.fill(full_caption)
            
            await asyncio.sleep(2)
            
            # Click Share/Publish
            share_btn = await page.query_selector('div[aria-label="Share"], div[aria-label="Publish"], button:has-text("Share")')
            if share_btn:
                await share_btn.click()
            
            # Wait for upload to complete
            await asyncio.sleep(20)
            
            post_url = "https://www.facebook.com/reels/"
            
            logger.info(f"Posted to Facebook: {clip.filename}")
            return PostResult('facebook', True, url=post_url)
            
        except Exception as e:
            logger.error(f"Facebook post failed: {e}")
            return PostResult('facebook', False, error=str(e))
    
    # =========================================================================
    # PARALLEL POSTING
    # =========================================================================
    async def post_to_all_platforms(self, clip: Clip) -> Dict[str, PostResult]:
        """Post a clip to all platforms in parallel."""
        logger.info(f"Posting clip to all platforms: {clip.filename}")
        
        # Update status to posting
        self.queue.update_clip_status(clip.id, ClipStatus.POSTING)
        
        # Run all posts in parallel based on enabled platforms
        post_tasks = []
        platform_list = []

        if 'tiktok' in config.PLATFORMS:
            post_tasks.append(self.post_tiktok(clip))
            platform_list.append('tiktok')
        if 'instagram' in config.PLATFORMS:
            post_tasks.append(self.post_instagram(clip))
            platform_list.append('instagram')
        if 'youtube' in config.PLATFORMS:
            post_tasks.append(self.post_youtube(clip))
            platform_list.append('youtube')
        if 'facebook' in config.PLATFORMS:
            post_tasks.append(self.post_facebook(clip))
            platform_list.append('facebook')

        results = await asyncio.gather(*post_tasks, return_exceptions=True)

        # Process results
        post_results = {}
        success_count = 0

        for i, result in enumerate(results):
            platform = platform_list[i]

            if isinstance(result, Exception):
                post_results[platform] = PostResult(platform, False, error=str(result))
            else:
                post_results[platform] = result
                if result.success:
                    success_count += 1
        
        # Update clip status based on results
        if success_count == len(config.PLATFORMS):
            status = ClipStatus.POSTED
        elif success_count > 0:
            status = ClipStatus.PARTIAL
        else:
            status = ClipStatus.FAILED

        # Build URL dict dynamically
        url_kwargs = {}
        for platform, result in post_results.items():
            if result.success:
                url_kwargs[f'{platform}_url'] = result.url

        self.queue.update_clip_status(clip.id, status, **url_kwargs)

        # Status update to DB is sufficient for tracker (get_daily_stats reads from clip status)
        if status in (ClipStatus.POSTED, ClipStatus.PARTIAL):
            logger.info(f"Clip {clip.filename} recorded: {success_count}/{len(config.PLATFORMS)} platforms")

        # Move file to appropriate folder
        src_path = Path(clip.filepath)
        if status in (ClipStatus.POSTED, ClipStatus.PARTIAL):
            dest_path = config.CLIPS_POSTED / src_path.name
        else:
            dest_path = config.CLIPS_FAILED / src_path.name
        
        try:
            shutil.move(str(src_path), str(dest_path))
        except Exception:
            pass
        
        logger.info(f"Posting complete: {success_count}/{len(config.PLATFORMS)} platforms successful")
        return post_results
    
    async def post_batch(self, clips: List[Clip]) -> List[Dict[str, PostResult]]:
        """Post multiple clips with quality & campaign requirement checking."""
        all_results = []
        quality_monitor = QualityMonitor()
        campaign_validator = CampaignRequirementsValidator()

        for i, clip in enumerate(clips):
            logger.info(f"Processing clip {i+1}/{len(clips)}: {clip.filename}")

            # ─── QUALITY GATE: Check before posting ────────────────────────────────
            quality_score = quality_monitor.assess_clip(clip.filepath, clip.caption)
            logger.info(f"  Quality score: {quality_score.overall_score}/100 | Approved: {quality_score.approved}")

            if quality_score.issues:
                logger.warning(f"  [BLOCKED] Quality issues: {', '.join(quality_score.issues)}")
                # Mark as failed and move to failed folder
                self.queue.update_clip_status(clip.id, ClipStatus.FAILED)
                src_path = Path(clip.filepath)
                try:
                    dest_path = config.CLIPS_FAILED / src_path.name
                    shutil.move(str(src_path), str(dest_path))
                    logger.info(f"  Moved to failed folder (quality issues)")
                except Exception as e:
                    logger.error(f"  Failed to move clip: {e}")

                # Skip posting this clip
                all_results.append({platform: PostResult(platform, False, error="Quality check failed")
                                   for platform in config.PLATFORMS})
                continue

            if not quality_score.approved:
                logger.warning(f"  [WARNING] Quality warnings: {', '.join(quality_score.warnings)}")
                logger.info(f"  Proceeding with caution (score {quality_score.overall_score} >= threshold 70)")

            # ─── CAMPAIGN GATE: Verify against campaign requirements ─────────────────
            if clip.campaign_id:
                approved, reasons = campaign_validator.validate_clip_for_campaign(
                    clip.campaign_id,
                    clip.creator_name or "unknown",
                    clip.source_platform or "unknown",
                    clip.clip_duration or 30
                )
                if not approved:
                    logger.warning(f"  [BLOCKED] Campaign requirement failed: {reasons[0]}")
                    self.queue.update_clip_status(clip.id, ClipStatus.FAILED)
                    all_results.append({platform: PostResult(platform, False, error="Campaign requirement failed")
                                       for platform in config.PLATFORMS})
                    continue
                logger.info(f"  Campaign requirements: PASSED")

            # ─── POSTING: Only if quality & campaign passed ─────────────────────────
            results = await self.post_to_all_platforms(clip)
            all_results.append(results)

            # Delay between clips to avoid rate limits
            if i < len(clips) - 1:
                delay = random.uniform(config.POST_DELAY_MIN, config.POST_DELAY_MAX)
                logger.info(f"  Waiting {delay:.0f}s before next clip...")
                await asyncio.sleep(delay)

        return all_results


async def main():
    """Test the poster."""
    logging.basicConfig(level=logging.INFO)
    
    queue = QueueManager()
    pending = queue.get_pending_clips(limit=1)
    
    if not pending:
        logger.info("No pending clips to post")
        return
    
    async with PlatformPoster() as poster:
        results = await poster.post_to_all_platforms(pending[0])
        
        logger.info("\nResults:")
        for platform, result in results.items():
            status = "✅" if result.success else "❌"
            logger.info(f"  {status} {platform}: {result.url or result.error}")


if __name__ == "__main__":
    asyncio.run(main())
