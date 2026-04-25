"""
Daemon Runner
=============
24/7 continuous operation for the Whop clipping system.
Handles scheduling, health checks, warmup gates, and automatic recovery.
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
from queue_manager import QueueManager, ClipStatus, AccountState
from services.whop_client import WhopClient
from platform_poster import PlatformPoster
from earnings_tracker import EarningsTracker
from quality_monitor import QualityMonitor
from clip_pipeline import ClipPipeline
from daemon_reliability import DaemonHealth, DaemonRecovery, ResourceCleaner
from monitoring import EventMonitor, SafetyLimiter, AnomalyDetector, MonitoringEvent, EventType

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


class WhopDaemon:
    """24/7 Whop clipping daemon."""
    
    def __init__(self):
        self.queue = QueueManager()
        self.tracker = EarningsTracker()
        self.quality_monitor = QualityMonitor()
        self.pipeline = ClipPipeline()
        self.health = DaemonHealth()
        self.recovery = DaemonRecovery()
        self.cleaner = ResourceCleaner()
        self.monitor = EventMonitor()
        self.limiter = SafetyLimiter()
        self.anomaly_detector = AnomalyDetector(self.monitor)
        self.running = False
        self.last_fetch = None
        self.last_post = None
        self.last_health_check = None
        self.last_pipeline = None
        self.last_cleanup = None

        # Stats for current session
        self.session_stats = {
            'started': datetime.now().isoformat(),
            'clips_fetched': 0,
            'clips_posted': 0,
            'clips_ingested': 0,
            'errors': 0,
        }
    
    async def start(self):
        """Start the daemon."""
        self.running = True
        logger.info("="*60)
        logger.info("WHOPCLIPPER DAEMON STARTING")
        logger.info("="*60)
        logger.info(f"Target: {config.DAILY_CLIP_TARGET} clips/day")
        logger.info(f"Sessions: {config.SESSIONS_PER_DAY}/day at {config.POSTING_TIMES}")
        logger.info(f"Whop check interval: {config.WHOP_CHECK_INTERVAL} minutes")
        logger.info(f"Warmup hold: {config.WARMUP_HOURS} hours")
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
                # Health check
                if self._should_health_check():
                    await self._health_check()

                # Promote NEW accounts that have cleared the warmup hold
                self._tick_account_warmup()

                # Process clips in inbox (PHASE 6: Autonomous pipeline)
                if self._should_run_pipeline():
                    await self._run_pipeline()

                # Refresh Whop campaigns periodically
                if self._should_fetch_clips():
                    await self._refresh_campaigns()

                # Post session if it's a scheduled posting time
                if self._should_post():
                    await self._post_session()

                # Submit any unsubmitted clip URLs to Whop
                await self._submit_pending()

                # Resource cleanup (PHASE 7: Daemon reliability)
                if self._should_cleanup():
                    await self._run_cleanup()

                # Sleep before next iteration
                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.session_stats['errors'] += 1
                # Record crash for recovery monitoring
                if not self.recovery.record_crash():
                    logger.critical("Too many crashes, stopping daemon")
                    self.running = False
                await asyncio.sleep(60)
        
        logger.info("Daemon stopped")
        await self._save_session_stats()
    
    def _should_health_check(self) -> bool:
        """Check if it's time for a health check."""
        if self.last_health_check is None:
            return True
        
        elapsed = (datetime.now() - self.last_health_check).total_seconds() / 60
        return elapsed >= config.HEALTH_CHECK_INTERVAL
    
    def _should_fetch_clips(self) -> bool:
        """Time to refresh Whop campaigns?"""
        if self.last_fetch is None:
            return True
        elapsed = (datetime.now() - self.last_fetch).total_seconds() / 60
        return elapsed >= config.WHOP_CHECK_INTERVAL

    def _should_post(self) -> bool:
        """Is it a scheduled posting time?"""
        now = datetime.now()
        for post_time in config.POSTING_TIMES:
            post_hour, post_min = map(int, post_time.split(":"))
            post_dt = now.replace(hour=post_hour, minute=post_min, second=0)
            diff = abs((now - post_dt).total_seconds())
            if diff <= 300:
                if self.last_post is None:
                    return True
                if (now - self.last_post).total_seconds() > 600:
                    return True
        return False

    def _should_run_pipeline(self) -> bool:
        """Should we run clip discovery pipeline? (every 5 minutes)"""
        if self.last_pipeline is None:
            return True
        elapsed = (datetime.now() - self.last_pipeline).total_seconds() / 60
        return elapsed >= 5

    async def _run_pipeline(self):
        """Process clips in inbox (PHASE 6: Autonomous pipeline)."""
        logger.info("Running clip discovery pipeline...")
        self.last_pipeline = datetime.now()
        try:
            stats = self.pipeline.process_inbox()
            if stats['ingested'] > 0:
                self.session_stats['clips_ingested'] += stats['ingested']
                logger.info(f"Pipeline ingested {stats['ingested']} clips")
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self.session_stats['errors'] += 1

    def _should_cleanup(self) -> bool:
        """Should we run resource cleanup? (every 24 hours)"""
        if self.last_cleanup is None:
            return False  # Don't cleanup immediately on startup
        elapsed = (datetime.now() - self.last_cleanup).total_seconds() / 3600
        return elapsed >= 24

    async def _run_cleanup(self):
        """Run resource cleanup and maintenance (PHASE 7)."""
        logger.info("Running resource cleanup...")
        self.last_cleanup = datetime.now()
        try:
            await self.cleaner.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            self.session_stats['errors'] += 1

    def _tick_account_warmup(self):
        """
        Promote NEW accounts that have cleared the warmup hold to WARMING,
        and WARMING accounts with posts to ACTIVE.
        """
        accounts = self.queue.get_all_accounts()
        for acc in accounts:
            if acc.state == AccountState.NEW.value and acc.created_at:
                created  = datetime.fromisoformat(acc.created_at)
                hours_old = (datetime.now() - created).total_seconds() / 3600
                if hours_old >= config.WARMUP_HOURS:
                    self.queue.update_account_state(
                        acc.platform, acc.username, AccountState.WARMING
                    )
                    logger.info(
                        f"Account {acc.platform}/{acc.username} promoted NEW → WARMING"
                    )
            elif acc.state == AccountState.WARMING.value and acc.total_posts >= 5:
                self.queue.update_account_state(
                    acc.platform, acc.username, AccountState.ACTIVE
                )
                logger.info(
                    f"Account {acc.platform}/{acc.username} promoted WARMING → ACTIVE"
                )

    async def _health_check(self):
        """Comprehensive health check including system resources."""
        logger.info("=" * 60)
        logger.info("HEALTH CHECK")
        logger.info("=" * 60)
        self.last_health_check = datetime.now()

        try:
            # System health
            health_result = self.health.full_health_check(self.queue)
            if not health_result['healthy']:
                logger.warning("System health issues detected:")
                for check_name, check_data in health_result['checks'].items():
                    if not check_data['ok']:
                        logger.warning(f"  {check_name}: {check_data['message']}")

            # Operational stats
            pending = self.queue.get_pending_clips(limit=100)
            today = self.queue.get_daily_stats()
            accounts = self.queue.get_all_accounts()
            ready_accs = sum(
                1 for a in accounts
                if self.queue.account_can_post(a.platform, a.username)
            )

            logger.info(
                f"Inbox: {len(pending)} clips | "
                f"Posted today: {today.get('clips_posted', 0)} | "
                f"Accounts: {ready_accs}/{len(accounts)} ready"
            )

            # Earnings
            self.tracker.display_dashboard()

            # Reset crash counter on successful check
            self.recovery.reset_crash_count()

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.session_stats['errors'] += 1

    async def _refresh_campaigns(self):
        """Refresh Whop campaign list via official API."""
        logger.info("Refreshing Whop campaigns...")
        self.last_fetch = datetime.now()
        try:
            client = WhopClient()
            campaigns = client.list_campaigns()
            self.session_stats['clips_fetched'] += len(campaigns)
            logger.info(f"Campaigns refreshed: {len(campaigns)} active")
        except Exception as e:
            logger.error(f"Campaign refresh failed: {e}")
            self.session_stats['errors'] += 1

    async def _post_session(self):
        """Post a batch of clips, respecting warmup gates and safety limits."""
        logger.info("=" * 40)
        logger.info("POSTING SESSION")
        logger.info("=" * 40)
        self.last_post = datetime.now()

        # Check safety limits before posting (PHASE 8)
        if not self.limiter.is_safe_to_proceed():
            limits = self.limiter.check_all_limits()
            logger.warning("Safety limits triggered, skipping posting session:")
            for limit_name, (ok, reason) in limits.items():
                if not ok:
                    logger.warning(f"  {limit_name}: {reason}")
                    self.monitor.log_event(MonitoringEvent(
                        timestamp=datetime.now().isoformat(),
                        event_type='safety_limit',
                        error_message=f"{limit_name}: {reason}",
                        severity='warning'
                    ))
            return

        pending = self.queue.get_pending_clips(limit=config.CLIPS_PER_SESSION)
        if not pending:
            logger.info("No pending clips in inbox")
            return

        logger.info(f"Posting {len(pending)} clips...")
        try:
            async with PlatformPoster() as poster:
                results = await poster.post_batch(pending)
                success_count = sum(
                    1 for r in results if any(pr.success for pr in r.values())
                )
                self.session_stats['clips_posted'] += success_count

                # Log each result as monitoring event
                for i, clip in enumerate(pending):
                    if i < len(results):
                        result_dict = results[i]
                        success = any(pr.success for pr in result_dict.values())
                        if success:
                            self.monitor.log_event(MonitoringEvent(
                                timestamp=datetime.now().isoformat(),
                                event_type=EventType.CLIP_POSTED.value,
                                clip_id=clip.id,
                                clip_name=clip.filename,
                                context={'platforms': list(result_dict.keys())},
                            ))
                        else:
                            self.monitor.log_event(MonitoringEvent(
                                timestamp=datetime.now().isoformat(),
                                event_type=EventType.CLIP_FAILED.value,
                                clip_id=clip.id,
                                clip_name=clip.filename,
                                severity='error'
                            ))

                logger.info(f"Session done: {success_count}/{len(pending)} clips posted")
        except Exception as e:
            logger.error(f"Posting session failed: {e}")
            self.session_stats['errors'] += 1
            self.monitor.log_event(MonitoringEvent(
                timestamp=datetime.now().isoformat(),
                event_type=EventType.POSTING_ERROR.value,
                error_message=str(e),
                severity='error'
            ))

        # Check for anomalies (PHASE 8)
        anomalies = self.anomaly_detector.detect_anomalies()
        if anomalies:
            logger.warning(f"Anomalies detected: {', '.join(anomalies)}")
            for anomaly in anomalies:
                self.monitor.log_event(MonitoringEvent(
                    timestamp=datetime.now().isoformat(),
                    event_type='anomaly',
                    error_message=anomaly,
                    severity='warning'
                ))

    async def _submit_pending(self):
        """Submit all posted-but-not-submitted clips to Whop via official API."""
        clips = self.queue.get_clips_needing_submission()
        if not clips:
            return
        logger.info(f"Submitting {len(clips)} clips to Whop...")
        try:
            client = WhopClient()
            submitted = 0
            for clip in clips:
                # Get first available platform URL (prefer TikTok > Instagram > YouTube)
                clip_url = clip.tiktok_url or clip.instagram_url or clip.youtube_url
                if not clip_url:
                    logger.warn(f"Clip {clip.id} has no posted URLs, skipping submission")
                    continue

                result = client.submit_clip(clip.campaign_id, clip_url)
                if result.get('success'):
                    self.queue.update_clip_status(clip.id, ClipStatus.SUBMITTED)
                    submitted += 1
            logger.info(f"Submitted {submitted}/{len(clips)} clips")
        except Exception as e:
            logger.error(f"Whop submission failed: {e}")
    
    async def _save_session_stats(self):
        """Save session stats to file asynchronously."""
        try:
            self.session_stats['ended'] = datetime.now().isoformat()
            
            # Create logs directory if it doesn't exist
            config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
            
            stats_file = config.LOGS_DIR / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Use executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: stats_file.write_text(json.dumps(self.session_stats, indent=2))
            )
            
            logger.info(f"Session stats saved to {stats_file}")
        except Exception as e:
            logger.error(f"Failed to save session stats: {e}")


class DaemonRunner:
    """Helper class for running daemon in different modes."""
    
    @staticmethod
    async def run_once():
        """Single cycle: refresh campaigns + post pending clips."""
        logger.info("Running single cycle...")
        queue = QueueManager()
        try:
            client = WhopClient()
            campaigns = client.list_campaigns()
            logger.info(f"Campaigns refreshed: {len(campaigns)}")
        except Exception as e:
            logger.error(f"Campaign refresh failed: {e}")

        pending = queue.get_pending_clips(limit=config.CLIPS_PER_SESSION)
        if pending:
            async with PlatformPoster() as poster:
                await poster.post_batch(pending)
        EarningsTracker().display_dashboard()

    @staticmethod
    async def run_continuous():
        """Run daemon continuously."""
        daemon = WhopDaemon()
        await daemon.start()

    @staticmethod
    async def run_fetch_only():
        """Only refresh campaigns, don't post."""
        logger.info("Refreshing campaigns only...")
        try:
            client = WhopClient()
            campaigns = client.list_campaigns()
            logger.info(f"Active campaigns: {len(campaigns)}")
            for c in campaigns:
                logger.info(f"  {c['name']} | CPM ${c.get('cpm', 0):.2f}")
        except Exception as e:
            logger.error(f"Campaign refresh failed: {e}")
    
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
    
    parser = argparse.ArgumentParser(description="WhopClipper Daemon")
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
