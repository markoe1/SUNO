"""
VyroClipper Configuration
=========================
All settings for the 24/7 Vyro clipping system.
Edit .env file for credentials, this file for behavior.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# PATHS
# =============================================================================
BASE_DIR = Path(__file__).parent
CLIPS_INBOX = BASE_DIR / "clips" / "inbox"      # Downloaded from Vyro
CLIPS_READY = BASE_DIR / "clips" / "ready"      # Processed, ready to post
CLIPS_POSTED = BASE_DIR / "clips" / "posted"    # Successfully posted
CLIPS_FAILED = BASE_DIR / "clips" / "failed"    # Failed to post
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# Database
DB_PATH = DATA_DIR / "vyro_clips.db"

# =============================================================================
# CREDENTIALS (from .env)
# =============================================================================
VYRO_EMAIL = os.getenv("VYRO_EMAIL", "")
VYRO_PASSWORD = os.getenv("VYRO_PASSWORD", "")

# Social media credentials (for browser automation)
TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "")
TIKTOK_PASSWORD = os.getenv("TIKTOK_PASSWORD", "")

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")

YOUTUBE_EMAIL = os.getenv("YOUTUBE_EMAIL", "")
YOUTUBE_PASSWORD = os.getenv("YOUTUBE_PASSWORD", "")

FACEBOOK_EMAIL = os.getenv("FACEBOOK_EMAIL", "")
FACEBOOK_PASSWORD = os.getenv("FACEBOOK_PASSWORD", "")

# =============================================================================
# VYRO SETTINGS
# =============================================================================
VYRO_BASE_URL = "https://app.vyro.com"
VYRO_LOGIN_URL = f"{VYRO_BASE_URL}/login"
VYRO_DASHBOARD_URL = f"{VYRO_BASE_URL}"
VYRO_CAMPAIGNS_URL = f"{VYRO_BASE_URL}/campaigns"

# Campaigns to target (update with active campaign IDs/names)
TARGET_CAMPAIGNS = [
    "beast-games",
    "mrbeast",
    "mark-rober",
]

# Minimum CPM to consider a campaign ($3 = 3.0)
MIN_CPM = 2.5

# =============================================================================
# POSTING SETTINGS
# =============================================================================
# Target clips per day
DAILY_CLIP_TARGET = 15

# Clips per posting session (spread throughout day)
CLIPS_PER_SESSION = 5

# Posting sessions per day (3 sessions × 5 clips = 15 clips)
SESSIONS_PER_DAY = 3

# Peak posting times (24h format, local time)
POSTING_TIMES = [
    "08:00",  # Morning - catch early scrollers
    "12:30",  # Lunch break - high engagement
    "19:00",  # Evening - prime time
]

# Delay between posts (seconds) - avoid rate limits
POST_DELAY_MIN = 30
POST_DELAY_MAX = 90

# Platforms to post to
# Facebook disabled until business page is ready
PLATFORMS = ["tiktok", "instagram", "youtube"]

# =============================================================================
# CONTENT SETTINGS
# =============================================================================
# Hashtag sets (rotated to avoid spam detection)
BASE_HASHTAGS = [
    "#fyp", "#foryou", "#viral", "#trending"
]

NICHE_HASHTAGS = {
    "mrbeast": ["#mrbeast", "#mrbeastgaming", "#beastreacts", "#beastgames"],
    "mark-rober": ["#markrober", "#science", "#engineering", "#experiment"],
    "general": ["#entertainment", "#mustwatch", "#mindblown", "#epic"],
}

# Caption hooks (rotated)
CAPTION_HOOKS = [
    "This part hit different 🔥",
    "Wait for it... 😱",
    "Nobody talks about this moment",
    "The craziest part of the video",
    "I had to clip this 🎬",
    "This deserves more attention",
    "Underrated moment right here",
    "The algorithm needs to see this",
]

# Call to actions
CTAS = [
    "Follow for more clips!",
    "Save this 🔖",
    "Share with someone who needs to see this",
    "Comment if you agree 👇",
    "Part 2? Let me know!",
]

# =============================================================================
# DAEMON SETTINGS (24/7 operation)
# =============================================================================
# Check for new Vyro clips every N minutes
VYRO_CHECK_INTERVAL = 30

# Health check interval (minutes)
HEALTH_CHECK_INTERVAL = 5

# Max retries for failed posts
MAX_POST_RETRIES = 3

# Cooldown after rate limit (minutes)
RATE_LIMIT_COOLDOWN = 15

# =============================================================================
# BROWSER SETTINGS
# =============================================================================
# Headless mode (True for server, False for debugging)
HEADLESS = False  # Set to False to see browser and debug login

# Browser timeout (seconds)
BROWSER_TIMEOUT = 60

# Download timeout (seconds)
DOWNLOAD_TIMEOUT = 120

# User agent rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# =============================================================================
# EARNINGS TRACKING
# =============================================================================
# CPM rate (dollars per 1000 views)
CPM_RATE = 3.0

# Minimum views to qualify for payout
MIN_VIEWS_FOR_PAYOUT = 5000

# Daily earnings goal
DAILY_EARNINGS_GOAL = 100.0

# Monthly earnings goal
MONTHLY_EARNINGS_GOAL = 3000.0
