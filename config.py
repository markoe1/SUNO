"""
WhopClipper Configuration
=========================
All settings for the 24/7 Whop clipping system.
Edit .env file for credentials, this file for behavior.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# PATHS
# =============================================================================
BASE_DIR = Path(__file__).parent
CLIPS_INBOX  = BASE_DIR / "clips" / "inbox"    # Clips ready to post (from AI clipper)
CLIPS_READY  = BASE_DIR / "clips" / "ready"    # Processed
CLIPS_POSTED = BASE_DIR / "clips" / "posted"   # Successfully posted
CLIPS_FAILED = BASE_DIR / "clips" / "failed"   # Failed to post
LOGS_DIR     = BASE_DIR / "logs"
DATA_DIR     = BASE_DIR / "data"

DB_PATH = DATA_DIR / "whop_clips.db"

# =============================================================================
# CREDENTIALS (from .env)
# =============================================================================
# WHOP_API_KEY is loaded from .env and used by services/whop_client.py
WHOP_API_KEY = os.getenv("WHOP_API_KEY", "")

TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "")
TIKTOK_PASSWORD = os.getenv("TIKTOK_PASSWORD", "")

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")

YOUTUBE_EMAIL    = os.getenv("YOUTUBE_EMAIL", "")
YOUTUBE_PASSWORD = os.getenv("YOUTUBE_PASSWORD", "")

FACEBOOK_EMAIL   = os.getenv("FACEBOOK_EMAIL", "")
FACEBOOK_PASSWORD = os.getenv("FACEBOOK_PASSWORD", "")

# =============================================================================
# CAMPAIGN SETTINGS
# =============================================================================
# Campaign filters
MIN_CPM               = 2.50    # Minimum dollars per 1K views
MIN_BUDGET_REMAINING  = 500.0   # Skip campaigns with less budget left
FREE_ONLY             = True    # Only join free campaigns

# =============================================================================
# POSTING SETTINGS
# =============================================================================
HEADLESS = False  # Run browser in headless mode (no GUI) — set to False for debugging/CAPTCHA solving
BROWSER_TIMEOUT = 30  # Seconds to wait for browser actions

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

DAILY_CLIP_TARGET  = 100  # Aggressive: keep posting until inbox empty
CLIPS_PER_SESSION  = 20   # Post more per session
SESSIONS_PER_DAY   = 0    # 0 = continuous (no scheduled breaks)

POSTING_TIMES = []  # DISABLED - always-on mode

POST_DELAY_MIN = 5    # 5 sec minimum between posts (fast)
POST_DELAY_MAX = 15   # 15 sec max (stay under radar)

# Facebook disabled until business page is ready
PLATFORMS = ["tiktok", "instagram", "youtube"]

# =============================================================================
# ACCOUNT WARMUP (DISABLED FOR AGGRESSIVE MODE)
# =============================================================================
# Minimum hours before a NEW account can post anything
WARMUP_HOURS = 0  # DISABLED - post immediately

# Posts-per-day ramp by account age (days)
# Format: (min_age_days, max_posts_per_day)
POSTING_RAMP = [
    (0,  100),   # Day 1+: unlimited
    (4,  100),   # No ramp, go full speed
    (14, 100),
    (30, 100),
]

# Minimum gap between posts on same account (minutes)
MIN_POST_GAP_MINUTES = 2  # 2 minutes (aggressive)

# =============================================================================
# CONTENT SETTINGS
# =============================================================================
BASE_HASHTAGS = ["#fyp", "#foryou", "#viral", "#trending"]

NICHE_HASHTAGS = {
    "general": ["#entertainment", "#mustwatch", "#mindblown", "#epic"],
}

CAPTION_HOOKS = [
    "This part hit different",
    "Wait for it...",
    "Nobody talks about this moment",
    "The craziest part of the video",
    "I had to clip this",
    "This deserves more attention",
    "Underrated moment right here",
    "The algorithm needs to see this",
]

CTAS = [
    "Follow for more clips!",
    "Save this",
    "Share with someone who needs to see this",
    "Comment if you agree",
    "Part 2? Let me know!",
]

# =============================================================================
# DAEMON SETTINGS
# =============================================================================
WHOP_CHECK_INTERVAL   = 60     # Minutes between campaign refresh
HEALTH_CHECK_INTERVAL = 5      # Minutes between health checks
MAX_POST_RETRIES      = 3
RATE_LIMIT_COOLDOWN   = 15     # Minutes to wait after a rate limit

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL       = "INFO"
LOG_FORMAT      = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# =============================================================================
# EARNINGS
# =============================================================================
CPM_RATE              = 3.0
MIN_VIEWS_FOR_PAYOUT  = 5000
DAILY_EARNINGS_GOAL   = 100.0
MONTHLY_EARNINGS_GOAL = 3000.0

# =============================================================================
# STARTUP VALIDATION
# =============================================================================
def validate_configuration():
    """Validate that all required configuration is present."""
    required_keys = {
        'WHOP_API_KEY': WHOP_API_KEY,
        'TIKTOK_USERNAME': TIKTOK_USERNAME,
        'TIKTOK_PASSWORD': TIKTOK_PASSWORD,
        'INSTAGRAM_USERNAME': INSTAGRAM_USERNAME,
        'INSTAGRAM_PASSWORD': INSTAGRAM_PASSWORD,
        'YOUTUBE_EMAIL': YOUTUBE_EMAIL,
        'YOUTUBE_PASSWORD': YOUTUBE_PASSWORD,
    }
    
    missing = [key for key, value in required_keys.items() if not value or not str(value).strip()]
    if missing:
        raise RuntimeError(
            f"Missing required credentials in environment or config.py: {', '.join(missing)}. "
            f"Set these environment variables or update config.py before starting the daemon."
        )
    
    # Additional validation
    if not isinstance(CLIPS_PER_SESSION, int) or CLIPS_PER_SESSION < 1:
        raise ValueError(f"CLIPS_PER_SESSION must be a positive integer, got {CLIPS_PER_SESSION}")
    
    if not isinstance(WHOP_CHECK_INTERVAL, int) or WHOP_CHECK_INTERVAL < 1:
        raise ValueError(f"WHOP_CHECK_INTERVAL must be a positive integer, got {WHOP_CHECK_INTERVAL}")

# Call validation if this module is imported at startup
if __name__ != "__main__":
    # Called when daemon imports this module
    validate_configuration()
