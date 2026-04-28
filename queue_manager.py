"""
Queue Manager
=============
SQLite-based clip + account tracking.

Tables:
  clips        — every clip: status, campaign, platform URLs, views, earnings
  campaigns    — Whop campaigns: CPM, budget, drive/yt sources
  accounts     — social accounts: warmup state, daily post count
  daily_stats  — aggregated daily numbers
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from enum import Enum

import config

logger = logging.getLogger(__name__)


# ─── Enums ────────────────────────────────────────────────────────────────────

class ClipStatus(Enum):
    PENDING   = "pending"     # In inbox, not yet posted
    POSTING   = "posting"     # Currently being posted
    POSTED    = "posted"      # Posted to all platforms
    PARTIAL   = "partial"     # Posted to some platforms
    FAILED    = "failed"      # Failed
    SUBMITTED = "submitted"   # URLs submitted to Whop


class AccountState(Enum):
    NEW     = "new"       # Just created, in warmup hold
    WARMING = "warming"   # Past 36hr hold, ramping up
    ACTIVE  = "active"    # Full posting speed
    BLOCKED = "blocked"   # Rate-limited or flagged


# Valid platform identifiers
VALID_PLATFORMS = {"tiktok", "instagram", "youtube", "facebook", "twitter"}

# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class Clip:
    id: Optional[int]    = None
    whop_clip_id: str    = ""
    campaign_name: str   = ""
    campaign_id: str     = ""
    filename: str        = ""
    filepath: str        = ""
    caption: str         = ""
    hashtags: str        = ""
    status: str          = ClipStatus.PENDING.value

    # Creator intent & campaign requirements (PHASE 5)
    creator_name: str    = ""        # Original creator/channel name
    source_platform: str = ""        # youtube, tiktok, instagram, twitter
    source_url: str      = ""        # Link to original content
    clip_duration: int   = 0         # Duration in seconds

    # Platform URLs (posting results)
    tiktok_url: str      = ""
    instagram_url: str   = ""
    youtube_url: str     = ""

    views_total: int     = 0
    earnings: float      = 0.0

    downloaded_at: str   = ""
    posted_at: str       = ""
    submitted_at: str    = ""

    retry_count: int     = 0
    last_error: str      = ""

    created_at: str      = ""
    updated_at: str      = ""


@dataclass
class Campaign:
    id: Optional[int]       = None
    whop_id: str            = ""
    name: str               = ""
    cpm: float              = 0.0
    budget_remaining: float = 0.0
    is_free: bool           = True
    drive_url: str          = ""
    youtube_url: str        = ""
    allowed_platforms: str  = "tiktok,instagram,youtube"
    active: bool            = True
    discovered_at: str      = ""
    last_checked: str       = ""

    # Creator intent & content requirements (PHASE 5)
    content_type: str       = "general"         # music, comedy, news, etc
    source_types: str       = "youtube"         # Comma-separated: youtube,tiktok,etc
    min_duration: int       = 15                # Minimum clip duration (seconds)
    max_duration: int       = 60                # Maximum clip duration (seconds)
    creator_whitelist: str  = ""                # Comma-separated creator names
    creator_blacklist: str  = ""                # Comma-separated creator names to block
    daily_clip_limit: int   = 100               # Max clips per day


@dataclass
class Account:
    id: Optional[int]    = None
    platform: str        = ""
    username: str        = ""
    state: str           = AccountState.NEW.value
    created_at: str      = ""
    first_posted_at: str = ""
    last_posted_at: str  = ""
    posts_today: int     = 0
    posts_today_date: str = ""
    total_posts: int     = 0
    notes: str           = ""


@dataclass
class Creator:
    """Creator/channel profile for source content approval."""
    id: Optional[int]        = None
    name: str                = ""                  # Creator/channel name
    platform: str            = ""                  # youtube, tiktok, instagram, twitter
    is_approved: bool        = False               # Is this creator approved?
    verification_status: str = "unverified"        # unverified, pending, verified, blocked
    approval_reason: str     = ""                  # Why approved/blocked
    clips_extracted: int     = 0                   # Number of clips extracted from this creator
    clips_posted: int        = 0                   # Number of clips successfully posted
    views_generated: int     = 0                   # Total views from clips from this creator
    earnings_generated: float = 0.0                # Total earnings from clips from this creator
    discovered_at: str       = ""                  # When first discovered
    approved_at: str         = ""                  # When approved
    created_at: str          = ""
    updated_at: str          = ""


# ─── QueueManager ─────────────────────────────────────────────────────────────

class QueueManager:
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or config.DB_PATH
        self._init_db()

    def _init_db(self):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            # Create tables
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS clips (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    whop_clip_id     TEXT UNIQUE,
                    campaign_name    TEXT,
                    campaign_id      TEXT DEFAULT '',
                    filename         TEXT,
                    filepath         TEXT,
                    caption          TEXT,
                    hashtags         TEXT,
                    status           TEXT DEFAULT 'pending',

                    creator_name     TEXT DEFAULT '',
                    source_platform  TEXT DEFAULT '',
                    source_url       TEXT DEFAULT '',
                    clip_duration    INTEGER DEFAULT 0,

                    tiktok_url       TEXT DEFAULT '',
                    instagram_url    TEXT DEFAULT '',
                    youtube_url      TEXT DEFAULT '',

                    views_total      INTEGER DEFAULT 0,
                    earnings         REAL DEFAULT 0.0,

                    downloaded_at    TEXT,
                    posted_at        TEXT,
                    submitted_at     TEXT,

                    retry_count      INTEGER DEFAULT 0,
                    last_error       TEXT DEFAULT '',

                    created_at       TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at       TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS campaigns (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    whop_id           TEXT UNIQUE,
                    name              TEXT,
                    cpm               REAL DEFAULT 0.0,
                    budget_remaining  REAL DEFAULT 0.0,
                    is_free           INTEGER DEFAULT 1,
                    drive_url         TEXT DEFAULT '',
                    youtube_url       TEXT DEFAULT '',
                    allowed_platforms TEXT DEFAULT 'tiktok,instagram,youtube',
                    active            INTEGER DEFAULT 1,
                    discovered_at     TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_checked      TEXT DEFAULT CURRENT_TIMESTAMP,

                    content_type      TEXT DEFAULT 'general',
                    source_types      TEXT DEFAULT 'youtube',
                    min_duration      INTEGER DEFAULT 15,
                    max_duration      INTEGER DEFAULT 60,
                    creator_whitelist TEXT DEFAULT '',
                    creator_blacklist TEXT DEFAULT '',
                    daily_clip_limit  INTEGER DEFAULT 100
                );

                CREATE TABLE IF NOT EXISTS accounts (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform         TEXT,
                    username         TEXT,
                    state            TEXT DEFAULT 'new',
                    created_at       TEXT DEFAULT CURRENT_TIMESTAMP,
                    first_posted_at  TEXT DEFAULT '',
                    last_posted_at   TEXT DEFAULT '',
                    posts_today      INTEGER DEFAULT 0,
                    posts_today_date TEXT DEFAULT '',
                    total_posts      INTEGER DEFAULT 0,
                    notes            TEXT DEFAULT '',
                    UNIQUE(platform, username)
                );

                CREATE TABLE IF NOT EXISTS daily_stats (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    date            TEXT UNIQUE,
                    clips_downloaded INTEGER DEFAULT 0,
                    clips_posted    INTEGER DEFAULT 0,
                    total_views     INTEGER DEFAULT 0,
                    total_earnings  REAL DEFAULT 0.0,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS creators (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    name                TEXT NOT NULL,
                    platform            TEXT NOT NULL,
                    is_approved         INTEGER DEFAULT 0,
                    verification_status TEXT DEFAULT 'unverified',
                    approval_reason     TEXT DEFAULT '',
                    clips_extracted     INTEGER DEFAULT 0,
                    clips_posted        INTEGER DEFAULT 0,
                    views_generated     INTEGER DEFAULT 0,
                    earnings_generated  REAL DEFAULT 0.0,
                    discovered_at       TEXT DEFAULT CURRENT_TIMESTAMP,
                    approved_at         TEXT DEFAULT '',
                    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, platform)
                );

                CREATE INDEX IF NOT EXISTS idx_clips_status   ON clips(status);
                CREATE INDEX IF NOT EXISTS idx_clips_campaign ON clips(campaign_name);
                CREATE INDEX IF NOT EXISTS idx_accounts_state ON accounts(platform, state);
                CREATE INDEX IF NOT EXISTS idx_creators_approved ON creators(is_approved);
                CREATE INDEX IF NOT EXISTS idx_creators_platform ON creators(platform, is_approved);
            """)
            conn.commit()

        # Run schema migrations
        self._migrate_schema()

    def _migrate_schema(self):
        """Apply schema migrations to add missing columns."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check clips table columns
            cursor.execute("PRAGMA table_info(clips)")
            clips_columns = {row[1] for row in cursor.fetchall()}

            # Add missing columns to clips table
            clips_missing = [
                ('creator_name', 'TEXT DEFAULT \'\''),
                ('source_platform', 'TEXT DEFAULT \'\''),
                ('source_url', 'TEXT DEFAULT \'\''),
                ('clip_duration', 'INTEGER DEFAULT 0'),
            ]

            for col_name, col_def in clips_missing:
                if col_name not in clips_columns:
                    try:
                        conn.execute(f"ALTER TABLE clips ADD COLUMN {col_name} {col_def}")
                        logger.info(f"Added column to clips: {col_name}")
                    except Exception as e:
                        logger.warning(f"Could not add column {col_name}: {e}")

            # Check campaigns table columns
            cursor.execute("PRAGMA table_info(campaigns)")
            campaign_columns = {row[1] for row in cursor.fetchall()}

            # Add missing columns to campaigns table
            campaign_missing = [
                ('content_type', 'TEXT DEFAULT \'general\''),
                ('source_types', 'TEXT DEFAULT \'youtube\''),
                ('min_duration', 'INTEGER DEFAULT 15'),
                ('max_duration', 'INTEGER DEFAULT 60'),
                ('creator_whitelist', 'TEXT DEFAULT \'\''),
                ('creator_blacklist', 'TEXT DEFAULT \'\''),
                ('daily_clip_limit', 'INTEGER DEFAULT 100'),
            ]

            for col_name, col_def in campaign_missing:
                if col_name not in campaign_columns:
                    try:
                        conn.execute(f"ALTER TABLE campaigns ADD COLUMN {col_name} {col_def}")
                        logger.info(f"Added column to campaigns: {col_name}")
                    except Exception as e:
                        logger.warning(f"Could not add column {col_name}: {e}")

            conn.commit()

    # ── Clips ──────────────────────────────────────────────────────────────────

    def add_clip(self, clip: Clip) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO clips (
                    whop_clip_id, campaign_name, campaign_id,
                    filename, filepath, caption, hashtags, status,
                    creator_name, source_platform, source_url, clip_duration,
                    downloaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                clip.whop_clip_id, clip.campaign_name, clip.campaign_id,
                clip.filename, clip.filepath, clip.caption, clip.hashtags,
                clip.status, clip.creator_name, clip.source_platform,
                clip.source_url, clip.clip_duration, datetime.now().isoformat()
            ))
            conn.commit()
            return cursor.lastrowid

    def get_pending_clips(self, limit: int = 5) -> List[Clip]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM clips
                WHERE status IN ('pending', 'partial')
                  AND retry_count < ?
                ORDER BY downloaded_at ASC
                LIMIT ?
            """, (config.MAX_POST_RETRIES, limit)).fetchall()
            return [Clip(**dict(r)) for r in rows]

    def clip_exists(self, whop_clip_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT 1 FROM clips WHERE whop_clip_id = ?", (whop_clip_id,)
            ).fetchone() is not None

    def update_clip_status(self, clip_id: int, status: ClipStatus,
                           tiktok_url: str = None, instagram_url: str = None,
                           youtube_url: str = None, error: str = None):
        with sqlite3.connect(self.db_path) as conn:
            updates = ["status = ?", "updated_at = ?"]
            values  = [status.value, datetime.now().isoformat()]

            if tiktok_url:
                updates.append("tiktok_url = ?");   values.append(tiktok_url)
            if instagram_url:
                updates.append("instagram_url = ?"); values.append(instagram_url)
            if youtube_url:
                updates.append("youtube_url = ?");   values.append(youtube_url)
            if error:
                updates.append("last_error = ?");    values.append(error)
                updates.append("retry_count = retry_count + 1")
            if status == ClipStatus.POSTED or status == ClipStatus.PARTIAL:
                updates.append("posted_at = ?");     values.append(datetime.now().isoformat())
            if status == ClipStatus.SUBMITTED:
                updates.append("submitted_at = ?");  values.append(datetime.now().isoformat())

            values.append(clip_id)
            conn.execute(
                f"UPDATE clips SET {', '.join(updates)} WHERE id = ?", values
            )
            conn.commit()

    def get_clips_needing_submission(self) -> List[Clip]:
        """Clips posted but not yet submitted to Whop (includes PARTIAL for MVP)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM clips
                WHERE status IN ('posted', 'partial')
                ORDER BY posted_at ASC
            """).fetchall()
            return [Clip(**dict(r)) for r in rows]

    def get_posted_clips(self, since_hours: int = 24) -> List[Clip]:
        """Get clips posted/submitted/partial within the last N hours."""
        cutoff_time = (datetime.now() - timedelta(hours=since_hours)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM clips
                WHERE status IN ('posted', 'submitted', 'partial')
                  AND posted_at >= ?
                ORDER BY posted_at DESC
            """, (cutoff_time,)).fetchall()
            return [Clip(**dict(r)) for r in rows]

    def update_views(self, clip_id: int, views: int):
        earnings = (views / 1000) * config.CPM_RATE
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE clips SET views_total = ?, earnings = ?, updated_at = ?
                WHERE id = ?
            """, (views, earnings, datetime.now().isoformat(), clip_id))
            conn.commit()

    def get_daily_stats(self, date: str = None) -> Dict:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        day_start = f"{date}T00:00:00"
        day_end   = f"{date}T23:59:59"
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as clips_downloaded,
                    SUM(CASE WHEN status IN ('posted','submitted','partial') THEN 1 ELSE 0 END) as clips_posted,
                    SUM(views_total) as total_views,
                    SUM(earnings)    as total_earnings
                FROM clips
                WHERE downloaded_at BETWEEN ? AND ?
            """, (day_start, day_end)).fetchone()
            return {
                "date": date,
                "clips_downloaded": row[0] or 0,
                "clips_posted":     row[1] or 0,
                "total_views":      row[2] or 0,
                "total_earnings":   row[3] or 0.0,
            }

    def get_all_time_stats(self) -> Dict:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total_clips,
                    SUM(CASE WHEN status IN ('posted','submitted','partial') THEN 1 ELSE 0 END) as total_posted,
                    SUM(views_total) as total_views,
                    SUM(earnings)    as total_earnings
                FROM clips
            """).fetchone()
            return {
                "total_clips":    row[0] or 0,
                "total_posted":   row[1] or 0,
                "total_views":    row[2] or 0,
                "total_earnings": row[3] or 0.0,
            }

    # ── Campaigns ──────────────────────────────────────────────────────────────

    def upsert_campaign(self, c: Campaign):
        """Insert or update campaign with all requirement fields."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO campaigns (
                    whop_id, name, cpm, budget_remaining, is_free,
                    drive_url, youtube_url, allowed_platforms, active,
                    discovered_at, last_checked,
                    content_type, source_types, min_duration, max_duration,
                    creator_whitelist, creator_blacklist, daily_clip_limit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(whop_id) DO UPDATE SET
                    name               = excluded.name,
                    cpm                = excluded.cpm,
                    budget_remaining   = excluded.budget_remaining,
                    is_free            = excluded.is_free,
                    drive_url          = excluded.drive_url,
                    youtube_url        = excluded.youtube_url,
                    allowed_platforms  = excluded.allowed_platforms,
                    active             = excluded.available,
                    last_checked       = excluded.last_checked,
                    content_type       = excluded.content_type,
                    source_types       = excluded.source_types,
                    min_duration       = excluded.min_duration,
                    max_duration       = excluded.max_duration,
                    creator_whitelist  = excluded.creator_whitelist,
                    creator_blacklist  = excluded.creator_blacklist,
                    daily_clip_limit   = excluded.daily_clip_limit
            """, (
                c.whop_id, c.name, c.cpm, c.budget_remaining, int(c.is_free),
                c.drive_url, c.youtube_url, c.allowed_platforms, int(c.available),
                c.discovered_at or datetime.now().isoformat(),
                datetime.now().isoformat(),
                c.content_type, c.source_types, c.min_duration, c.max_duration,
                c.creator_whitelist, c.creator_blacklist, c.daily_clip_limit
            ))
            conn.commit()

    def get_active_campaigns(self) -> List[Campaign]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM campaigns WHERE active = 1 ORDER BY cpm DESC"
            ).fetchall()
            return [Campaign(**{k: row[k] for k in row.keys()}) for row in rows]

    # ── Accounts ───────────────────────────────────────────────────────────────

    def upsert_account(self, acc: Account):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO accounts (platform, username, state, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(platform, username) DO UPDATE SET
                    state = excluded.state
            """, (acc.platform, acc.username, acc.state,
                  acc.created_at or datetime.now().isoformat()))
            conn.commit()

    def get_account(self, platform: str, username: str) -> Optional[Account]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM accounts WHERE platform = ? AND username = ?",
                (platform, username)
            ).fetchone()
            return Account(**dict(row)) if row else None

    def get_all_accounts(self, platform: str = None) -> List[Account]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if platform:
                rows = conn.execute(
                    "SELECT * FROM accounts WHERE platform = ?", (platform,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM accounts").fetchall()
            return [Account(**dict(r)) for r in rows]

    def update_account_state(self, platform: str, username: str, state: AccountState):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE accounts SET state = ? WHERE platform = ? AND username = ?",
                (state.value, platform, username)
            )
            conn.commit()

    def record_account_post(self, platform: str, username: str):
        """Increment post counters and update timestamps after a successful post."""
        today = datetime.now().strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE accounts SET
                    last_posted_at   = ?,
                    first_posted_at  = CASE WHEN first_posted_at = '' THEN ? ELSE first_posted_at END,
                    posts_today      = CASE WHEN posts_today_date = ? THEN posts_today + 1 ELSE 1 END,
                    posts_today_date = ?,
                    total_posts      = total_posts + 1
                WHERE platform = ? AND username = ?
            """, (
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                today, today,
                platform, username
            ))
            conn.commit()

    def get_account_daily_limit(self, acc: Account) -> int:
        """Return how many posts this account is allowed today based on ramp."""
        if acc.state in (AccountState.NEW.value, AccountState.BLOCKED.value):
            return 0
        if not acc.first_posted_at:
            age_days = 0
        else:
            first = datetime.fromisoformat(acc.first_posted_at)
            age_days = (datetime.now() - first).days

        limit = config.POSTING_RAMP[0][1]
        for min_age, max_posts in config.POSTING_RAMP:
            if age_days >= min_age:
                limit = max_posts
        return limit

    def _try_promote_account(self, platform: str, username: str, from_state: str, to_state: str) -> bool:
        """
        Atomically promote account from one state to another.
        Returns True if promotion succeeded, False if account was already in different state.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE accounts 
                SET state = ? 
                WHERE platform = ? AND username = ? AND state = ?
            """, (to_state, platform, username, from_state))
            conn.commit()
            return cursor.rowcount > 0

    def account_can_post(self, platform: str, username: str) -> bool:
        """
        Returns True if account is warmed up, within daily limit,
        and past the minimum gap since last post.

        Args:
            platform: Social media platform (tiktok, instagram, youtube)
            username: Account username

        Returns:
            bool: True if account can post now, False otherwise
        """
        acc = self.get_account(platform, username)
        if not acc:
            return False

        # Must be WARMING or ACTIVE
        if acc.state == AccountState.NEW.value:
            if acc.created_at:
                created = datetime.fromisoformat(acc.created_at)
                hours_old = (datetime.now() - created).total_seconds() / 3600
                if hours_old < config.WARMUP_HOURS:
                    return False
                # Atomically promote to WARMING (prevents race condition)
                self._try_promote_account(platform, username, AccountState.NEW.value, AccountState.WARMING.value)
                # Re-fetch to get updated state
                acc = self.get_account(platform, username)
                if not acc:
                    return False
            else:
                return False

        if acc.state == AccountState.BLOCKED.value:
            return False

        # Daily limit check
        today = datetime.now().strftime("%Y-%m-%d")
        posts_today = acc.posts_today if acc.posts_today_date == today else 0
        if posts_today >= self.get_account_daily_limit(acc):
            return False

        # Minimum gap check
        if acc.last_posted_at:
            last = datetime.fromisoformat(acc.last_posted_at)
            gap_minutes = (datetime.now() - last).total_seconds() / 60
            if gap_minutes < config.MIN_POST_GAP_MINUTES:
                return False

        return True

    # ── Creators ───────────────────────────────────────────────────────────────

    def upsert_creator(self, creator: Creator) -> int:
        """Add or update a creator in the registry."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO creators (
                    name, platform, is_approved, verification_status,
                    approval_reason, clips_extracted, clips_posted,
                    views_generated, earnings_generated, discovered_at, approved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name, platform) DO UPDATE SET
                    is_approved         = excluded.is_approved,
                    verification_status = excluded.verification_status,
                    approval_reason     = excluded.approval_reason,
                    clips_extracted     = excluded.clips_extracted,
                    clips_posted        = excluded.clips_posted,
                    views_generated     = excluded.views_generated,
                    earnings_generated  = excluded.earnings_generated,
                    approved_at         = excluded.approved_at,
                    updated_at          = CURRENT_TIMESTAMP
            """, (
                creator.name, creator.platform, int(creator.is_approved),
                creator.verification_status, creator.approval_reason,
                creator.clips_extracted, creator.clips_posted,
                creator.views_generated, creator.earnings_generated,
                creator.discovered_at or datetime.now().isoformat(),
                creator.approved_at or ""
            ))
            conn.commit()
            return cursor.lastrowid

    def get_creator(self, name: str, platform: str) -> Optional[Creator]:
        """Get creator profile by name and platform."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM creators WHERE name = ? AND platform = ?",
                (name, platform)
            ).fetchone()
            return Creator(**dict(row)) if row else None

    def get_approved_creators(self, platform: str = None) -> List[Creator]:
        """Get all approved creators, optionally filtered by platform."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if platform:
                rows = conn.execute(
                    "SELECT * FROM creators WHERE is_approved = 1 AND platform = ? ORDER BY name",
                    (platform,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM creators WHERE is_approved = 1 ORDER BY platform, name"
                ).fetchall()
            return [Creator(**dict(r)) for r in rows]

    def get_blocked_creators(self, platform: str = None) -> List[Creator]:
        """Get all blocked creators, optionally filtered by platform."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if platform:
                rows = conn.execute(
                    "SELECT * FROM creators WHERE verification_status = 'blocked' AND platform = ? ORDER BY name",
                    (platform,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM creators WHERE verification_status = 'blocked' ORDER BY platform, name"
                ).fetchall()
            return [Creator(**dict(r)) for r in rows]

    def approve_creator(self, name: str, platform: str, reason: str = "") -> bool:
        """Approve a creator."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE creators SET
                    is_approved = 1,
                    verification_status = 'verified',
                    approval_reason = ?,
                    approved_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE name = ? AND platform = ?
            """, (reason, datetime.now().isoformat(), name, platform))
            conn.commit()
            return conn.total_changes > 0

    def block_creator(self, name: str, platform: str, reason: str = "") -> bool:
        """Block a creator."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE creators SET
                    is_approved = 0,
                    verification_status = 'blocked',
                    approval_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE name = ? AND platform = ?
            """, (reason, name, platform))
            conn.commit()
            return conn.total_changes > 0

    def is_creator_approved(self, name: str, platform: str) -> bool:
        """Check if creator is approved."""
        creator = self.get_creator(name, platform)
        return creator is not None and creator.is_approved

    def is_creator_blocked(self, name: str, platform: str) -> bool:
        """Check if creator is blocked."""
        creator = self.get_creator(name, platform)
        return creator is not None and creator.verification_status == "blocked"

    def update_creator_stats(self, name: str, platform: str,
                            clips_extracted: int = 0, clips_posted: int = 0,
                            views: int = 0, earnings: float = 0.0):
        """Update creator statistics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE creators SET
                    clips_extracted = clips_extracted + ?,
                    clips_posted    = clips_posted + ?,
                    views_generated = views_generated + ?,
                    earnings_generated = earnings_generated + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE name = ? AND platform = ?
            """, (clips_extracted, clips_posted, views, earnings, name, platform))
            conn.commit()


# Convenience instance
queue = QueueManager()
