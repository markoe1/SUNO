"""
Queue Manager
=============
SQLite-based clip tracking system.
Tracks: download status, post status per platform, view counts, earnings.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
from enum import Enum

import config


class ClipStatus(Enum):
    PENDING = "pending"           # Downloaded, not yet posted
    POSTING = "posting"           # Currently being posted
    POSTED = "posted"             # Successfully posted to all platforms
    PARTIAL = "partial"           # Posted to some platforms
    FAILED = "failed"             # Failed to post
    SUBMITTED = "submitted"       # URLs submitted to Vyro


@dataclass
class Clip:
    id: Optional[int] = None
    vyro_clip_id: str = ""
    campaign_name: str = ""
    filename: str = ""
    filepath: str = ""
    caption: str = ""
    hashtags: str = ""
    status: str = ClipStatus.PENDING.value
    
    # Platform post URLs
    tiktok_url: str = ""
    instagram_url: str = ""
    youtube_url: str = ""
    
    # Tracking
    views_total: int = 0
    earnings: float = 0.0
    
    # Timestamps
    downloaded_at: str = ""
    posted_at: str = ""
    submitted_at: str = ""
    
    # Retry tracking
    retry_count: int = 0
    last_error: str = ""


class QueueManager:
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or config.DB_PATH
        self._init_db()
    
    def _init_db(self):
        """Initialize database with schema."""
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vyro_clip_id TEXT UNIQUE,
                    campaign_name TEXT,
                    filename TEXT,
                    filepath TEXT,
                    caption TEXT,
                    hashtags TEXT,
                    status TEXT DEFAULT 'pending',
                    
                    tiktok_url TEXT DEFAULT '',
                    instagram_url TEXT DEFAULT '',
                    youtube_url TEXT DEFAULT '',
                    
                    views_total INTEGER DEFAULT 0,
                    earnings REAL DEFAULT 0.0,
                    
                    downloaded_at TEXT,
                    posted_at TEXT,
                    submitted_at TEXT,
                    
                    retry_count INTEGER DEFAULT 0,
                    last_error TEXT DEFAULT '',
                    
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE,
                    clips_downloaded INTEGER DEFAULT 0,
                    clips_posted INTEGER DEFAULT 0,
                    total_views INTEGER DEFAULT 0,
                    total_earnings REAL DEFAULT 0.0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_clips_status ON clips(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_clips_campaign ON clips(campaign_name)
            """)
            
            conn.commit()
    
    def add_clip(self, clip: Clip) -> int:
        """Add a new clip to the queue."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO clips (
                    vyro_clip_id, campaign_name, filename, filepath,
                    caption, hashtags, status, downloaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                clip.vyro_clip_id, clip.campaign_name, clip.filename, clip.filepath,
                clip.caption, clip.hashtags, clip.status, 
                datetime.now().isoformat()
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_pending_clips(self, limit: int = 5) -> List[Clip]:
        """Get clips ready to be posted."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM clips 
                WHERE status IN ('pending', 'partial')
                AND retry_count < ?
                ORDER BY downloaded_at ASC
                LIMIT ?
            """, (config.MAX_POST_RETRIES, limit))
            
            rows = cursor.fetchall()
            return [Clip(**dict(row)) for row in rows]
    
    def update_clip_status(self, clip_id: int, status: ClipStatus, 
                          tiktok_url: str = None, instagram_url: str = None,
                          youtube_url: str = None, error: str = None):
        """Update clip posting status."""
        with sqlite3.connect(self.db_path) as conn:
            updates = ["status = ?", "updated_at = ?"]
            values = [status.value, datetime.now().isoformat()]
            
            if tiktok_url:
                updates.append("tiktok_url = ?")
                values.append(tiktok_url)
            if instagram_url:
                updates.append("instagram_url = ?")
                values.append(instagram_url)
            if youtube_url:
                updates.append("youtube_url = ?")
                values.append(youtube_url)
            if error:
                updates.append("last_error = ?")
                updates.append("retry_count = retry_count + 1")
                values.append(error)
            if status == ClipStatus.POSTED:
                updates.append("posted_at = ?")
                values.append(datetime.now().isoformat())
            if status == ClipStatus.SUBMITTED:
                updates.append("submitted_at = ?")
                values.append(datetime.now().isoformat())
            
            values.append(clip_id)
            
            conn.execute(f"""
                UPDATE clips SET {', '.join(updates)}
                WHERE id = ?
            """, values)
            conn.commit()
    
    def update_views(self, clip_id: int, views: int):
        """Update view count and calculate earnings."""
        earnings = (views / 1000) * config.CPM_RATE
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE clips 
                SET views_total = ?, earnings = ?, updated_at = ?
                WHERE id = ?
            """, (views, earnings, datetime.now().isoformat(), clip_id))
            conn.commit()
    
    def get_posted_clips(self, since_hours: int = 24) -> List[Clip]:
        """Get clips posted in the last N hours."""
        cutoff = (datetime.now() - timedelta(hours=since_hours)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM clips 
                WHERE status IN ('posted', 'submitted')
                AND posted_at > ?
                ORDER BY posted_at DESC
            """, (cutoff,))
            
            rows = cursor.fetchall()
            return [Clip(**dict(row)) for row in rows]
    
    def get_daily_stats(self, date: str = None) -> Dict:
        """Get stats for a specific date (default: today)."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get from daily_stats table
            cursor = conn.execute("""
                SELECT * FROM daily_stats WHERE date = ?
            """, (date,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            
            # Calculate from clips table
            day_start = f"{date}T00:00:00"
            day_end = f"{date}T23:59:59"
            
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as clips_downloaded,
                    SUM(CASE WHEN status IN ('posted', 'submitted') THEN 1 ELSE 0 END) as clips_posted,
                    SUM(views_total) as total_views,
                    SUM(earnings) as total_earnings
                FROM clips
                WHERE downloaded_at BETWEEN ? AND ?
            """, (day_start, day_end))
            
            row = cursor.fetchone()
            return {
                "date": date,
                "clips_downloaded": row[0] or 0,
                "clips_posted": row[1] or 0,
                "total_views": row[2] or 0,
                "total_earnings": row[3] or 0.0,
            }
    
    def get_all_time_stats(self) -> Dict:
        """Get lifetime statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_clips,
                    SUM(CASE WHEN status IN ('posted', 'submitted') THEN 1 ELSE 0 END) as total_posted,
                    SUM(views_total) as total_views,
                    SUM(earnings) as total_earnings
                FROM clips
            """)
            row = cursor.fetchone()
            
            return {
                "total_clips": row[0] or 0,
                "total_posted": row[1] or 0,
                "total_views": row[2] or 0,
                "total_earnings": row[3] or 0.0,
            }
    
    def clip_exists(self, vyro_clip_id: str) -> bool:
        """Check if a clip has already been downloaded."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 1 FROM clips WHERE vyro_clip_id = ?
            """, (vyro_clip_id,))
            return cursor.fetchone() is not None
    
    def get_clips_needing_submission(self) -> List[Clip]:
        """Get clips posted but not yet submitted to Vyro."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM clips 
                WHERE status = 'posted'
                ORDER BY posted_at ASC
            """)
            
            rows = cursor.fetchall()
            return [Clip(**dict(row)) for row in rows]


# Convenience instance
queue = QueueManager()
