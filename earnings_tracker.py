"""
Earnings Tracker
================
Track views, calculate earnings, display dashboard.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List

import config
from queue_manager import QueueManager, Clip

logger = logging.getLogger(__name__)



# Singleton instance to reuse database connection
_queue_instance = None

def get_queue_manager():
    """Get or create singleton QueueManager instance."""
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = QueueManager()
    return _queue_instance

class EarningsTracker:
    def __init__(self):
        self.queue = get_queue_manager()
    
    def get_today_stats(self) -> Dict:
        """Get today's statistics."""
        return self.queue.get_daily_stats()
    
    def get_all_time_stats(self) -> Dict:
        """Get lifetime statistics."""
        return self.queue.get_all_time_stats()
    
    def calculate_projected_earnings(self, views: int) -> float:
        """Calculate earnings from views."""
        return (views / 1000) * config.CPM_RATE
    
    def get_goal_progress(self) -> Dict:
        """Get progress toward daily and monthly goals."""
        today = self.get_today_stats()
        all_time = self.get_all_time_stats()
        
        # Get this month's earnings
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        # Approximate monthly from all_time for now
        monthly_earnings = all_time.get('total_earnings', 0)
        
        return {
            'daily': {
                'current': today.get('total_earnings', 0),
                'goal': config.DAILY_EARNINGS_GOAL,
                'percent': min(100, (today.get('total_earnings', 0) / config.DAILY_EARNINGS_GOAL) * 100) if config.DAILY_EARNINGS_GOAL > 0 else 0,
            },
            'monthly': {
                'current': monthly_earnings,
                'goal': config.MONTHLY_EARNINGS_GOAL,
                'percent': min(100, (monthly_earnings / config.MONTHLY_EARNINGS_GOAL) * 100) if config.MONTHLY_EARNINGS_GOAL > 0 else 0,
            }
        }
    
    def get_top_clips(self, limit: int = 10) -> List[Clip]:
        """Get top performing clips by views."""
        clips = self.queue.get_posted_clips(since_hours=24*30)  # Last 30 days
        return sorted(clips, key=lambda c: c.views_total, reverse=True)[:limit]
    
    def display_dashboard(self):
        """Display earnings dashboard in terminal."""
        today = self.get_today_stats()
        all_time = self.get_all_time_stats()
        progress = self.get_goal_progress()
        
        # Clear screen and display
        logger.info("\n" + "="*60)
        logger.info("💰 SUNO EARNINGS DASHBOARD")
        logger.info("="*60)
        
        # Today's Stats
        logger.info("\n📊 TODAY'S STATS")
        logger.info("-"*40)
        logger.info(f"  Clips Downloaded:  {today.get('clips_downloaded', 0)}")
        logger.info(f"  Clips Posted:      {today.get('clips_posted', 0)}")
        logger.info(f"  Total Views:       {today.get('total_views', 0):,}")
        logger.info(f"  Earnings:          ${today.get('total_earnings', 0):.2f}")
        
        # All Time Stats
        logger.info("\n📈 ALL TIME STATS")
        logger.info("-"*40)
        logger.info(f"  Total Clips:       {all_time.get('total_clips', 0)}")
        logger.info(f"  Total Posted:      {all_time.get('total_posted', 0)}")
        logger.info(f"  Total Views:       {all_time.get('total_views', 0):,}")
        logger.info(f"  Total Earnings:    ${all_time.get('total_earnings', 0):.2f}")
        
        # Goal Progress
        logger.info("\n🎯 GOAL PROGRESS")
        logger.info("-"*40)
        
        daily = progress['daily']
        daily_bar = self._progress_bar(daily['percent'])
        logger.info(f"  Daily (${daily['goal']:.0f}):   {daily_bar} {daily['percent']:.1f}%")
        logger.info(f"                    ${daily['current']:.2f} / ${daily['goal']:.2f}")
        
        monthly = progress['monthly']
        monthly_bar = self._progress_bar(monthly['percent'])
        logger.info(f"  Monthly (${monthly['goal']:.0f}): {monthly_bar} {monthly['percent']:.1f}%")
        logger.info(f"                    ${monthly['current']:.2f} / ${monthly['goal']:.2f}")
        
        # Top Clips
        top_clips = self.get_top_clips(5)
        if top_clips:
            logger.info("\n🏆 TOP PERFORMING CLIPS")
            logger.info("-"*40)
            for i, clip in enumerate(top_clips, 1):
                logger.info(f"  {i}. {clip.filename[:30]}")
                logger.info(f"     Views: {clip.views_total:,} | Earned: ${clip.earnings:.2f}")
        
        # Projections
        logger.info("\n📊 PROJECTIONS")
        logger.info("-"*40)
        views_today = today.get('total_views', 0)
        clips_today = today.get('clips_posted', 0)
        
        if clips_today > 0:
            avg_views = views_today / clips_today
            projected_15 = avg_views * 15 * 3  # 15 clips × 3 platforms
            logger.info(f"  Avg Views/Clip:    {avg_views:,.0f}")
            logger.info(f"  Projected (15/day): ${self.calculate_projected_earnings(projected_15):.2f}/day")
        
        logger.info("\n" + "="*60)
        logger.info(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*60 + "\n")
    
    def _progress_bar(self, percent: float, width: int = 20) -> str:
        """Create a text progress bar."""
        filled = int(width * percent / 100)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}]"
    
    def get_stats_json(self) -> Dict:
        """Get all stats as JSON for API/export."""
        return {
            'today': self.get_today_stats(),
            'all_time': self.get_all_time_stats(),
            'goals': self.get_goal_progress(),
            'top_clips': [
                {
                    'filename': c.filename,
                    'campaign': c.campaign_name,
                    'views': c.views_total,
                    'earnings': c.earnings,
                }
                for c in self.get_top_clips(10)
            ],
            'timestamp': datetime.now().isoformat(),
        }


def main():
    """Display dashboard."""
    tracker = EarningsTracker()
    tracker.display_dashboard()


if __name__ == "__main__":
    main()
