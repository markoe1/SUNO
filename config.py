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
HEADLESS = True  # Run browser in headless mode (no GUI)
BROWSER_TIMEOUT = 30  # Seconds to wait for browser actions

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

DAILY_CLIP_TARGET  = 15
CLIPS_PER_SESSION  = 5
SESSIONS_PER_DAY   = 3

POSTING_TIMES = [
    "08:00",
    "12:30",
    "19:00",
]

POST_DELAY_MIN = 30
POST_DELAY_MAX = 90

# Facebook disabled until business page is ready
PLATFORMS = ["tiktok", "instagram", "youtube"]

# =============================================================================
# ACCOUNT WARMUP
# =============================================================================
# Minimum hours before a NEW account can post anything
WARMUP_HOURS = 36

# Posts-per-day ramp by account age (days)
# Format: (min_age_days, max_posts_per_day)
POSTING_RAMP = [
    (0,  1),   # Day 1–3: 1/day
    (4,  3),   # Day 4–7: 3/day
    (14, 6),   # Day 14+: 6/day
    (30, 10),  # Day 30+: 10/day
]

# Minimum gap between posts on same account (minutes)
MIN_POST_GAP_MINUTES = 360  # 6 hours

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
