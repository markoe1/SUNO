"""
Autonomous Clip Pipeline
========================
PHASE 6: Complete flow from clip discovery to posting and earnings tracking.

Pipeline stages:
1. Discover: Monitor clips/inbox for new files
2. Validate: Check quality, campaign requirements, creator info
3. Enqueue: Add to posting queue with metadata
4. Post: Upload to all enabled platforms
5. Submit: Send URLs back to Whop for tracking
6. Track: Monitor views and earnings
"""

import logging
import asyncio
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import json

import config
from queue_manager import QueueManager, Clip, ClipStatus
from quality_monitor import QualityMonitor
from campaign_requirements import CampaignRequirementsValidator
from earnings_tracker import EarningsTracker
from youtube_discovery import YouTubeDiscovery
from moment_detector import MomentDetector
from auto_clipper import AutoClipper
from caption_generator import CaptionGenerator

logger = logging.getLogger(__name__)


class ClipPipeline:
    """Autonomous pipeline for clip processing from inbox to posting."""

    def __init__(self):
        self.queue = QueueManager()
        self.quality_monitor = QualityMonitor()
        self.campaign_validator = CampaignRequirementsValidator()
        self.earnings_tracker = EarningsTracker()

    def discover_clips(self) -> List[Path]:
        """
        Discover new clips in inbox directory.

        Returns:
            List of Path objects for video files
        """
        config.CLIPS_INBOX.mkdir(parents=True, exist_ok=True)

        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        clips = [
            f for f in config.CLIPS_INBOX.iterdir()
            if f.is_file() and f.suffix.lower() in video_extensions
        ]

        return sorted(clips, key=lambda x: x.stat().st_mtime)

    def _extract_clip_metadata(self, clip_path: Path) -> Dict:
        """
        Extract metadata from clip filename or metadata file.

        Expected filename format:
        {creator}_{source}_{campaign}_{title}_{duration}.mp4

        Or look for .meta.json file with same base name

        Args:
            clip_path: Path to clip file

        Returns:
            Dict with creator_name, source_platform, source_url, etc
        """
        metadata = {
            'creator_name': 'unknown',
            'source_platform': 'youtube',
            'source_url': '',
            'clip_duration': 30,
            'campaign_id': '',
        }

        # Try to load metadata file first
        meta_file = clip_path.with_suffix('.meta.json')
        if meta_file.exists():
            try:
                with open(meta_file) as f:
                    metadata.update(json.load(f))
                logger.info(f"Loaded metadata from {meta_file.name}")
                return metadata
            except Exception as e:
                logger.warning(f"Failed to load metadata file: {e}")

        # Parse from filename (fallback)
        # Format: creator_source_campaign_title_duration.mp4
        stem = clip_path.stem
        parts = stem.split('_')

        if len(parts) >= 3:
            metadata['creator_name'] = parts[0]
            metadata['source_platform'] = parts[1]
            if len(parts) >= 4:
                metadata['campaign_id'] = parts[2]

        logger.info(f"Extracted metadata from filename: {metadata}")
        return metadata

    def ingest_clip(self, clip_path: Path, campaign_name: str = None) -> Optional[int]:
        """
        Ingest a single clip into the queue.

        Args:
            clip_path: Path to clip file
            campaign_name: Campaign name (if known)

        Returns:
            Clip ID if successfully added, None otherwise
        """
        logger.info(f"Ingesting clip: {clip_path.name}")

        try:
            # Extract metadata
            metadata = self._extract_clip_metadata(clip_path)

            # Create clip object
            clip = Clip(
                filename=clip_path.name,
                filepath=str(clip_path),
                campaign_name=campaign_name or "default",
                campaign_id=metadata.get('campaign_id', ''),
                creator_name=metadata.get('creator_name', 'unknown'),
                source_platform=metadata.get('source_platform', 'youtube'),
                source_url=metadata.get('source_url', ''),
                clip_duration=metadata.get('clip_duration', 30),
                caption=metadata.get('caption', ''),
                hashtags=metadata.get('hashtags', ''),
                status=ClipStatus.PENDING.value,
            )

            # Add to queue
            clip_id = self.queue.add_clip(clip)
            logger.info(f"Clip ingested with ID: {clip_id}")
            return clip_id

        except Exception as e:
            logger.error(f"Failed to ingest clip: {e}")
            return None

    def process_inbox(self, campaign_name: str = None) -> Dict:
        """
        Process all clips in inbox and add to queue.

        Args:
            campaign_name: Campaign to assign clips to (if not in metadata)

        Returns:
            Dict with processing stats
        """
        logger.info("Processing clips in inbox...")

        clips = self.discover_clips()
        stats = {
            'total': len(clips),
            'ingested': 0,
            'failed': 0,
            'already_queued': 0,
        }

        for clip_path in clips:
            # Check if already in queue
            if self.queue.clip_exists(clip_path.name):
                logger.info(f"Clip already queued: {clip_path.name}")
                stats['already_queued'] += 1
                continue

            # Ingest clip
            clip_id = self.ingest_clip(clip_path, campaign_name)
            if clip_id:
                stats['ingested'] += 1
            else:
                stats['failed'] += 1

        logger.info(f"Inbox processed: {stats}")
        return stats

    async def discover_and_generate_clips(
        self,
        source_type: str = "youtube",
        query: Optional[str] = None,
        channel_url: Optional[str] = None,
        max_videos: int = 5,
        moments_per_video: int = 3,
        target_duration_sec: tuple = (15, 60),
        padding_sec: float = 1.0,
        campaign_name: str = "auto_generated"
    ) -> Dict:
        """
        Full upstream pipeline: discover → clip → caption → queue.

        Args:
            source_type: "youtube" (currently supported)
            query: Search query (alternative to channel_url)
            channel_url: YouTube channel URL
            max_videos: Maximum videos to process
            moments_per_video: Target moments to extract per video
            target_duration_sec: Target clip duration range (min, max)
            padding_sec: Padding around moment (seconds)
            campaign_name: Campaign to assign generated clips to

        Returns:
            Dict with pipeline stats:
            {
                'videos_discovered': int,
                'videos_downloaded': int,
                'moments_detected': int,
                'clips_extracted': int,
                'captions_generated': int,
                'clips_queued': int,
                'failed': int,
                'total_duration_queued': float (seconds)
            }
        """
        logger.info(
            f"Starting autonomous discovery pipeline: "
            f"source={source_type}, max_videos={max_videos}"
        )

        stats = {
            'videos_discovered': 0,
            'videos_downloaded': 0,
            'moments_detected': 0,
            'clips_extracted': 0,
            'captions_generated': 0,
            'clips_queued': 0,
            'failed': 0,
            'total_duration_queued': 0.0,
        }

        # Step 1: Discover videos from YouTube
        if source_type != "youtube":
            logger.error(f"Unsupported source type: {source_type}")
            return stats

        try:
            discovery = YouTubeDiscovery()

            if query:
                videos = discovery.search_query(query, max_videos=max_videos)
            elif channel_url:
                videos = discovery.search_channel(channel_url, max_videos=max_videos)
            else:
                logger.error("Must provide either query or channel_url")
                return stats

            if not videos:
                logger.warning("No videos discovered")
                return stats

            stats['videos_discovered'] = len(videos)
            logger.info(f"Discovered {len(videos)} videos")

            # Download videos
            logger.info("Downloading videos...")
            downloaded = discovery.download_videos(videos)
            stats['videos_downloaded'] = len(downloaded)
            logger.info(f"Downloaded {len(downloaded)}/{len(videos)} videos")

            # Process each downloaded video
            for i, video in enumerate(downloaded, 1):
                logger.info(f"\n=== Processing video {i}/{len(downloaded)}: {video.title} ===")

                try:
                    if not video.local_path:
                        logger.warning(f"No local path for {video.title}")
                        stats['failed'] += 1
                        continue

                    # Generate clips from this video
                    video_stats = await self._generate_clips_from_video(
                        video_path=video.local_path,
                        source_title=video.title,
                        source_url=video.url,
                        source_channel=video.channel,
                        moments_target=moments_per_video,
                        target_duration_sec=target_duration_sec,
                        padding_sec=padding_sec,
                        campaign_name=campaign_name
                    )

                    # Accumulate stats
                    stats['moments_detected'] += video_stats['moments_detected']
                    stats['clips_extracted'] += video_stats['clips_extracted']
                    stats['captions_generated'] += video_stats['captions_generated']
                    stats['clips_queued'] += video_stats['clips_queued']
                    stats['total_duration_queued'] += video_stats['total_duration_queued']
                    if video_stats['failed'] > 0:
                        stats['failed'] += video_stats['failed']

                except Exception as e:
                    logger.error(f"Failed to process video: {e}")
                    stats['failed'] += 1

            logger.info(f"\n=== Pipeline Complete ===")
            logger.info(f"Videos processed: {stats['videos_downloaded']}")
            logger.info(f"Moments detected: {stats['moments_detected']}")
            logger.info(f"Clips extracted: {stats['clips_extracted']}")
            logger.info(f"Clips queued: {stats['clips_queued']}")
            logger.info(f"Total duration queued: {stats['total_duration_queued']:.1f}s")

            return stats

        except Exception as e:
            logger.error(f"Discovery and generation pipeline failed: {e}")
            return stats

    async def _generate_clips_from_video(
        self,
        video_path: str,
        source_title: str,
        source_url: str,
        source_channel: str,
        moments_target: int = 3,
        target_duration_sec: tuple = (15, 60),
        padding_sec: float = 1.0,
        campaign_name: str = "auto_generated"
    ) -> Dict:
        """
        Generate clips from a single video.

        Args:
            video_path: Path to downloaded video
            source_title: Original video title
            source_url: URL of source video
            source_channel: Channel name
            moments_target: Target number of moments to extract
            target_duration_sec: Target duration range
            padding_sec: Padding around moment
            campaign_name: Campaign name

        Returns:
            Dict with stats for this video
        """
        stats = {
            'moments_detected': 0,
            'clips_extracted': 0,
            'captions_generated': 0,
            'clips_queued': 0,
            'failed': 0,
            'total_duration_queued': 0.0,
        }

        try:
            # Step 2: Detect moments in video
            logger.info("Detecting moments...")
            detector = MomentDetector()
            moments = detector.detect_moments(video_path)

            if not moments:
                logger.warning("No moments detected in video")
                return stats

            stats['moments_detected'] = len(moments)
            logger.info(f"Detected {len(moments)} moments")

            # Limit to target
            moments_to_clip = moments[:moments_target]
            logger.info(f"Processing top {len(moments_to_clip)} moments")

            # Step 3: Extract clips from moments
            logger.info("Extracting clips from moments...")
            clipper = AutoClipper()
            clip_paths = clipper.extract_clips_from_moments(
                video_path,
                moments_to_clip,
                padding_sec=padding_sec,
                target_duration_sec=target_duration_sec
            )

            stats['clips_extracted'] = len(clip_paths)
            logger.info(f"Extracted {len(clip_paths)} clips")

            # Validate clips
            valid_clips = clipper.validate_clips(clip_paths)
            logger.info(f"Validated {len(valid_clips)}/{len(clip_paths)} clips")

            # Step 4: Generate captions for each clip
            logger.info("Generating captions...")
            generator = CaptionGenerator()
            captions_data = []

            for clip_path in valid_clips:
                try:
                    # Find corresponding moment
                    moment_idx = clip_paths.index(clip_path)
                    moment = moments_to_clip[moment_idx] if moment_idx < len(moments_to_clip) else None

                    caption_obj = generator.generate(
                        clip_path=str(clip_path),
                        source_title=source_title,
                        moment_type=moment.reason if moment else "unknown",
                        creator_preferences={
                            "style": "engaging, viral-focused",
                            "tone": "energetic, authentic"
                        }
                    )

                    if caption_obj:
                        captions_data.append({
                            'clip_path': clip_path,
                            'caption': caption_obj.caption,
                            'hashtags': caption_obj.hashtags,
                            'moment_type': caption_obj.moment_type
                        })
                        stats['captions_generated'] += 1
                    else:
                        logger.warning(f"Failed to generate caption for {clip_path.name}")

                except Exception as e:
                    logger.warning(f"Caption generation failed for {clip_path.name}: {e}")

            logger.info(f"Generated {stats['captions_generated']} captions")

            # Step 5: Ingest clips into queue
            logger.info("Ingesting clips into queue...")
            for caption_data in captions_data:
                try:
                    clip_path = caption_data['clip_path']

                    # Create metadata file
                    meta_file = clip_path.with_suffix('.meta.json')
                    metadata = {
                        'creator_name': source_channel,
                        'source_platform': 'youtube',
                        'source_url': source_url,
                        'clip_duration': 0,  # Will be measured
                        'campaign_id': campaign_name,
                        'caption': caption_data['caption'],
                        'hashtags': ' '.join(caption_data['hashtags']),
                        'moment_type': caption_data['moment_type'],
                        'generated_at': datetime.now().isoformat(),
                    }

                    with open(meta_file, 'w') as f:
                        json.dump(metadata, f, indent=2)

                    # Ingest clip
                    clip_id = self.ingest_clip(
                        clip_path,
                        campaign_name=campaign_name
                    )

                    if clip_id:
                        stats['clips_queued'] += 1
                        # Get clip duration from file if possible
                        try:
                            import subprocess
                            result = subprocess.run(
                                [
                                    "ffprobe", "-v", "error",
                                    "-show_entries", "format=duration",
                                    "-of", "default=noprint_wrappers=1:nokey=1:noval=0",
                                    str(clip_path)
                                ],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            if result.returncode == 0:
                                duration = float(result.stdout.strip())
                                stats['total_duration_queued'] += duration
                        except Exception:
                            pass  # Ignore duration extraction errors

                        logger.info(f"Queued clip: {clip_path.name}")
                    else:
                        logger.warning(f"Failed to queue clip: {clip_path.name}")
                        stats['failed'] += 1

                except Exception as e:
                    logger.error(f"Failed to ingest clip: {e}")
                    stats['failed'] += 1

            return stats

        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            stats['failed'] += 1
            return stats

    async def run_pipeline_loop(self, interval: int = 60):
        """
        Run the pipeline continuously.

        Args:
            interval: Seconds between pipeline runs
        """
        logger.info(f"Starting autonomous clip pipeline (interval: {interval}s)")

        while True:
            try:
                # Discover and ingest new clips
                self.process_inbox()

                # Get pending clips
                pending = self.queue.get_pending_clips(limit=config.CLIPS_PER_SESSION)
                if pending:
                    logger.info(f"Found {len(pending)} pending clips, ready for posting")

                # Display status
                stats = self.queue.get_daily_stats()
                logger.info(
                    f"Pipeline status: "
                    f"Pending: {stats.get('clips_pending', 0)}, "
                    f"Posted today: {stats.get('clips_posted', 0)}, "
                    f"Earnings: ${stats.get('earnings', 0):.2f}"
                )

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Pipeline error: {e}")
                await asyncio.sleep(interval)


def main():
    """Test clip pipeline."""
    logging.basicConfig(level=logging.INFO)

    pipeline = ClipPipeline()

    # Test clip discovery
    logger.info("Testing clip discovery...")
    clips = pipeline.discover_clips()
    logger.info(f"Found {len(clips)} clips in inbox")

    # Test inbox processing
    logger.info("Testing inbox processing...")
    stats = pipeline.process_inbox(campaign_name="default")
    logger.info(f"Processed: {stats}")


if __name__ == "__main__":
    main()
