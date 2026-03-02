"""
WhopClipper — Main Entry Point
===============================
CLI for all operations.

Modes:
  login      — Open browser, log into Whop, save session (run once)
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
from whop_scraper import WhopScraper
from platform_poster import PlatformPoster
from earnings_tracker import EarningsTracker
from daemon import VyroDaemon

logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
    datefmt=config.LOG_DATE_FORMAT,
)
logger = logging.getLogger(__name__)


def print_banner():
    print("=" * 50)
    print("  WhopClipper — Whop Edition")
    print("  $3/1K Views | 24/7 Automation")
    print("=" * 50)


# ── Mode handlers ─────────────────────────────────────────────────────────────

async def cmd_login(args):
    """Save Whop session interactively."""
    print("\nOpening browser for Whop login...\n")
    async with WhopScraper() as scraper:
        success = await scraper.login()
        if success:
            print("\nLogin successful. Session saved to data/whop_session.json")
            print("You won't need to do this again unless the session expires.")
        else:
            print("\nLogin failed or timed out. Try again.")


async def cmd_campaigns(args):
    """Discover and refresh Whop campaigns."""
    print("\nRefreshing Whop campaigns...\n")
    async with WhopScraper() as scraper:
        campaigns = await scraper.refresh_campaigns()
        print(f"\nFound {len(campaigns)} campaigns:")
        for c in campaigns:
            print(f"  {c.name}")
            print(f"    CPM: ${c.cpm:.2f} | Budget: ${c.budget_remaining:.0f} | Free: {c.is_free}")
            if c.drive_url:
                print(f"    Drive: {c.drive_url[:70]}")
            if c.youtube_url:
                print(f"    YouTube: {c.youtube_url[:70]}")


async def cmd_post(args):
    """Post pending clips from inbox."""
    count = args.count or config.CLIPS_PER_SESSION
    queue = QueueManager()
    pending = queue.get_pending_clips(limit=count)

    if not pending:
        print("No pending clips to post")
        return

    logger.info(f"Posting {len(pending)} clips...")
    async with PlatformPoster() as poster:
        results = await poster.post_batch(pending)
        print(f"\nResults:")
        for i, clip_results in enumerate(results):
            print(f"\n  Clip {i+1}:")
            for platform, result in clip_results.items():
                status = "OK" if result.success else "FAIL"
                print(f"    [{status}] {platform}: {result.url or result.error}")


async def cmd_run(args):
    """Full cycle: refresh campaigns then post."""
    count = args.count or config.CLIPS_PER_SESSION
    print(f"\nFull cycle ({count} clips)...\n")

    # Refresh campaigns
    async with WhopScraper() as scraper:
        campaigns = await scraper.refresh_campaigns()
        print(f"Campaigns: {len(campaigns)} active")

    # Post pending clips
    queue = QueueManager()
    pending = queue.get_pending_clips(limit=count)
    if pending:
        async with PlatformPoster() as poster:
            results = await poster.post_batch(pending)
            success = sum(1 for r in results if any(pr.success for pr in r.values()))
            print(f"Posted: {success}/{len(pending)} clips")
    else:
        print("No clips in inbox. Drop .mp4 files into clips/inbox/ to post.")

    EarningsTracker().display_dashboard()


async def cmd_daemon(args):
    """Run 24/7 daemon."""
    print("\nStarting 24/7 daemon...\n")
    daemon = VyroDaemon()
    await daemon.start()


def cmd_status(args):
    """Show queue + account status."""
    queue   = QueueManager()
    tracker = EarningsTracker()
    pending = queue.get_pending_clips(limit=100)
    today   = queue.get_daily_stats()

    print("\nSTATUS")
    print("=" * 44)
    print(f"Clips in inbox:    {len(pending)}")
    print(f"Posted today:      {today.get('clips_posted', 0)}")
    print(f"Views today:       {today.get('total_views', 0):,}")
    print(f"Earnings today:    ${today.get('total_earnings', 0):.2f}")

    # Account warmup table
    accounts = queue.get_all_accounts()
    if accounts:
        print(f"\nACCOUNTS ({len(accounts)})")
        print(f"  {'Platform':<12} {'Username':<20} {'State':<10} {'Posts today'}")
        print("  " + "-" * 56)
        today_str = __import__('datetime').datetime.now().strftime("%Y-%m-%d")
        for acc in accounts:
            posts = acc.posts_today if acc.posts_today_date == today_str else 0
            limit = queue.get_account_daily_limit(acc)
            can   = "GO" if queue.account_can_post(acc.platform, acc.username) else "WAIT"
            print(f"  {acc.platform:<12} {acc.username:<20} {acc.state:<10} {posts}/{limit}  [{can}]")

    # Active campaigns
    campaigns = queue.get_active_campaigns()
    if campaigns:
        print(f"\nCAMPAIGNS ({len(campaigns)})")
        for c in campaigns:
            print(f"  {c.name[:40]:<40} CPM ${c.cpm:.2f}")

    print("=" * 44)


def cmd_dashboard(args):
    EarningsTracker().display_dashboard()


def cmd_test(args):
    """Verify config and credentials."""
    print("\nTEST MODE")
    print("=" * 44)

    print("\nConfiguration:")
    print(f"  Daily target:     {config.DAILY_CLIP_TARGET} clips")
    print(f"  Post times:       {config.POSTING_TIMES}")
    print(f"  Platforms:        {config.PLATFORMS}")
    print(f"  Min CPM:          ${config.MIN_CPM}")
    print(f"  Free only:        {config.FREE_ONLY}")
    print(f"  Warmup hours:     {config.WARMUP_HOURS}")

    print("\nCredentials:")
    print(f"  Whop:       {'SET' if config.WHOP_EMAIL else 'MISSING'}")
    print(f"  TikTok:     {'SET' if config.TIKTOK_USERNAME else 'MISSING'}")
    print(f"  Instagram:  {'SET' if config.INSTAGRAM_USERNAME else 'MISSING'}")
    print(f"  YouTube:    {'SET' if config.YOUTUBE_EMAIL else 'MISSING'}")

    print("\nSession:")
    session_ok = config.WHOP_SESSION_FILE.exists()
    print(f"  Whop session:   {'EXISTS' if session_ok else 'MISSING — run --mode login'}")

    print("\nDirectories:")
    for label, path in [
        ("Inbox",  config.CLIPS_INBOX),
        ("Posted", config.CLIPS_POSTED),
        ("Failed", config.CLIPS_FAILED),
        ("Logs",   config.LOGS_DIR),
        ("Data",   config.DATA_DIR),
    ]:
        exists = "OK" if path.exists() else "MISSING"
        print(f"  [{exists}] {label}: {path}")

    print("\nDatabase:")
    queue = QueueManager()
    print(f"  Connected: {config.DB_PATH}")

    print("\n" + "=" * 44)
    print("Run --mode login first if Whop session is missing.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="WhopClipper — automated Whop clipping system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode login              # Save Whop session (run once)
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
        choices=["login", "campaigns", "fetch", "post", "run",
                 "daemon", "status", "dashboard", "test"],
        default="status",
    )
    parser.add_argument("--count", "-c", type=int)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    dispatch = {
        "login":     lambda: asyncio.run(cmd_login(args)),
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
