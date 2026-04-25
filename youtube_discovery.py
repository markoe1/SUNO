"""
YouTube Content Discovery
=========================
Finds and downloads videos from YouTube channels.
Uses yt-dlp for reliable, API-free access.
"""

import logging
import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import subprocess
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Import creator registry for auto-discovery integration
try:
    from creator_registry import CreatorRegistry
    HAS_CREATOR_REGISTRY = True
except ImportError:
    HAS_CREATOR_REGISTRY = False
    logger.warning("CreatorRegistry not available - creator discovery disabled")


@dataclass
class YouTubeVideo:
    """YouTube video metadata."""
    video_id: str
    url: str
    title: str
    channel: str
    duration: int  # seconds
    upload_date: str  # YYYY-MM-DD
    description: str
    local_path: Optional[str] = None  # After download


class YouTubeDiscovery:
    """Discover and download videos from YouTube."""

    def __init__(self, download_dir: Path = None, auto_register_creators: bool = True):
        """
        Initialize YouTube discovery.

        Args:
            download_dir: Directory to save downloaded videos
            auto_register_creators: If True, automatically register discovered creators
                                   in the creator registry (for auto-discovery pipeline)
        """
        self.download_dir = download_dir or Path("data/youtube_sources")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.download_dir / "metadata.json"
        self.auto_register_creators = auto_register_creators
        self.creator_registry = CreatorRegistry() if HAS_CREATOR_REGISTRY and auto_register_creators else None

    def search_channel(
        self,
        channel_url: str,
        max_videos: int = 10,
        min_duration_sec: int = 60,
        max_duration_sec: int = 3600,
        days_back: int = 90
    ) -> List[YouTubeVideo]:
        """
        Get videos from a YouTube channel.

        Args:
            channel_url: https://www.youtube.com/@channelname or /c/channelname
            max_videos: Maximum number of videos to return
            min_duration_sec: Minimum video duration (skip Shorts)
            max_duration_sec: Maximum duration (skip long-form)
            days_back: Only videos from last N days

        Returns:
            List of YouTubeVideo objects
        """
        logger.info(f"Searching channel: {channel_url}")

        try:
            # Use yt-dlp to list videos
            cmd = [
                "yt-dlp",
                "--dump-json",
                "-j",
                f"{channel_url}/videos",
                "--dateafter",
                (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d"),
                "--max-downloads",
                str(max_videos),
            ]

            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.error(f"yt-dlp failed: {result.stderr}")
                return []

            videos = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    duration = data.get("duration", 0)

                    # Filter by duration
                    if duration < min_duration_sec or duration > max_duration_sec:
                        logger.debug(
                            f"Skipping {data.get('title', 'Unknown')}: "
                            f"duration {duration}s outside range"
                        )
                        continue

                    channel_name = data.get("channel", "Unknown")
                    video = YouTubeVideo(
                        video_id=data.get("id", ""),
                        url=f"https://www.youtube.com/watch?v={data.get('id', '')}",
                        title=data.get("title", "Unknown"),
                        channel=channel_name,
                        duration=duration,
                        upload_date=data.get("upload_date", ""),
                        description=data.get("description", "")[:200],  # Truncate
                    )
                    videos.append(video)

                    # Register creator with registry (auto-discovery integration)
                    self._register_creator(channel_name)

                    logger.info(
                        f"  Found: {video.title} ({video.duration}s) "
                        f"from {video.channel}"
                    )

                except json.JSONDecodeError:
                    continue

            logger.info(f"Found {len(videos)} videos matching criteria")
            return videos

        except subprocess.TimeoutExpired:
            logger.error("yt-dlp search timed out")
            return []
        except Exception as e:
            logger.error(f"Channel search failed: {e}")
            return []

    def _register_creator(self, channel_name: str):
        """Register a creator with the creator registry for auto-discovery."""
        if not self.creator_registry or not channel_name or channel_name == "Unknown":
            return

        try:
            self.creator_registry.discover_creator(channel_name, "youtube")
        except Exception as e:
            logger.debug(f"Could not register creator {channel_name}: {e}")

    def search_query(
        self,
        query: str,
        max_videos: int = 5,
        min_duration_sec: int = 60,
        max_duration_sec: int = 3600,
    ) -> List[YouTubeVideo]:
        """
        Search YouTube for videos matching query.

        Args:
            query: Search term
            max_videos: Max results
            min_duration_sec: Minimum duration
            max_duration_sec: Maximum duration

        Returns:
            List of YouTubeVideo objects
        """
        logger.info(f"Searching YouTube for: {query}")

        try:
            cmd = [
                "yt-dlp",
                "--dump-json",
                "-j",
                f"ytsearch{max_videos}:{query}",
            ]

            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.error(f"yt-dlp search failed: {result.stderr}")
                return []

            videos = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    duration = data.get("duration", 0)

                    if duration < min_duration_sec or duration > max_duration_sec:
                        continue

                    channel_name = data.get("channel", "Unknown")
                    video = YouTubeVideo(
                        video_id=data.get("id", ""),
                        url=f"https://www.youtube.com/watch?v={data.get('id', '')}",
                        title=data.get("title", "Unknown"),
                        channel=channel_name,
                        duration=duration,
                        upload_date=data.get("upload_date", ""),
                        description=data.get("description", "")[:200],
                    )
                    videos.append(video)

                    # Register creator with registry (auto-discovery integration)
                    self._register_creator(channel_name)

                    logger.info(
                        f"  Found: {video.title} ({video.duration}s) "
                        f"from {video.channel}"
                    )

                except json.JSONDecodeError:
                    continue

            logger.info(f"Search returned {len(videos)} videos")
            return videos

        except subprocess.TimeoutExpired:
            logger.error("yt-dlp search timed out")
            return []
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def download_video(self, video: YouTubeVideo) -> Optional[Path]:
        """
        Download a video file.

        Args:
            video: YouTubeVideo object

        Returns:
            Path to downloaded file, or None if failed
        """
        output_template = str(
            self.download_dir / "%(id)s_%(title)s.%(ext)s"
        )

        logger.info(f"Downloading: {video.title} ({video.duration}s)")

        try:
            cmd = [
                "yt-dlp",
                "-f",
                "best[ext=mp4]/best",  # Best quality MP4
                "-o",
                output_template,
                video.url,
            ]

            logger.info(f"Running: {' '.join(cmd[:3])}...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                logger.error(f"Download failed: {result.stderr}")
                return None

            # Find the downloaded file
            downloaded_files = list(
                self.download_dir.glob(f"{video.video_id}_*.mp4")
            )
            if downloaded_files:
                file_path = downloaded_files[0]
                logger.info(f"Downloaded to: {file_path}")
                video.local_path = str(file_path)
                return file_path
            else:
                logger.error("Download completed but file not found")
                return None

        except subprocess.TimeoutExpired:
            logger.error("Download timed out (video too large)")
            return None
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    def download_videos(self, videos: List[YouTubeVideo]) -> List[YouTubeVideo]:
        """
        Download multiple videos.

        Args:
            videos: List of YouTubeVideo objects

        Returns:
            List of videos with local_path filled in (excludes failed)
        """
        downloaded = []

        for i, video in enumerate(videos, 1):
            logger.info(f"Downloading {i}/{len(videos)}: {video.title}")

            file_path = self.download_video(video)
            if file_path:
                downloaded.append(video)
            else:
                logger.warning(f"Failed to download: {video.title}")

        logger.info(f"Successfully downloaded {len(downloaded)}/{len(videos)} videos")
        return downloaded

    def save_metadata(self, videos: List[YouTubeVideo]) -> None:
        """Save video metadata to JSON file."""
        try:
            metadata = [
                {
                    "video_id": v.video_id,
                    "url": v.url,
                    "title": v.title,
                    "channel": v.channel,
                    "duration": v.duration,
                    "upload_date": v.upload_date,
                    "description": v.description,
                    "local_path": v.local_path,
                    "downloaded_at": datetime.now().isoformat(),
                }
                for v in videos
            ]

            with open(self.metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved metadata to {self.metadata_file}")
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")


def main():
    """Test YouTube discovery."""
    logging.basicConfig(level=logging.INFO)

    discovery = YouTubeDiscovery()

    # Test 1: Search for videos
    logger.info("\n=== TEST 1: Search YouTube ===")
    videos = discovery.search_query(
        "viral clips",
        max_videos=3,
        min_duration_sec=60,  # At least 1 min
        max_duration_sec=1800,  # At most 30 min
    )
    logger.info(f"Found {len(videos)} videos")

    if videos:
        # Test 2: Download (optional - will be slow)
        logger.info("\n=== TEST 2: Download Video ===")
        logger.info("Skipping download in test (would take time)")
        logger.info(f"Would download: {videos[0].title}")

        # Show what would be downloaded
        logger.info("\nVideos ready for download:")
        for v in videos:
            logger.info(f"  - {v.title} ({v.duration}s)")


if __name__ == "__main__":
    main()
