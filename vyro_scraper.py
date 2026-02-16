"""
Vyro Scraper
============
Browser automation to download clips from Vyro dashboard.
Uses Playwright for reliable, fast scraping.
"""

import asyncio
import random
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

import config
from queue_manager import QueueManager, Clip, ClipStatus

logger = logging.getLogger(__name__)


# Session storage file for persistent login
SESSION_FILE = config.DATA_DIR / "vyro_session.json"


class VyroScraper:
    def __init__(self):
        self.queue = QueueManager()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._logged_in = False
        self.playwright = None
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def start(self):
        """Initialize browser with saved session if available."""
        self.playwright = await async_playwright().start()
        
        self.browser = await self.playwright.chromium.launch(
            headless=config.HEADLESS,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Load saved session if it exists
        storage_state = None
        if SESSION_FILE.exists():
            storage_state = str(SESSION_FILE)
            logger.info("Loading saved Vyro session...")
        
        self.context = await self.browser.new_context(
            user_agent=random.choice(config.USER_AGENTS),
            viewport={'width': 1920, 'height': 1080},
            storage_state=storage_state,
        )
        
        self.page = await self.context.new_page()
        
        # Set download path
        config.CLIPS_INBOX.mkdir(parents=True, exist_ok=True)
        
        logger.info("Browser started")
    
    async def close(self):
        """Close browser and save session."""
        if self.context and self._logged_in:
            # Save session for next time
            try:
                await self.context.storage_state(path=str(SESSION_FILE))
                logger.info("Session saved for next time")
            except Exception as e:
                logger.warning(f"Could not save session: {e}")
        
        # Properly close everything to avoid I/O errors on Windows
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser closed")
        except Exception as e:
            logger.debug(f"Cleanup warning: {e}")
    
    async def login(self) -> bool:
        """Login to Vyro using saved session or manual login."""
        if self._logged_in:
            return True
        
        try:
            logger.info("Checking Vyro login status...")
            
            # Go to dashboard to check if already logged in
            await self.page.goto(config.VYRO_DASHBOARD_URL, timeout=config.BROWSER_TIMEOUT * 1000)
            await asyncio.sleep(3)
            
            # Check if we're on dashboard (logged in) or redirected to login
            current_url = self.page.url
            
            if 'dashboard' in current_url or 'campaigns' in current_url or 'app' in current_url:
                # Already logged in from saved session!
                self._logged_in = True
                logger.info("Already logged in (session restored)")
                return True
            
            # Not logged in - need manual login
            logger.info("")
            logger.info("=" * 60)
            logger.info("MANUAL LOGIN REQUIRED")
            logger.info("=" * 60)
            logger.info("")
            logger.info("A browser window should be open.")
            logger.info("Please log into Vyro manually:")
            logger.info("  1. Enter your email")
            logger.info("  2. Check your email for the code")
            logger.info("  3. Enter the code")
            logger.info("  4. Wait until you see the dashboard")
            logger.info("")
            logger.info("Your session will be saved for future runs.")
            logger.info("=" * 60)
            
            # Go to login page
            await self.page.goto(config.VYRO_LOGIN_URL, timeout=config.BROWSER_TIMEOUT * 1000)
            
            # Wait for user to complete manual login (up to 5 minutes)
            logger.info("Waiting for manual login (up to 5 minutes)...")
            
            for _ in range(60):  # Check every 5 seconds for 5 minutes
                await asyncio.sleep(5)
                current_url = self.page.url
                
                if 'dashboard' in current_url or 'campaigns' in current_url or 'app' in current_url:
                    self._logged_in = True
                    logger.info("")
                    logger.info("Login successful! Session will be saved.")
                    return True
                
                if 'login' not in current_url and 'vyro.com' in current_url:
                    # Might be logged in, check for dashboard elements
                    try:
                        await self.page.wait_for_selector('[href*="campaign"], [href*="dashboard"]', timeout=2000)
                        self._logged_in = True
                        logger.info("Login successful! Session will be saved.")
                        return True
                    except:
                        pass
            
            logger.error("Login timeout - please try again")
            return False
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    async def get_campaigns(self) -> List[Dict]:
        """Get list of available campaigns."""
        if not await self.login():
            return []
        
        campaigns = []
        
        try:
            # Try multiple possible campaign URLs
            campaign_urls = [
                config.VYRO_CAMPAIGNS_URL,
                f"{config.VYRO_BASE_URL}/campaigns",
                f"{config.VYRO_BASE_URL}/discover",
                f"{config.VYRO_BASE_URL}/explore",
                config.VYRO_DASHBOARD_URL,
            ]
            
            for url in campaign_urls:
                await self.page.goto(url, timeout=config.BROWSER_TIMEOUT * 1000)
                await self.page.wait_for_load_state('networkidle')
                await asyncio.sleep(2)
                
                # Debug: Log current URL and page title
                current_url = self.page.url
                title = await self.page.title()
                logger.info(f"Checking URL: {current_url} (Title: {title})")
                
                # Try multiple selector patterns for campaigns
                selector_patterns = [
                    '[data-campaign]',
                    '.campaign-card',
                    'a[href*="campaign"]',
                    'a[href*="/c/"]',
                    '[class*="campaign"]',
                    '[class*="creator"]',
                    'div[class*="card"]',
                    'article',
                    '.listing',
                    '[data-testid]',
                ]
                
                for selector in selector_patterns:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        if elements:
                            logger.info(f"Found {len(elements)} elements with selector: {selector}")
                    except:
                        pass
                
                # Try to find any clickable campaign links
                all_links = await self.page.query_selector_all('a[href]')
                for link in all_links[:20]:  # Check first 20 links
                    try:
                        href = await link.get_attribute('href') or ""
                        text = await link.inner_text() or ""
                        text = text.strip()[:50]  # First 50 chars
                        
                        # Look for campaign-like links
                        if any(kw in href.lower() for kw in ['campaign', 'creator', 'mrbeast', 'rober', '/c/']):
                            logger.info(f"Potential campaign link: {href} ({text})")
                            
                            campaigns.append({
                                'name': text.strip().lower().replace(' ', '-') or 'unknown',
                                'url': href if href.startswith('http') else f"{config.VYRO_BASE_URL}{href}",
                                'cpm': 3.0,
                            })
                    except:
                        continue
                
                if campaigns:
                    break  # Found campaigns, stop searching
            
            if not campaigns:
                # No campaigns found - let's save a screenshot for debugging
                screenshot_path = config.DATA_DIR / "vyro_debug.png"
                await self.page.screenshot(path=str(screenshot_path))
                logger.warning(f"No campaigns found. Screenshot saved to {screenshot_path}")
                logger.warning(f"Current URL: {self.page.url}")
                
                # Also save the page HTML for debugging
                html_path = config.DATA_DIR / "vyro_debug.html"
                html_content = await self.page.content()
                html_path.write_text(html_content, encoding='utf-8')
                logger.warning(f"Page HTML saved to {html_path}")
            
            # Filter by minimum CPM and target campaigns
            campaigns = [
                c for c in campaigns 
                if c['cpm'] >= config.MIN_CPM or c['name'] in config.TARGET_CAMPAIGNS
            ]
            
            logger.info(f"Found {len(campaigns)} eligible campaigns")
            return campaigns
            
        except Exception as e:
            logger.error(f"Failed to get campaigns: {e}")
            return []
    
    async def get_campaign_clips(self, campaign_url: str, campaign_name: str, limit: int = 10) -> List[Dict]:
        """Get available clips from a campaign."""
        clips = []
        
        try:
            await self.page.goto(campaign_url, timeout=config.BROWSER_TIMEOUT * 1000)
            await self.page.wait_for_load_state('networkidle')
            
            # Find clip elements (adjust selectors based on actual Vyro UI)
            clip_elements = await self.page.query_selector_all(
                '[data-clip], .clip-card, .clip-item, [data-clip-id]'
            )
            
            for element in clip_elements[:limit]:
                try:
                    clip_id = await element.get_attribute('data-clip-id') or await element.get_attribute('id')
                    
                    # Skip if already downloaded
                    if clip_id and self.queue.clip_exists(clip_id):
                        continue
                    
                    # Get download button/link
                    download_btn = await element.query_selector('[data-download], .download-btn, a[download]')
                    if not download_btn:
                        continue
                    
                    download_url = await download_btn.get_attribute('href') or await download_btn.get_attribute('data-url')
                    
                    # Get caption if provided
                    caption_el = await element.query_selector('.clip-caption, [data-caption]')
                    caption = await caption_el.inner_text() if caption_el else ""
                    
                    clips.append({
                        'id': clip_id or f"{campaign_name}_{len(clips)}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        'campaign': campaign_name,
                        'download_url': download_url,
                        'caption': caption,
                    })
                    
                except Exception as e:
                    logger.debug(f"Error parsing clip element: {e}")
                    continue
            
            logger.info(f"Found {len(clips)} new clips in {campaign_name}")
            return clips
            
        except Exception as e:
            logger.error(f"Failed to get clips from {campaign_name}: {e}")
            return []
    
    async def download_clip(self, clip_info: Dict) -> Optional[Clip]:
        """Download a single clip."""
        try:
            clip_id = clip_info['id']
            campaign = clip_info['campaign']
            download_url = clip_info['download_url']
            
            filename = f"{campaign}_{clip_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            filepath = config.CLIPS_INBOX / filename
            
            # Start download
            async with self.page.expect_download() as download_info:
                # Try clicking download or navigating to URL
                if download_url.startswith('http'):
                    await self.page.goto(download_url)
                else:
                    # Find and click download button
                    await self.page.click(f'[data-clip-id="{clip_id}"] [data-download], [data-clip-id="{clip_id}"] .download-btn')
            
            download = await download_info.value
            await download.save_as(str(filepath))
            
            # Generate caption and hashtags
            caption = self._generate_caption(clip_info.get('caption', ''), campaign)
            hashtags = self._generate_hashtags(campaign)
            
            # Create clip record
            clip = Clip(
                vyro_clip_id=clip_id,
                campaign_name=campaign,
                filename=filename,
                filepath=str(filepath),
                caption=caption,
                hashtags=hashtags,
                status=ClipStatus.PENDING.value,
            )
            
            self.queue.add_clip(clip)
            logger.info(f"Downloaded: {filename}")
            
            return clip
            
        except Exception as e:
            logger.error(f"Failed to download clip {clip_info.get('id')}: {e}")
            return None
    
    async def download_clips_batch(self, clips: List[Dict]) -> List[Clip]:
        """Download multiple clips."""
        downloaded = []
        
        for clip_info in clips:
            clip = await self.download_clip(clip_info)
            if clip:
                downloaded.append(clip)
            
            # Small delay between downloads
            await asyncio.sleep(random.uniform(1, 3))
        
        return downloaded
    
    async def fetch_new_clips(self, target_count: int = 15) -> List[Clip]:
        """Main method: fetch new clips from all campaigns."""
        if not await self.login():
            logger.error("Cannot fetch clips - login failed")
            return []
        
        all_clips = []
        campaigns = await self.get_campaigns()
        
        if not campaigns:
            logger.warning("No campaigns found")
            return []
        
        clips_per_campaign = max(1, target_count // len(campaigns))
        
        for campaign in campaigns:
            if len(all_clips) >= target_count:
                break
            
            clip_infos = await self.get_campaign_clips(
                campaign['url'], 
                campaign['name'],
                limit=clips_per_campaign
            )
            
            downloaded = await self.download_clips_batch(clip_infos)
            all_clips.extend(downloaded)
            
            logger.info(f"Downloaded {len(downloaded)} clips from {campaign['name']}")
        
        logger.info(f"Total clips fetched: {len(all_clips)}")
        return all_clips
    
    async def submit_urls_to_vyro(self, clips: List[Clip]) -> int:
        """Submit posted URLs back to Vyro for tracking."""
        if not await self.login():
            return 0
        
        submitted = 0
        
        for clip in clips:
            try:
                # Navigate to submission page (adjust based on actual Vyro UI)
                await self.page.goto(f"{config.VYRO_BASE_URL}/submit", timeout=config.BROWSER_TIMEOUT * 1000)
                
                # Fill in URLs
                if clip.tiktok_url:
                    await self.page.fill('input[name="tiktok_url"], #tiktok-url', clip.tiktok_url)
                if clip.instagram_url:
                    await self.page.fill('input[name="instagram_url"], #instagram-url', clip.instagram_url)
                if clip.youtube_url:
                    await self.page.fill('input[name="youtube_url"], #youtube-url', clip.youtube_url)
                
                # Submit
                await self.page.click('button[type="submit"]')
                await self.page.wait_for_load_state('networkidle')
                
                # Update status
                self.queue.update_clip_status(clip.id, ClipStatus.SUBMITTED)
                submitted += 1
                
                await asyncio.sleep(random.uniform(2, 5))
                
            except Exception as e:
                logger.error(f"Failed to submit clip {clip.id}: {e}")
        
        logger.info(f"Submitted {submitted} clips to Vyro")
        return submitted
    
    def _generate_caption(self, base_caption: str, campaign: str) -> str:
        """Generate engaging caption."""
        hook = random.choice(config.CAPTION_HOOKS)
        cta = random.choice(config.CTAS)
        
        if base_caption:
            return f"{hook}\n\n{base_caption}\n\n{cta}"
        return f"{hook}\n\n{cta}"
    
    def _generate_hashtags(self, campaign: str) -> str:
        """Generate hashtags for a clip."""
        tags = config.BASE_HASHTAGS.copy()
        
        # Add campaign-specific tags
        if campaign in config.NICHE_HASHTAGS:
            tags.extend(random.sample(config.NICHE_HASHTAGS[campaign], min(2, len(config.NICHE_HASHTAGS[campaign]))))
        else:
            tags.extend(random.sample(config.NICHE_HASHTAGS['general'], 2))
        
        return ' '.join(tags)


async def main():
    """Test the scraper."""
    logging.basicConfig(level=logging.INFO)
    
    async with VyroScraper() as scraper:
        clips = await scraper.fetch_new_clips(target_count=5)
        print(f"\nDownloaded {len(clips)} clips")
        
        for clip in clips:
            print(f"  - {clip.filename} ({clip.campaign_name})")


if __name__ == "__main__":
    asyncio.run(main())
