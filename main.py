"""
VyroClipper - Main Entry Point
==============================
CLI interface for all operations.
"""

import asyncio
import argparse
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import config
from queue_manager import QueueManager
from vyro_scraper import VyroScraper
from platform_poster import PlatformPoster
from earnings_tracker import EarningsTracker
from daemon import VyroDaemon, DaemonRunner

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
    datefmt=config.LOG_DATE_FORMAT,
)
logger = logging.getLogger(__name__)


def print_banner():
    """Print startup banner."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ██╗   ██╗██╗   ██╗██████╗  ██████╗                        ║
║   ██║   ██║╚██╗ ██╔╝██╔══██╗██╔═══██╗                       ║
║   ██║   ██║ ╚████╔╝ ██████╔╝██║   ██║                       ║
║   ╚██╗ ██╔╝  ╚██╔╝  ██╔══██╗██║   ██║                       ║
║    ╚████╔╝    ██║   ██║  ██║╚██████╔╝                       ║
║     ╚═══╝     ╚═╝   ╚═╝  ╚═╝ ╚═════╝                        ║
║                                                              ║
║   C L I P P E R   S Y S T E M                               ║
║   $3/1K Views | 24/7 Automation                             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


async def cmd_fetch(args):
    """Fetch clips from Vyro."""
    count = args.count or config.DAILY_CLIP_TARGET
    logger.info(f"Fetching {count} clips from Vyro...")
    
    async with VyroScraper() as scraper:
        clips = await scraper.fetch_new_clips(target_count=count)
        
        print(f"\n✅ Fetched {len(clips)} clips:")
        for clip in clips:
            print(f"   - {clip.filename} ({clip.campaign_name})")


async def cmd_post(args):
    """Post pending clips."""
    count = args.count or config.CLIPS_PER_SESSION
    
    queue = QueueManager()
    pending = queue.get_pending_clips(limit=count)
    
    if not pending:
        print("No pending clips to post")
        return
    
    logger.info(f"Posting {len(pending)} clips...")
    
    async with PlatformPoster() as poster:
        results = await poster.post_batch(pending)
        
        print(f"\n📊 Results:")
        for i, clip_results in enumerate(results):
            print(f"\n   Clip {i+1}:")
            for platform, result in clip_results.items():
                status = "✅" if result.success else "❌"
                print(f"     {status} {platform}: {result.url or result.error}")


async def cmd_run(args):
    """Run full workflow (fetch + post)."""
    count = args.count or config.CLIPS_PER_SESSION
    
    print(f"\n🚀 Running full workflow ({count} clips)...\n")
    
    # Fetch
    async with VyroScraper() as scraper:
        clips = await scraper.fetch_new_clips(target_count=count)
        print(f"✅ Fetched {len(clips)} clips")
    
    # Post
    queue = QueueManager()
    pending = queue.get_pending_clips(limit=count)
    
    if pending:
        async with PlatformPoster() as poster:
            results = await poster.post_batch(pending)
            success = sum(1 for r in results if any(pr.success for pr in r.values()))
            print(f"✅ Posted {success}/{len(pending)} clips")
    
    # Show stats
    tracker = EarningsTracker()
    tracker.display_dashboard()


async def cmd_daemon(args):
    """Run 24/7 daemon."""
    print("\n🔄 Starting 24/7 daemon...\n")
    daemon = VyroDaemon()
    await daemon.start()


def cmd_status(args):
    """Show current status."""
    queue = QueueManager()
    tracker = EarningsTracker()
    
    pending = queue.get_pending_clips(limit=100)
    today = queue.get_daily_stats()
    
    print("\n📊 CURRENT STATUS")
    print("="*40)
    print(f"Pending clips:     {len(pending)}")
    print(f"Posted today:      {today.get('clips_posted', 0)}")
    print(f"Views today:       {today.get('total_views', 0):,}")
    print(f"Earnings today:    ${today.get('total_earnings', 0):.2f}")
    print("="*40)


def cmd_dashboard(args):
    """Show earnings dashboard."""
    tracker = EarningsTracker()
    tracker.display_dashboard()


def cmd_test(args):
    """Test mode - dry run without posting."""
    print("\n🧪 TEST MODE")
    print("="*40)
    
    # Check config
    print("\n✅ Configuration:")
    print(f"   Daily target: {config.DAILY_CLIP_TARGET} clips")
    print(f"   Post times: {config.POSTING_TIMES}")
    print(f"   Platforms: {config.PLATFORMS}")
    
    # Check credentials
    print("\n🔑 Credentials:")
    print(f"   Vyro: {'✅ Set' if config.VYRO_EMAIL else '❌ Missing'}")
    print(f"   TikTok: {'✅ Set' if config.TIKTOK_USERNAME else '❌ Missing'}")
    print(f"   Instagram: {'✅ Set' if config.INSTAGRAM_USERNAME else '❌ Missing'}")
    print(f"   YouTube: {'✅ Set' if config.YOUTUBE_EMAIL else '❌ Missing'}")
    
    # Check directories
    print("\n📁 Directories:")
    for name, path in [
        ("Inbox", config.CLIPS_INBOX),
        ("Ready", config.CLIPS_READY),
        ("Posted", config.CLIPS_POSTED),
        ("Failed", config.CLIPS_FAILED),
        ("Logs", config.LOGS_DIR),
        ("Data", config.DATA_DIR),
    ]:
        exists = "✅" if path.exists() else "❌"
        print(f"   {exists} {name}: {path}")
    
    # Check database
    print("\n💾 Database:")
    queue = QueueManager()
    print(f"   ✅ Connected: {config.DB_PATH}")
    
    print("\n" + "="*40)
    print("Test complete! Run with --mode run to start.")


def main():
    """Main entry point."""
    print_banner()
    
    parser = argparse.ArgumentParser(
        description="VyroClipper - Automated Vyro Clipping System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode fetch --count 15    # Fetch 15 clips from Vyro
  python main.py --mode post --count 5      # Post 5 pending clips
  python main.py --mode run --count 15      # Full workflow (fetch + post)
  python main.py --mode daemon              # Run 24/7 daemon
  python main.py --mode status              # Show current status
  python main.py --mode dashboard           # Show earnings dashboard
  python main.py --mode test                # Test configuration
        """
    )
    
    parser.add_argument(
        '--mode', '-m',
        choices=['fetch', 'post', 'run', 'daemon', 'status', 'dashboard', 'test'],
        default='status',
        help='Operation mode'
    )
    
    parser.add_argument(
        '--count', '-c',
        type=int,
        help='Number of clips to fetch/post'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Route to appropriate command
    if args.mode == 'fetch':
        asyncio.run(cmd_fetch(args))
    elif args.mode == 'post':
        asyncio.run(cmd_post(args))
    elif args.mode == 'run':
        asyncio.run(cmd_run(args))
    elif args.mode == 'daemon':
        asyncio.run(cmd_daemon(args))
    elif args.mode == 'status':
        cmd_status(args)
    elif args.mode == 'dashboard':
        cmd_dashboard(args)
    elif args.mode == 'test':
        cmd_test(args)


if __name__ == "__main__":
    main()
