"""
Customer Dashboard API
Account status, activity, and performance for customers.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


class CustomerDashboard:
    """Customer-facing dashboard with account and performance info."""

    def __init__(self, db: Session):
        """Initialize customer dashboard."""
        self.db = db

    def get_account_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get account status for user.

        Args:
            user_id: User ID

        Returns:
            Dict with account status, tier, automation status, etc.
        """
        from suno.common.models import User, Membership, Account, Tier
        from suno.common.enums import MembershipLifecycle

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}

        # Get active membership
        membership = self.db.query(Membership).filter(
            Membership.user_id == user_id,
            Membership.status == "active",
        ).first()

        if not membership:
            return {
                "status": "inactive",
                "message": "No active membership",
            }

        tier = membership.tier
        account = membership.account

        return {
            "status": "active",
            "tier": tier.name.value,
            "email": user.email,
            "automation_enabled": account.automation_enabled if account else False,
            "workspace_id": account.workspace_id if account else None,
            "created_at": membership.created_at.isoformat(),
            "features": {
                "max_daily_clips": tier.max_daily_clips,
                "max_platforms": tier.max_platforms,
                "auto_posting": tier.auto_posting,
                "scheduling": tier.scheduling,
                "analytics": tier.analytics,
                "api_access": tier.api_access,
            },
            "platforms": tier.platforms,
        }

    def get_activity(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """
        Get recent activity for user.

        Args:
            user_id: User ID
            days: Number of days to look back

        Returns:
            Dict with clip discovery, posting, submission stats
        """
        from suno.common.models import (
            Clip, ClipAssignment, PostJob, SubmissionJob,
            Account, Membership
        )
        from suno.common.enums import JobLifecycle

        # Get user's accounts
        memberships = self.db.query(Membership).filter(
            Membership.user_id == user_id
        ).all()
        account_ids = [m.account.id for m in memberships if m.account]

        cutoff = datetime.utcnow() - timedelta(days=days)

        # Clips discovered
        clips_discovered = self.db.query(func.count(Clip.id)).filter(
            Clip.created_at >= cutoff
        ).scalar() or 0

        # Clips assigned
        clips_assigned = self.db.query(func.count(ClipAssignment.id)).filter(
            ClipAssignment.account_id.in_(account_ids),
            ClipAssignment.created_at >= cutoff,
        ).scalar() or 0

        # Posts created
        posts_created = self.db.query(func.count(PostJob.id)).filter(
            PostJob.account_id.in_(account_ids),
            PostJob.created_at >= cutoff,
        ).scalar() or 0

        # Posts succeeded
        posts_succeeded = self.db.query(func.count(PostJob.id)).filter(
            PostJob.account_id.in_(account_ids),
            PostJob.status == JobLifecycle.SUCCEEDED,
            PostJob.posted_at >= cutoff,
        ).scalar() or 0

        # Submissions pending
        submissions_pending = self.db.query(func.count(SubmissionJob.id)).filter(
            SubmissionJob.created_at >= cutoff,
        ).scalar() or 0

        # Success rate
        success_rate = (posts_succeeded / posts_created * 100) if posts_created > 0 else 0

        return {
            "period_days": days,
            "clips_discovered": clips_discovered,
            "clips_assigned": clips_assigned,
            "posts_created": posts_created,
            "posts_succeeded": posts_succeeded,
            "success_rate": f"{success_rate:.1f}%",
            "submissions_pending": submissions_pending,
        }

    def get_daily_quota(self, user_id: int) -> Dict[str, Any]:
        """
        Get today's quota status.

        Args:
            user_id: User ID

        Returns:
            Dict with usage vs. limit
        """
        from suno.common.models import Membership, PostJob
        from suno.common.enums import MembershipLifecycle, JobLifecycle

        membership = self.db.query(Membership).filter(
            Membership.user_id == user_id,
            Membership.status == "active",
        ).first()

        if not membership or not membership.account:
            return {"error": "No active account"}

        tier = membership.tier
        account = membership.account
        max_daily = tier.max_daily_clips

        # Count posts created today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = self.db.query(func.count(PostJob.id)).filter(
            PostJob.account_id == account.id,
            PostJob.created_at >= today_start,
            PostJob.status.in_([
                JobLifecycle.PENDING,
                JobLifecycle.PROCESSING,
                JobLifecycle.SUCCEEDED,
            ]),
        ).scalar() or 0

        return {
            "max_daily_clips": max_daily,
            "used_today": today_count,
            "remaining": max(0, max_daily - today_count),
            "percentage": (today_count / max_daily * 100) if max_daily > 0 else 0,
        }

    def get_recent_posts(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent posted clips.

        Args:
            user_id: User ID
            limit: Max posts to return

        Returns:
            List of recent posts
        """
        from suno.common.models import Membership, PostJob

        # Get user's accounts
        memberships = self.db.query(Membership).filter(
            Membership.user_id == user_id
        ).all()
        account_ids = [m.account.id for m in memberships if m.account]

        posts = self.db.query(PostJob).filter(
            PostJob.account_id.in_(account_ids),
            PostJob.posted_at.isnot(None),
        ).order_by(PostJob.posted_at.desc()).limit(limit).all()

        return [
            {
                "id": p.id,
                "platform": p.target_platform,
                "posted_at": p.posted_at.isoformat(),
                "posted_url": p.posted_url,
                "status": p.status.value,
            }
            for p in posts
        ]

    def get_platform_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get platform-specific posting status.

        Args:
            user_id: User ID

        Returns:
            Dict with posts per platform
        """
        from suno.common.models import Membership, PostJob
        from suno.common.enums import JobLifecycle

        # Get user's accounts
        memberships = self.db.query(Membership).filter(
            Membership.user_id == user_id
        ).all()
        account_ids = [m.account.id for m in memberships if m.account]

        # Count posts by platform (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)

        platform_stats = {}
        for platform in ["tiktok", "instagram", "youtube", "twitter", "bluesky", "threads"]:
            count = self.db.query(func.count(PostJob.id)).filter(
                PostJob.account_id.in_(account_ids),
                PostJob.target_platform == platform,
                PostJob.created_at >= week_ago,
                PostJob.status == JobLifecycle.SUCCEEDED,
            ).scalar() or 0

            platform_stats[platform] = {
                "posts_7d": count,
            }

        return platform_stats

    def get_warnings(self, user_id: int) -> List[str]:
        """
        Get account warnings (issues needing attention).

        Args:
            user_id: User ID

        Returns:
            List of warning messages
        """
        from suno.common.models import Membership, Account, PostJob
        from suno.common.enums import MembershipLifecycle, JobLifecycle

        warnings = []

        # Check membership status
        membership = self.db.query(Membership).filter(
            Membership.user_id == user_id
        ).first()

        if not membership:
            warnings.append("No active membership")
            return warnings

        if membership.status != MembershipLifecycle.ACTIVE:
            warnings.append(f"Membership status: {membership.status.value}")

        # Check automation
        if membership.account and not membership.account.automation_enabled:
            warnings.append("Automation is disabled")

        # Check recent failures
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        failed_today = self.db.query(func.count(PostJob.id)).filter(
            PostJob.account_id == membership.account.id if membership.account else -1,
            PostJob.status == JobLifecycle.FAILED,
            PostJob.created_at >= today_start,
        ).scalar() or 0

        if failed_today > 0:
            warnings.append(f"{failed_today} posts failed today")

        return warnings
