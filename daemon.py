"""
Daemon Runner
=============
24/7 continuous operation for the Vyro clipping system.
Handles scheduling, health checks, and automatic recovery.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional
import json
from pathlib import Path

import config
from queue_manager import QueueManager, ClipStatus
from vyro_scraper import VyroScraper
from platform_poster import PlatformPoster
from earnings_tracker import EarningsTracker

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    datefmt=config.LOG_DATE_FORMAT,
    handlers=[
        logging.FileHandler(config.LOGS_DIR / f"daemon_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class VyroDaemon:
    """24/7 Vyro clipping daemon."""
    
    def __init__(self):
        self.queue = QueueManager()
        self.tracker = EarningsTracker()
        self.running = False
        self.last_fetch = None
        self.last_post = None
        self.last_health_check = None
        
        # Stats for current session
        self.session_stats = {
            'started': datetime.now().isoformat(),
            'clips_fetched': 0,
            'clips_posted': 0,
            'errors': 0,
        }
    
    async def start(self):
        """Start the daemon."""
        self.running = True
        logger.info("="*60)
        logger.info("VYRO DAEMON STARTING")
        logger.info("="*60)
        logger.info(f"Target: {config.DAILY_CLIP_TARGET} clips/day")
        logger.info(f"Sessions: {config.SESSIONS_PER_DAY}/day at {config.POSTING_TIMES}")
        logger.info(f"Vyro check interval: {config.VYRO_CHECK_INTERVAL} minutes")
        logger.info("="*60)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Run main loop
        await self._main_loop()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    async def _main_loop(self):
        """Main daemon loop."""
        while self.running:
            try:
                now = datetime.now()
                
                # Health check
                if self._should_health_check():
                    await self._health_check()
                
                # Check if it's time to fetch new clips
                if self._should_fetch_clips():
                    await self._fetch_clips()
                
                # Check if it's a posting time
                if self._should_post():
                    await self._post_session()
                
                # Submit any pending URLs to Vyro
                await self._submit_to_vyro()
                
                # Sleep before next iteration
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.session_stats['errors'] += 1
                await asyncio.sleep(60)
        
        logger.info("Daemon stopped")
        self._save_session_stats()
    
    def _should_health_check(self) -> bool:
        """Check if it's time for a health check."""
        if self.last_health_check is None:
            return True
        
        elapsed = (datetime.now() - self.last_health_check).total_seconds() / 60
        return elapsed >= config.HEALTH_CHECK_INTERVAL
    
    def _should_fetch_clips(self) -> bool:
        """Check if it's time to fetch new clips from Vyro."""
        if self.last_fetch is None:
            return True
        
        elapsed = (datetime.now() - self.last_fetch).total_seconds() / 60
        return elapsed >= config.VYRO_CHECK_INTERVAL
    
    def _should_post(self) -> bool:
        """Check if it's a scheduled posting time."""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        # Check if we're within 5 minutes of a posting time
        for post_time in config.POSTING_TIMES:
            post_hour, post_min = map(int, post_time.split(':'))
            post_dt = now.replace(hour=post_hour, minute=post_min, second=0)
            
            diff = abs((now - post_dt).total_seconds())
            
            if diff <= 300:  # Within 5 minutes
                # Check we haven't already posted in this window
                if self.last_post is None:
                    return True
                
                last_post_diff = (now - self.last_post).total_seconds()
                if last_post_diff > 600:  # More than 10 min since last post
                    return True
        
        return False
    
    async def _health_check(self):
        """Perform health check."""
        logger.info("Running health check...")
        self.last_health_check = datetime.now()
        
        # Check queue status
        pending = self.queue.get_pending_clips(limit=100)
        posted_today = self.queue.get_daily_stats()
        
        logger.info(f"Health: {len(pending)} pending clips, {posted_today.get('clips_posted', 0)} posted today")
        
        # Display mini dashboard
        self.tracker.display_dashboard()
    
    async def _fetch_clips(self):
        """Fetch new clips from Vyro."""
        logger.info("Fetching new clips from Vyro...")
        self.last_fetch = datetime.now()
        
        # Check how many clips we need
        today_stats = self.queue.get_daily_stats()
        posted_today = today_stats.get('clips_posted', 0)
        pending = len(self.queue.get_pending_clips(limit=100))
        
        needed = config.DAILY_CLIP_TARGET - posted_today - pending
        
        if needed <= 0:
            logger.info(f"Already have enough clips ({pending} pending, {posted_today} posted)")
            return
        
        try:
            async with VyroScraper() as scraper:
                clips = await scraper.fetch_new_clips(target_count=needed)
                self.session_stats['clips_fetched'] += len(clips)
                logger.info(f"Fetched {len(clips)} new clips")
                
        except Exception as e:
            logger.error(f"Failed to fetch clips: {e}")
            self.session_stats['errors'] += 1
    
    async def _post_session(self):
        """Run a posting session."""
        logger.info("="*40)
        logger.info("STARTING POSTING SESSION")
        logger.info("="*40)
        
        self.last_post = datetime.now()
        
        # Get pending clips
        pending = self.queue.get_pending_clips(limit=config.CLIPS_PER_SESSION)
        
        if not pending:
            logger.info("No pending clips to post")
            return
        
        logger.info(f"Posting {len(pending)} clips...")
        
        try:
            async with PlatformPoster() as poster:
                results = await poster.post_batch(pending)
                
                # Count successes
                success_count = sum(
                    1 for r in results 
                    if any(pr.success for pr in r.values())
                )
                
                self.session_stats['clips_posted'] += success_count
                logger.info(f"Session complete: {success_count}/{len(pending)} clips posted successfully")
                
        except Exception as e:
            logger.error(f"Posting session failed: {e}")
            self.session_stats['errors'] += 1
    
    async def _submit_to_vyro(self):
        """Submit posted URLs back to Vyro."""
        clips_to_submit = self.queue.get_clips_needing_submission()
        
        if not clips_to_submit:
            return
        
        logger.info(f"Submitting {len(clips_to_submit)} clips to Vyro...")
        
        try:
            async with VyroScraper() as scraper:
                submitted = await scraper.submit_urls_to_vyro(clips_to_submit)
                logger.info(f"Submitted {submitted} clips to Vyro")
                
        except Exception as e:
            logger.error(f"Failed to submit to Vyro: {e}")
    
    def _save_session_stats(self):
        """Save session stats to file."""
        self.session_stats['ended'] = datetime.now().isoformat()
        
        stats_file = config.LOGS_DIR / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(stats_file, 'w') as f:
            json.dump(self.session_stats, f, indent=2)
        
        logger.info(f"Session stats saved to {stats_file}")


class DaemonRunner:
    """Helper class for running daemon in different modes."""
    
    @staticmethod
    async def run_once():
        """Run a single fetch + post cycle."""
        logger.info("Running single cycle...")
        
        queue = QueueManager()
        
        # Fetch clips
        async with VyroScraper() as scraper:
            clips = await scraper.fetch_new_clips(target_count=config.CLIPS_PER_SESSION)
            logger.info(f"Fetched {len(clips)} clips")
        
        # Post clips
        pending = queue.get_pending_clips(limit=config.CLIPS_PER_SESSION)
        if pending:
            async with PlatformPoster() as poster:
                await poster.post_batch(pending)
        
        # Show stats
        tracker = EarningsTracker()
        tracker.display_dashboard()
    
    @staticmethod
    async def run_continuous():
        """Run daemon continuously."""
        daemon = VyroDaemon()
        await daemon.start()
    
    @staticmethod
    async def run_fetch_only():
        """Only fetch clips, don't post."""
        logger.info("Fetching clips only...")
        
        async with VyroScraper() as scraper:
            clips = await scraper.fetch_new_clips(target_count=config.DAILY_CLIP_TARGET)
            logger.info(f"Fetched {len(clips)} clips")
            
            for clip in clips:
                print(f"  - {clip.filename}")
    
    @staticmethod
    async def run_post_only():
        """Only post pending clips."""
        logger.info("Posting pending clips only...")
        
        queue = QueueManager()
        pending = queue.get_pending_clips(limit=config.CLIPS_PER_SESSION)
        
        if not pending:
            logger.info("No pending clips")
            return
        
        async with PlatformPoster() as poster:
            await poster.post_batch(pending)


def main():
    """Entry point for daemon."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Vyro Clipping Daemon")
    parser.add_argument(
        '--mode', 
        choices=['continuous', 'once', 'fetch', 'post'],
        default='continuous',
        help='Run mode: continuous (24/7), once (single cycle), fetch (only fetch), post (only post)'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'continuous':
        asyncio.run(DaemonRunner.run_continuous())
    elif args.mode == 'once':
        asyncio.run(DaemonRunner.run_once())
    elif args.mode == 'fetch':
        asyncio.run(DaemonRunner.run_fetch_only())
    elif args.mode == 'post':
        asyncio.run(DaemonRunner.run_post_only())


if __name__ == "__main__":
    main()
