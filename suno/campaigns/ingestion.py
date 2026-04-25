"""
Campaign and Clip Ingestion Layer
Fetches campaigns/clips from source, normalizes metadata, persists with deduplication.

Source integrations:
- Internal campaign API
- User uploads
- External content sources
"""

import hashlib
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class CampaignIngestionError(Exception):
    """Raised when campaign ingestion fails"""
    pass


class CampaignMetadataNormalizer:
    """Normalize campaign and clip metadata from various sources."""

    @staticmethod
    def normalize_campaign(raw_campaign: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize campaign metadata from external source.

        Args:
            raw_campaign: Raw campaign data (structure varies by source)

        Returns:
            Normalized campaign dict with required fields
        """
        return {
            "source_id": str(raw_campaign.get("id") or raw_campaign.get("campaign_id")),
            "source_type": raw_campaign.get("source_type", "internal"),
            "title": str(raw_campaign.get("title") or raw_campaign.get("name", "")).strip(),
            "description": str(raw_campaign.get("description", "")).strip(),
            "brief": str(raw_campaign.get("brief", "")).strip(),
            "keywords": raw_campaign.get("keywords", []),
            "target_platforms": raw_campaign.get("platforms", []),
            "tone": raw_campaign.get("tone", ""),
            "style": raw_campaign.get("style", ""),
            "duration_seconds": raw_campaign.get("duration", 30),
            "metadata": raw_campaign.get("metadata", {}),
        }

    @staticmethod
    def normalize_clip(raw_clip: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize clip metadata from source.

        Args:
            raw_clip: Raw clip data (structure varies by source)

        Returns:
            Normalized clip dict with required fields
        """
        return {
            "source_url": raw_clip.get("url") or raw_clip.get("source_url", ""),
            "source_platform": raw_clip.get("platform", ""),
            "title": str(raw_clip.get("title", "")).strip(),
            "description": str(raw_clip.get("description", "")).strip(),
            "creator": raw_clip.get("creator", ""),
            "view_count": int(raw_clip.get("views") or raw_clip.get("view_count", 0)),
            "engagement_score": float(raw_clip.get("engagement_score", 0.0)),
            "trending_category": raw_clip.get("trending_category", ""),
            "hashtags": raw_clip.get("hashtags", []),
            "audio_source": raw_clip.get("audio_source", ""),
            "metadata": raw_clip.get("metadata", {}),
        }

    @staticmethod
    def compute_content_hash(content: Dict[str, Any]) -> str:
        """
        Compute unique hash for clip content to detect duplicates.

        Args:
            content: Normalized clip/campaign data

        Returns:
            SHA256 hash of content
        """
        # Create deterministic string representation
        key_fields = [
            content.get("source_url", ""),
            content.get("title", ""),
            content.get("description", ""),
        ]
        content_str = "|".join(str(f) for f in key_fields)
        return hashlib.sha256(content_str.encode()).hexdigest()


class CampaignIngestionManager:
    """
    Manages campaign and clip ingestion with deduplication and state tracking.
    """

    def __init__(self, db: Session):
        """
        Initialize ingestion manager.

        Args:
            db: SQLAlchemy session for database access
        """
        self.db = db
        self.normalizer = CampaignMetadataNormalizer()

    def ingest_campaign(self, raw_campaign: Dict[str, Any]) -> tuple[bool, Any]:
        """
        Ingest a campaign with deduplication.

        Args:
            raw_campaign: Raw campaign data from source

        Returns:
            (is_new, campaign_record): bool indicating if new, and the campaign record

        Raises:
            CampaignIngestionError: If ingestion fails
        """
        try:
            # Normalize metadata
            normalized = self.normalizer.normalize_campaign(raw_campaign)

            # Import here to avoid circular imports
            from suno.common.models import Campaign

            # Check if campaign already exists (by source_id + source_type)
            existing = self.db.query(Campaign).filter(
                Campaign.source_id == normalized["source_id"],
                Campaign.source_type == normalized["source_type"],
            ).first()

            if existing:
                # Campaign already exists - update last_seen
                existing.last_seen_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"Campaign {normalized['source_id']} already ingested, updated timestamp")
                return False, existing

            # Create new campaign record
            campaign = Campaign(
                source_id=normalized["source_id"],
                source_type=normalized["source_type"],
                title=normalized["title"],
                description=normalized["description"],
                brief=normalized["brief"],
                keywords=normalized["keywords"],
                target_platforms=normalized["target_platforms"],
                tone=normalized["tone"],
                style=normalized["style"],
                duration_seconds=normalized["duration_seconds"],
                metadata=normalized["metadata"],
                available=True,
                last_seen_at=datetime.utcnow(),
            )
            self.db.add(campaign)
            self.db.commit()

            logger.info(f"Successfully ingested campaign {normalized['source_id']}")
            return True, campaign

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error ingesting campaign: {e}")
            raise CampaignIngestionError(f"Duplicate campaign: {e}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error ingesting campaign: {e}")
            raise CampaignIngestionError(f"Failed to ingest campaign: {e}")

    def ingest_clip(self, campaign_id: int, raw_clip: Dict[str, Any]) -> tuple[bool, Any]:
        """
        Ingest a clip with deduplication and platform eligibility checking.

        Args:
            campaign_id: ID of parent campaign
            raw_clip: Raw clip data from source

        Returns:
            (is_new, clip_record): bool indicating if new, and the clip record

        Raises:
            CampaignIngestionError: If ingestion fails
        """
        try:
            # Normalize metadata
            normalized = self.normalizer.normalize_clip(raw_clip)

            # Import here to avoid circular imports
            from suno.common.models import Clip, Campaign

            # Get campaign
            campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                raise CampaignIngestionError(f"Campaign {campaign_id} not found")

            # Compute content hash for deduplication
            content_hash = self.normalizer.compute_content_hash(normalized)

            # Check if clip already exists (by content hash or source URL)
            existing = self.db.query(Clip).filter(
                (Clip.content_hash == content_hash) |
                (Clip.source_url == normalized["source_url"])
            ).first()

            if existing:
                # Clip already exists - update last_seen
                existing.last_seen_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"Clip {normalized.get('title')} already ingested, updated timestamp")
                return False, existing

            # Determine platform eligibility
            platform_eligible = self._determine_platform_eligibility(
                normalized["source_platform"],
                campaign.target_platforms,
            )

            # Create new clip record
            clip = Clip(
                campaign_id=campaign_id,
                source_url=normalized["source_url"],
                source_platform=normalized["source_platform"],
                title=normalized["title"],
                description=normalized["description"],
                creator=normalized["creator"],
                view_count=normalized["view_count"],
                engagement_score=normalized["engagement_score"],
                trending_category=normalized["trending_category"],
                hashtags=normalized["hashtags"],
                audio_source=normalized["audio_source"],
                content_hash=content_hash,
                platform_eligible=platform_eligible,
                available=True,
                metadata=normalized["metadata"],
                last_seen_at=datetime.utcnow(),
            )
            self.db.add(clip)
            self.db.commit()

            logger.info(f"Successfully ingested clip {normalized.get('title')}")
            return True, clip

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error ingesting clip: {e}")
            raise CampaignIngestionError(f"Duplicate clip: {e}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error ingesting clip: {e}")
            raise CampaignIngestionError(f"Failed to ingest clip: {e}")

    def ingest_campaigns_batch(self, campaigns: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Ingest multiple campaigns in batch.

        Args:
            campaigns: List of raw campaign dicts

        Returns:
            Stats dict with counts: new_count, existing_count, failed_count
        """
        stats = {"new": 0, "existing": 0, "failed": 0}

        for raw_campaign in campaigns:
            try:
                is_new, _ = self.ingest_campaign(raw_campaign)
                if is_new:
                    stats["new"] += 1
                else:
                    stats["existing"] += 1
            except Exception as e:
                logger.error(f"Failed to ingest campaign: {e}")
                stats["failed"] += 1

        logger.info(f"Batch ingestion complete: {stats}")
        return stats

    def ingest_clips_batch(self, campaign_id: int, clips: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Ingest multiple clips for a campaign.

        Args:
            campaign_id: ID of parent campaign
            clips: List of raw clip dicts

        Returns:
            Stats dict with counts: new_count, existing_count, failed_count
        """
        stats = {"new": 0, "existing": 0, "failed": 0}

        for raw_clip in clips:
            try:
                is_new, _ = self.ingest_clip(campaign_id, raw_clip)
                if is_new:
                    stats["new"] += 1
                else:
                    stats["existing"] += 1
            except Exception as e:
                logger.error(f"Failed to ingest clip: {e}")
                stats["failed"] += 1

        logger.info(f"Clips batch ingestion complete: {stats}")
        return stats

    @staticmethod
    def _determine_platform_eligibility(source_platform: str, target_platforms: List[str]) -> bool:
        """
        Determine if clip is eligible for target platforms based on source.

        Rules:
        - TikTok clips eligible for all platforms
        - Instagram Reels eligible for all platforms
        - YouTube Shorts eligible for all platforms
        - Twitter video eligible for Twitter, Threads, Bluesky

        Args:
            source_platform: Platform clip originated from
            target_platforms: Platforms we want to post to

        Returns:
            True if clip can be adapted for target platforms
        """
        if not target_platforms:
            return False

        source = source_platform.lower()
        target_set = {p.lower() for p in target_platforms}

        # TikTok, Instagram Reels, YouTube Shorts are universal
        if source in ["tiktok", "instagram_reels", "youtube_shorts"]:
            return True

        # Twitter videos work on text-based platforms
        if source == "twitter":
            compatible = {"twitter", "threads", "bluesky"}
            return bool(target_set & compatible)

        # Default: any source is eligible if we have targets
        return len(target_set) > 0
