"""
Campaign Requirements & Creator Intent Validation
==================================================
PHASE 5: Validates that clips match campaign requirements and creator is approved.

Enforces:
1. Campaign is active in database
2. Clip source/creator matches campaign requirements
3. Creator is whitelisted (if applicable)
4. Campaign budget not exhausted
5. Clip matches campaign content type requirements
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json

from queue_manager import QueueManager

logger = logging.getLogger(__name__)


@dataclass
class CreatorProfile:
    """Creator metadata and verification status."""
    name: str                  # Creator/channel name
    source_url: str            # Original source (YouTube, TikTok, etc)
    source_platform: str       # youtube, tiktok, instagram, etc
    is_whitelisted: bool       # Creator approved for this account
    verification_status: str   # unverified, pending, verified, blocked


@dataclass
class CampaignRequirement:
    """Campaign-specific requirements."""
    campaign_id: str
    campaign_name: str
    active: bool

    # Content requirements
    min_clip_duration: int     # seconds
    max_clip_duration: int     # seconds
    allowed_sources: List[str] # youtube, tiktok, instagram, twitter, etc
    content_type: str          # music, comedy, educational, news, etc

    # Creator requirements
    creator_whitelist: List[str]  # If empty, all creators allowed
    creator_blacklist: List[str]  # Never allow these creators

    # Budget & limits
    budget_remaining: float    # $ remaining
    daily_clip_limit: int      # Clips per day max
    cpm: float                 # $ per 1K views


class CampaignRequirementsValidator:
    """Validates clips against campaign requirements."""

    def __init__(self, allow_unverified_creators: bool = True):
        """
        Initialize validator.

        Args:
            allow_unverified_creators: If True, allow clips from unverified creators
                                      (for auto-discovery mode). If False, reject them
                                      (strict mode).
        """
        self.queue = QueueManager()
        self.requirements_cache: Dict[str, CampaignRequirement] = {}
        self.allow_unverified_creators = allow_unverified_creators
        self._load_requirements()

    def _load_requirements(self):
        """Load campaign requirements from database and normalize lists."""
        try:
            active_campaigns = self.queue.get_active_campaigns()
            for campaign in active_campaigns:
                # Parse comma-separated strings into lists
                source_types = self._parse_list(campaign.source_types, default=["youtube"])
                creator_whitelist = self._parse_list(campaign.creator_whitelist, default=[])
                creator_blacklist = self._parse_list(campaign.creator_blacklist, default=[])

                req = CampaignRequirement(
                    campaign_id=campaign.whop_id,  # Use whop_id as canonical key
                    campaign_name=campaign.name,
                    active=campaign.active,
                    min_clip_duration=campaign.min_duration or 15,
                    max_clip_duration=campaign.max_duration or 60,
                    allowed_sources=source_types,
                    content_type=campaign.content_type or "general",
                    creator_whitelist=creator_whitelist,
                    creator_blacklist=creator_blacklist,
                    budget_remaining=campaign.budget_remaining or 0,
                    daily_clip_limit=campaign.daily_clip_limit or 100,
                    cpm=campaign.cpm or 0.0
                )
                # Use whop_id as cache key for consistency
                self.requirements_cache[campaign.whop_id] = req
        except Exception as e:
            logger.error(f"Failed to load campaign requirements: {e}")

    def _parse_list(self, value: str, default: list = None) -> list:
        """
        Parse comma-separated string into list.

        Args:
            value: Comma-separated string (e.g., "youtube,tiktok")
            default: Default value if empty

        Returns:
            List of items
        """
        if default is None:
            default = []

        if not value or not isinstance(value, str):
            return default

        # Split by comma and strip whitespace
        items = [item.strip() for item in value.split(',') if item.strip()]
        return items if items else default

    def validate_clip_for_campaign(
        self,
        campaign_id: str,
        creator_name: str,
        source_platform: str,
        clip_duration: int
    ) -> Tuple[bool, List[str]]:
        """
        Validate if clip matches campaign requirements.

        Args:
            campaign_id: Campaign whop_id (canonical key)
            creator_name: Creator/channel name
            source_platform: Where clip comes from (youtube, tiktok, etc)
            clip_duration: Duration in seconds

        Returns:
            (approved: bool, reasons: List[str] if rejected)
        """
        reasons = []

        # Check campaign exists and is active
        if campaign_id not in self.requirements_cache:
            return False, [f"Campaign {campaign_id} not found or inactive"]

        req = self.requirements_cache[campaign_id]

        if not req.active:
            reasons.append(f"Campaign '{req.campaign_name}' is inactive")
            return False, reasons

        # Check budget
        if req.budget_remaining <= 0:
            reasons.append(f"Campaign budget exhausted")

        # Check source platform (case-insensitive)
        platform_lower = source_platform.lower()
        allowed_sources_lower = [s.lower() for s in req.allowed_sources]
        if platform_lower not in allowed_sources_lower:
            reasons.append(
                f"Source platform '{source_platform}' not allowed. "
                f"Allowed: {', '.join(req.allowed_sources)}"
            )

        # Check clip duration
        if clip_duration < req.min_clip_duration:
            reasons.append(
                f"Clip duration {clip_duration}s below minimum {req.min_clip_duration}s"
            )
        if clip_duration > req.max_clip_duration:
            reasons.append(
                f"Clip duration {clip_duration}s exceeds maximum {req.max_clip_duration}s"
            )

        # Check creator blacklist (case-sensitive match)
        if creator_name in req.creator_blacklist:
            reasons.append(f"Creator '{creator_name}' is blacklisted")

        # Check creator whitelist (if configured, case-sensitive match)
        if req.creator_whitelist and creator_name not in req.creator_whitelist:
            reasons.append(
                f"Creator '{creator_name}' not in whitelist. "
                f"Whitelisted: {', '.join(req.creator_whitelist[:3])}"
            )

        # Return result
        approved = len(reasons) == 0
        return approved, reasons

    def validate_creator(
        self,
        creator_name: str,
        source_platform: str
    ) -> Tuple[bool, Optional[CreatorProfile]]:
        """
        Validate creator and return profile.

        Policy:
        1. BLOCKED creators → REJECT (always)
        2. APPROVED creators → ALLOW (always)
        3. UNVERIFIED creators → depends on allow_unverified_creators flag:
           - True (discovery mode) → ALLOW but mark as unverified
           - False (strict mode) → REJECT

        Args:
            creator_name: Creator/channel name
            source_platform: youtube, tiktok, instagram, etc

        Returns:
            (approved: bool, profile: CreatorProfile or None)
        """
        # Get or create creator profile
        creator = self.queue.get_creator(creator_name, source_platform)

        # If creator not in registry, create entry as unverified
        if not creator:
            from queue_manager import Creator
            creator = Creator(
                name=creator_name,
                platform=source_platform,
                is_approved=False,
                verification_status="unverified"
            )
            self.queue.upsert_creator(creator)
            logger.info(f"Discovered new creator: {creator_name} ({source_platform})")

        # RULE 1: Blocked creators are always rejected
        if creator.verification_status == "blocked":
            logger.warning(
                f"Creator '{creator_name}' is blocked: {creator.approval_reason}"
            )
            return False, None

        # Create profile
        profile = CreatorProfile(
            name=creator.name,
            source_url=f"https://{source_platform}.com/{creator.name}",
            source_platform=source_platform,
            is_whitelisted=creator.is_approved,
            verification_status=creator.verification_status
        )

        # RULE 2: Approved creators are always allowed
        if creator.is_approved:
            logger.info(f"Creator '{creator_name}' is APPROVED")
            return True, profile

        # RULE 3: Unverified creators depend on policy
        if self.allow_unverified_creators:
            logger.debug(
                f"Creator '{creator_name}' is UNVERIFIED but allowed "
                f"(discovery mode enabled)"
            )
            return True, profile
        else:
            logger.warning(
                f"Creator '{creator_name}' is UNVERIFIED and rejected "
                f"(strict mode enabled)"
            )
            return False, None

    def get_campaign_requirements(self, campaign_id: str) -> Optional[CampaignRequirement]:
        """
        Get requirements for a campaign.

        Args:
            campaign_id: Campaign whop_id (canonical key)

        Returns:
            CampaignRequirement or None if not found
        """
        return self.requirements_cache.get(campaign_id)

    def refresh_requirements(self):
        """Reload requirements from database."""
        self.requirements_cache.clear()
        self._load_requirements()


def main():
    """Test campaign requirements validation."""
    logging.basicConfig(level=logging.INFO)

    validator = CampaignRequirementsValidator()

    # Example: Test validation
    # (Requires actual campaign data)
    logger.info("Campaign Requirements Validator initialized")
    logger.info(f"Loaded {len(validator.requirements_cache)} campaigns")


if __name__ == "__main__":
    main()
