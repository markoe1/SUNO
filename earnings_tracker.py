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


class EarningsTracker:
    def __init__(self):
        self.queue = QueueManager()
    
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
        print("\n" + "="*60)
        print("💰 VYRO EARNINGS DASHBOARD")
        print("="*60)
        
        # Today's Stats
        print("\n📊 TODAY'S STATS")
        print("-"*40)
        print(f"  Clips Downloaded:  {today.get('clips_downloaded', 0)}")
        print(f"  Clips Posted:      {today.get('clips_posted', 0)}")
        print(f"  Total Views:       {today.get('total_views', 0):,}")
        print(f"  Earnings:          ${today.get('total_earnings', 0):.2f}")
        
        # All Time Stats
        print("\n📈 ALL TIME STATS")
        print("-"*40)
        print(f"  Total Clips:       {all_time.get('total_clips', 0)}")
        print(f"  Total Posted:      {all_time.get('total_posted', 0)}")
        print(f"  Total Views:       {all_time.get('total_views', 0):,}")
        print(f"  Total Earnings:    ${all_time.get('total_earnings', 0):.2f}")
        
        # Goal Progress
        print("\n🎯 GOAL PROGRESS")
        print("-"*40)
        
        daily = progress['daily']
        daily_bar = self._progress_bar(daily['percent'])
        print(f"  Daily (${daily['goal']:.0f}):   {daily_bar} {daily['percent']:.1f}%")
        print(f"                    ${daily['current']:.2f} / ${daily['goal']:.2f}")
        
        monthly = progress['monthly']
        monthly_bar = self._progress_bar(monthly['percent'])
        print(f"  Monthly (${monthly['goal']:.0f}): {monthly_bar} {monthly['percent']:.1f}%")
        print(f"                    ${monthly['current']:.2f} / ${monthly['goal']:.2f}")
        
        # Top Clips
        top_clips = self.get_top_clips(5)
        if top_clips:
            print("\n🏆 TOP PERFORMING CLIPS")
            print("-"*40)
            for i, clip in enumerate(top_clips, 1):
                print(f"  {i}. {clip.filename[:30]}")
                print(f"     Views: {clip.views_total:,} | Earned: ${clip.earnings:.2f}")
        
        # Projections
        print("\n📊 PROJECTIONS")
        print("-"*40)
        views_today = today.get('total_views', 0)
        clips_today = today.get('clips_posted', 0)
        
        if clips_today > 0:
            avg_views = views_today / clips_today
            projected_15 = avg_views * 15 * 3  # 15 clips × 3 platforms
            print(f"  Avg Views/Clip:    {avg_views:,.0f}")
            print(f"  Projected (15/day): ${self.calculate_projected_earnings(projected_15):.2f}/day")
        
        print("\n" + "="*60)
        print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60 + "\n")
    
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
