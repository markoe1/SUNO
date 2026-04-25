"""
WhopClipper — Main Entry Point
===============================
CLI for all operations.

Modes:
  campaigns  — Discover + refresh Whop campaigns
  fetch      — Alias for campaigns (kept for compat)
  post       — Post pending clips from inbox
  run        — campaigns + post (full cycle)
  daemon     — 24/7 automated loop
  status     — Show queue + account status
  dashboard  — Earnings overview
  test       — Verify config + credentials
"""

import asyncio
import argparse
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from queue_manager import QueueManager, AccountState
from services.whop_client import WhopClient
from platform_poster import PlatformPoster
from earnings_tracker import EarningsTracker
from daemon import WhopDaemon

logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
    datefmt=config.LOG_DATE_FORMAT,
)
logger = logging.getLogger(__name__)


def print_banner():
    logger.info("=" * 50)
    logger.info("  WhopClipper — Whop Edition")
    logger.info("  $3/1K Views | 24/7 Automation")
    logger.info("=" * 50)


# ── Mode handlers ─────────────────────────────────────────────────────────────

async def cmd_campaigns(args):
    """Discover and refresh Whop campaigns via official API."""
    logger.info("\nRefreshing Whop campaigns...\n")
    try:
        client = WhopClient()
        campaigns = client.list_campaigns()
        logger.info(f"\nFound {len(campaigns)} campaigns:")
        for c in campaigns:
            logger.info(f"  {c['name']}")
            logger.info(f"    CPM: ${c.get('cpm', 0):.2f} | Free: {c.get('is_free', False)}")
            if c.get('drive_url'):
                logger.info(f"    Drive: {c['drive_url'][:70]}")
            if c.get('youtube_url'):
                logger.info(f"    YouTube: {c['youtube_url'][:70]}")
    except Exception as e:
        logger.info(f"\nError refreshing campaigns: {e}")
        logger.info("Make sure WHOP_API_KEY is set in .env")


async def cmd_post(args):
    """Post pending clips from inbox."""
    count = args.count or config.CLIPS_PER_SESSION
    queue = QueueManager()
    pending = queue.get_pending_clips(limit=count)

    if not pending:
        logger.info("No pending clips to post")
        return

    logger.info(f"Posting {len(pending)} clips...")
    async with PlatformPoster() as poster:
        results = await poster.post_batch(pending)
        logger.info(f"\nResults:")
        for i, clip_results in enumerate(results):
            logger.info(f"\n  Clip {i+1}:")
            for platform, result in clip_results.items():
                status = "OK" if result.success else "FAIL"
                logger.info(f"    [{status}] {platform}: {result.url or result.error}")


async def cmd_run(args):
    """Full cycle: refresh campaigns then post."""
    count = args.count or config.CLIPS_PER_SESSION
    logger.info(f"\nFull cycle ({count} clips)...\n")

    # Refresh campaigns
    try:
        client = WhopClient()
        campaigns = client.list_campaigns()
        logger.info(f"Campaigns: {len(campaigns)} active")
    except Exception as e:
        logger.info(f"Campaign refresh failed: {e}")

    # Post pending clips
    queue = QueueManager()
    pending = queue.get_pending_clips(limit=count)
    if pending:
        async with PlatformPoster() as poster:
            results = await poster.post_batch(pending)
            success = sum(1 for r in results if any(pr.success for pr in r.values()))
            logger.info(f"Posted: {success}/{len(pending)} clips")
    else:
        logger.info("No clips in inbox. Drop .mp4 files into clips/inbox/ to post.")

    EarningsTracker().display_dashboard()


async def cmd_daemon(args):
    """Run 24/7 daemon."""
    logger.info("\nStarting 24/7 daemon...\n")
    daemon = WhopDaemon()
    await daemon.start()


def cmd_status(args):
    """Show queue + account status."""
    queue   = QueueManager()
    tracker = EarningsTracker()
    pending = queue.get_pending_clips(limit=100)
    today   = queue.get_daily_stats()

    logger.info("\nSTATUS")
    logger.info("=" * 44)
    logger.info(f"Clips in inbox:    {len(pending)}")
    logger.info(f"Posted today:      {today.get('clips_posted', 0)}")
    logger.info(f"Views today:       {today.get('total_views', 0):,}")
    logger.info(f"Earnings today:    ${today.get('total_earnings', 0):.2f}")

    # Account warmup table
    accounts = queue.get_all_accounts()
    if accounts:
        logger.info(f"\nACCOUNTS ({len(accounts)})")
        logger.info(f"  {'Platform':<12} {'Username':<20} {'State':<10} {'Posts today'}")
        logger.info("  " + "-" * 56)
        today_str = __import__('datetime').datetime.now().strftime("%Y-%m-%d")
        for acc in accounts:
            posts = acc.posts_today if acc.posts_today_date == today_str else 0
            limit = queue.get_account_daily_limit(acc)
            can   = "GO" if queue.account_can_post(acc.platform, acc.username) else "WAIT"
            logger.info(f"  {acc.platform:<12} {acc.username:<20} {acc.state:<10} {posts}/{limit}  [{can}]")

    # Active campaigns
    campaigns = queue.get_active_campaigns()
    if campaigns:
        logger.info(f"\nCAMPAIGNS ({len(campaigns)})")
        for c in campaigns:
            logger.info(f"  {c.name[:40]:<40} CPM ${c.cpm:.2f}")

    logger.info("=" * 44)


def cmd_dashboard(args):
    EarningsTracker().display_dashboard()


def cmd_test(args):
    """Verify config and credentials."""
    logger.info("\nTEST MODE")
    logger.info("=" * 44)

    logger.info("\nConfiguration:")
    logger.info(f"  Daily target:     {config.DAILY_CLIP_TARGET} clips")
    logger.info(f"  Post times:       {config.POSTING_TIMES}")
    logger.info(f"  Platforms:        {config.PLATFORMS}")
    logger.info(f"  Min CPM:          ${config.MIN_CPM}")
    logger.info(f"  Free only:        {config.FREE_ONLY}")
    logger.info(f"  Warmup hours:     {config.WARMUP_HOURS}")

    logger.info("\nCredentials:")
    logger.info(f"  Whop API Key:   {'SET' if config.WHOP_API_KEY else 'MISSING'}")
    logger.info(f"  TikTok:         {'SET' if config.TIKTOK_USERNAME else 'MISSING'}")
    logger.info(f"  Instagram:      {'SET' if config.INSTAGRAM_USERNAME else 'MISSING'}")
    logger.info(f"  YouTube:        {'SET' if config.YOUTUBE_EMAIL else 'MISSING'}")

    logger.info("\nDirectories:")
    for label, path in [
        ("Inbox",  config.CLIPS_INBOX),
        ("Posted", config.CLIPS_POSTED),
        ("Failed", config.CLIPS_FAILED),
        ("Logs",   config.LOGS_DIR),
        ("Data",   config.DATA_DIR),
    ]:
        exists = "OK" if path.exists() else "MISSING"
        logger.info(f"  [{exists}] {label}: {path}")

    logger.info("\nDatabase:")
    queue = QueueManager()
    logger.info(f"  Connected: {config.DB_PATH}")

    logger.info("\n" + "=" * 44)
    if not config.WHOP_API_KEY:
        logger.info("ERROR: WHOP_API_KEY not set in .env file")
    else:
        logger.info("All critical configuration looks good!")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="WhopClipper — automated Whop clipping system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode campaigns          # Refresh campaign list
  python main.py --mode post --count 5     # Post 5 clips from inbox
  python main.py --mode run  --count 15   # Full cycle (campaigns + post)
  python main.py --mode daemon             # 24/7 daemon
  python main.py --mode status             # Queue + account status
  python main.py --mode dashboard          # Earnings overview
  python main.py --mode test               # Verify setup
        """
    )

    parser.add_argument(
        "--mode", "-m",
        choices=["campaigns", "fetch", "post", "run",
                 "daemon", "status", "dashboard", "test"],
        default="status",
    )
    parser.add_argument("--count", "-c", type=int)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    dispatch = {
        "campaigns": lambda: asyncio.run(cmd_campaigns(args)),
        "fetch":     lambda: asyncio.run(cmd_campaigns(args)),  # alias
        "post":      lambda: asyncio.run(cmd_post(args)),
        "run":       lambda: asyncio.run(cmd_run(args)),
        "daemon":    lambda: asyncio.run(cmd_daemon(args)),
        "status":    lambda: cmd_status(args),
        "dashboard": lambda: cmd_dashboard(args),
        "test":      lambda: cmd_test(args),
    }

    dispatch[args.mode]()


if __name__ == "__main__":
    main()
