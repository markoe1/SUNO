"""
PHASE 3, PART 2: Clip Eligibility Checking and Assignment Queueing
Checks platform compatibility, daily limits, and queues assignments.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


class EligibilityCheckError(Exception):
    """Raised when eligibility check fails"""
    pass


class ClipEligibilityChecker:
    """Validates clip eligibility for posting."""

    def __init__(self, db: Session):
        """
        Initialize eligibility checker.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def check_platform_compatibility(self, clip_id: int, target_platform: str) -> Tuple[bool, str]:
        """
        Check if clip is compatible with target platform.

        Args:
            clip_id: ID of clip
            target_platform: Target platform name

        Returns:
            (is_compatible, reason): tuple of bool and reason string
        """
        from suno.common.models import Clip

        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return False, "Clip not found"

        if not clip.platform_eligible:
            return False, "Clip marked as not platform eligible"

        # Platform-specific rules
        source = clip.source_platform.lower()
        target = target_platform.lower()

        # TikTok → all platforms
        if source == "tiktok":
            return True, "TikTok clips compatible with all platforms"

        # Instagram Reels → all platforms
        if source == "instagram_reels":
            return True, "Instagram Reels compatible with all platforms"

        # YouTube Shorts → all platforms
        if source == "youtube_shorts":
            return True, "YouTube Shorts compatible with all platforms"

        # Twitter → text-based platforms
        if source == "twitter":
            if target in ["twitter", "threads", "bluesky"]:
                return True, "Twitter compatible with text-based platforms"
            return False, "Twitter clips only compatible with text-based platforms"

        # LinkedIn video → LinkedIn only
        if source == "linkedin":
            if target == "linkedin":
                return True, "LinkedIn video compatible with LinkedIn"
            return False, "LinkedIn videos only compatible with LinkedIn"

        # Default: incompatible
        return False, f"No compatibility rule between {source} and {target}"

    def check_daily_limit(self, account_id: int, tier_id: int) -> Tuple[bool, int]:
        """
        Check if account has reached daily clip limit.

        Args:
            account_id: ID of account
            tier_id: ID of tier

        Returns:
            (can_post, remaining): tuple of bool and remaining clips today
        """
        from suno.common.models import Tier, Membership, PostJob
        from suno.common.enums import JobLifecycle

        # Get tier limits
        tier = self.db.query(Tier).filter(Tier.id == tier_id).first()
        if not tier:
            return False, 0

        max_daily = tier.max_daily_clips

        # Count posts created today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = self.db.query(func.count(PostJob.id)).filter(
            PostJob.account_id == account_id,
            PostJob.created_at >= today_start,
            PostJob.status.in_([JobLifecycle.PENDING, JobLifecycle.PROCESSING, JobLifecycle.SUCCEEDED])
        ).scalar() or 0

        remaining = max_daily - today_count
        can_post = remaining > 0

        logger.info(f"Account {account_id}: {today_count}/{max_daily} posts today, {remaining} remaining")
        return can_post, remaining

    def check_platform_quota(self, account_id: int, target_platform: str) -> Tuple[bool, int]:
        """
        Check if account has reached platform-specific posting limit today.

        Args:
            account_id: ID of account
            target_platform: Target platform name

        Returns:
            (can_post, remaining): tuple of bool and remaining posts for platform today
        """
        from suno.common.models import PostJob
        from suno.common.enums import JobLifecycle

        # Platform-specific limits (per account per day)
        PLATFORM_LIMITS = {
            "tiktok": 5,
            "instagram": 3,
            "youtube": 2,
            "twitter": 10,
            "threads": 5,
            "bluesky": 5,
            "linkedin": 2,
        }

        limit = PLATFORM_LIMITS.get(target_platform.lower(), 5)

        # Count posts to this platform today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        platform_count = self.db.query(func.count(PostJob.id)).filter(
            PostJob.account_id == account_id,
            PostJob.target_platform == target_platform,
            PostJob.created_at >= today_start,
            PostJob.status.in_([JobLifecycle.PENDING, JobLifecycle.PROCESSING, JobLifecycle.SUCCEEDED])
        ).scalar() or 0

        remaining = limit - platform_count
        can_post = remaining > 0

        logger.info(f"Account {account_id} on {target_platform}: {platform_count}/{limit} posts today, {remaining} remaining")
        return can_post, remaining

    def check_content_maturity(self, clip_id: int, target_platform: str) -> Tuple[bool, str]:
        """
        Check if clip is mature enough (has metadata, good engagement) to post.

        Args:
            clip_id: ID of clip
            target_platform: Target platform

        Returns:
            (is_mature, reason): tuple of bool and reason
        """
        from suno.common.models import Clip

        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return False, "Clip not found"

        # Clips must have title and description
        if not clip.title or not clip.description:
            return False, "Clip missing title or description"

        # Engagement score must be reasonable (0.0-1.0 where higher is better)
        if clip.engagement_score < 0.1:
            return False, f"Clip engagement score too low: {clip.engagement_score}"

        # Must have been seen at least once
        if clip.view_count < 1:
            return False, "Clip has no view count"

        return True, "Clip has sufficient maturity"

    def get_full_eligibility(self, clip_id: int, account_id: int, target_platform: str) -> Dict:
        """
        Get complete eligibility assessment for clip → account → platform.

        Args:
            clip_id: ID of clip
            account_id: ID of account
            target_platform: Target platform

        Returns:
            Dict with all eligibility checks and overall verdict
        """
        from suno.common.models import Account

        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return {
                "eligible": False,
                "reason": "Account not found",
                "checks": {}
            }

        checks = {}

        # Platform compatibility
        compat, compat_reason = self.check_platform_compatibility(clip_id, target_platform)
        checks["platform_compatibility"] = {"passed": compat, "reason": compat_reason}

        if not compat:
            return {
                "eligible": False,
                "reason": f"Platform compatibility failed: {compat_reason}",
                "checks": checks
            }

        # Daily limit
        daily_ok, daily_remaining = self.check_daily_limit(account_id, account.membership.tier_id)
        checks["daily_limit"] = {"passed": daily_ok, "remaining": daily_remaining}

        if not daily_ok:
            return {
                "eligible": False,
                "reason": "Daily posting limit reached",
                "checks": checks
            }

        # Platform quota
        platform_ok, platform_remaining = self.check_platform_quota(account_id, target_platform)
        checks["platform_quota"] = {"passed": platform_ok, "remaining": platform_remaining}

        if not platform_ok:
            return {
                "eligible": False,
                "reason": f"Platform {target_platform} quota reached",
                "checks": checks
            }

        # Content maturity
        mature, mature_reason = self.check_content_maturity(clip_id, target_platform)
        checks["content_maturity"] = {"passed": mature, "reason": mature_reason}

        if not mature:
            return {
                "eligible": False,
                "reason": f"Content maturity check failed: {mature_reason}",
                "checks": checks
            }

        return {
            "eligible": True,
            "reason": "All checks passed",
            "checks": checks
        }


class AssignmentQueueManager:
    """Manages clip-to-account-platform assignments and queueing."""

    def __init__(self, db: Session):
        """
        Initialize assignment queue manager.

        Args:
            db: SQLAlchemy session
        """
        self.db = db
        self.eligibility = ClipEligibilityChecker(db)

    def create_assignments(self, clip_id: int, account_ids: List[int], target_platforms: List[str]) -> Dict:
        """
        Create clip assignments for specified accounts and platforms.

        Args:
            clip_id: ID of clip
            account_ids: List of account IDs to assign to
            target_platforms: List of target platforms

        Returns:
            Stats dict with assignment_count, skipped_count, error_count
        """
        from suno.common.models import Clip, ClipAssignment, Account
        from suno.common.enums import ClipLifecycle

        stats = {"created": 0, "skipped": 0, "errors": 0}

        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            logger.error(f"Clip {clip_id} not found")
            return stats

        for account_id in account_ids:
            account = self.db.query(Account).filter(Account.id == account_id).first()
            if not account:
                logger.warning(f"Account {account_id} not found, skipping")
                stats["skipped"] += 1
                continue

            # Check automation enabled
            if not account.automation_enabled:
                logger.info(f"Account {account_id} automation disabled, skipping")
                stats["skipped"] += 1
                continue

            for target_platform in target_platforms:
                try:
                    # Check eligibility
                    eligibility = self.eligibility.get_full_eligibility(clip_id, account_id, target_platform)
                    if not eligibility["eligible"]:
                        logger.info(f"Clip {clip_id} → account {account_id} → {target_platform} ineligible: {eligibility['reason']}")
                        stats["skipped"] += 1
                        continue

                    # Check if assignment already exists
                    existing = self.db.query(ClipAssignment).filter(
                        ClipAssignment.clip_id == clip_id,
                        ClipAssignment.account_id == account_id,
                        ClipAssignment.target_platform == target_platform
                    ).first()

                    if existing:
                        logger.info(f"Assignment already exists for clip {clip_id} → account {account_id} → {target_platform}")
                        stats["skipped"] += 1
                        continue

                    # Create assignment
                    assignment = ClipAssignment(
                        clip_id=clip_id,
                        account_id=account_id,
                        target_platform=target_platform,
                        status="eligible",
                        priority=self._calculate_priority(clip, account_id, target_platform)
                    )
                    self.db.add(assignment)
                    self.db.commit()

                    logger.info(f"Created assignment: clip {clip_id} → account {account_id} → {target_platform}")
                    stats["created"] += 1

                except Exception as e:
                    self.db.rollback()
                    logger.error(f"Error creating assignment: {e}")
                    stats["errors"] += 1

        logger.info(f"Assignment creation complete: {stats}")
        return stats

    def queue_for_caption_generation(self, assignment_ids: List[int]) -> Dict:
        """
        Queue assignments for caption generation.

        Args:
            assignment_ids: List of assignment IDs to queue

        Returns:
            Stats dict with queued_count, error_count
        """
        from suno.common.models import ClipAssignment, CaptionJob
        from suno.common.enums import ClipLifecycle, JobLifecycle

        stats = {"queued": 0, "errors": 0}

        for assignment_id in assignment_ids:
            try:
                assignment = self.db.query(ClipAssignment).filter(
                    ClipAssignment.id == assignment_id
                ).first()

                if not assignment:
                    logger.warning(f"Assignment {assignment_id} not found")
                    continue

                # Update assignment status
                assignment.status = "queued"
                self.db.commit()

                # Create caption generation job
                job = CaptionJob(
                    assignment_id=assignment_id,
                    status=JobLifecycle.PENDING
                )
                self.db.add(job)
                self.db.commit()

                logger.info(f"Queued assignment {assignment_id} for caption generation")
                stats["queued"] += 1

            except Exception as e:
                self.db.rollback()
                logger.error(f"Error queuing assignment {assignment_id}: {e}")
                stats["errors"] += 1

        logger.info(f"Caption job queueing complete: {stats}")
        return stats

    @staticmethod
    def _calculate_priority(clip, account_id: int, target_platform: str) -> int:
        """
        Calculate priority for assignment (higher = process first).

        Factors:
        - Engagement score (trending clips get higher priority)
        - Platform (TikTok > Instagram > YouTube > others)
        - Time (older clips get lower priority)

        Args:
            clip: Clip object
            account_id: Account ID (unused, for future extensions)
            target_platform: Target platform name

        Returns:
            Priority score (0-100)
        """
        priority = 0

        # Engagement score (0-30 points)
        priority += int(clip.engagement_score * 30)

        # Platform weighting (0-30 points)
        platform_weights = {
            "tiktok": 30,
            "instagram": 25,
            "youtube": 20,
            "twitter": 15,
            "threads": 15,
            "bluesky": 15,
            "linkedin": 10,
        }
        priority += platform_weights.get(target_platform.lower(), 10)

        # Age factor (0-40 points, newer = higher)
        age_hours = (datetime.utcnow() - clip.created_at).total_seconds() / 3600
        age_points = max(0, 40 - min(40, age_hours / 6))  # 6 hours per point, max 40
        priority += int(age_points)

        return min(100, priority)  # Cap at 100
