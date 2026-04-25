"""
Operator Dashboard API
Real-time system health and control interface for operators.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


class OperatorDashboard:
    """Operator dashboard with system health and control capabilities."""

    def __init__(self, db: Session):
        """Initialize operator dashboard."""
        self.db = db

    def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health snapshot.

        Returns:
            Dict with health metrics across all subsystems
        """
        from suno.common.models import (
            User, Membership, Account, Campaign, Clip,
            ClipAssignment, CaptionJob, PostJob, SubmissionJob,
            DeadLetterJob, WebhookEvent, AuditLog
        )
        from suno.common.enums import MembershipLifecycle, JobLifecycle
        from sqlalchemy import and_

        # Timestamp
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        hour_ago = now - timedelta(hours=1)

        # Active members (count unique users with active memberships)
        from sqlalchemy.orm import aliased
        active_members = self.db.query(func.count(User.id.distinct())).join(
            Membership, User.id == Membership.user_id
        ).filter(
            Membership.status == MembershipLifecycle.ACTIVE
        ).scalar() or 0

        active_memberships = self.db.query(func.count(Membership.id)).filter(
            Membership.status == MembershipLifecycle.ACTIVE
        ).scalar() or 0
        active_accounts = self.db.query(func.count(Account.id)).filter(
            Account.automation_enabled == True
        ).scalar() or 0

        # Campaign stats
        total_campaigns = self.db.query(func.count(Campaign.id)).scalar() or 0
        total_clips = self.db.query(func.count(Clip.id)).scalar() or 0
        pending_clips = self.db.query(func.count(Clip.id)).filter(
            Clip.available == True
        ).scalar() or 0

        # Job queue depths
        pending_captions = self.db.query(func.count(CaptionJob.id)).filter(
            CaptionJob.status == JobLifecycle.PENDING
        ).scalar() or 0
        pending_posts = self.db.query(func.count(PostJob.id)).filter(
            PostJob.status == JobLifecycle.PENDING
        ).scalar() or 0
        pending_submissions = self.db.query(func.count(SubmissionJob.id)).filter(
            SubmissionJob.status == JobLifecycle.PENDING
        ).scalar() or 0

        # Failures & dead-letter
        failed_jobs = self.db.query(func.count(CaptionJob.id)).filter(
            CaptionJob.status == JobLifecycle.FAILED
        ).scalar() or 0
        failed_jobs += self.db.query(func.count(PostJob.id)).filter(
            PostJob.status == JobLifecycle.FAILED
        ).scalar() or 0

        dead_letter = self.db.query(func.count(DeadLetterJob.id)).scalar() or 0

        # Webhook health
        from suno.billing.webhook_events import WebhookEventStatus

        pending_webhooks = self.db.query(func.count(WebhookEvent.id)).filter(
            WebhookEvent.status.in_([
                WebhookEventStatus.RECEIVED,
                WebhookEventStatus.VALIDATED,
                WebhookEventStatus.ENQUEUED,
            ])
        ).scalar() or 0
        webhook_failures = self.db.query(func.count(WebhookEvent.id)).filter(
            WebhookEvent.status.in_([
                WebhookEventStatus.FAILED,
                WebhookEventStatus.DEAD_LETTER,
            ])
        ).scalar() or 0

        # Recent activity
        recent_posts = self.db.query(func.count(PostJob.id)).filter(
            PostJob.posted_at >= hour_ago
        ).scalar() or 0
        recent_captions = self.db.query(func.count(CaptionJob.id)).filter(
            CaptionJob.status == JobLifecycle.SUCCEEDED,
            CaptionJob.updated_at >= hour_ago
        ).scalar() or 0

        # Error rate
        recent_total = self.db.query(func.count(PostJob.id)).filter(
            PostJob.created_at >= day_ago
        ).scalar() or 1
        recent_succeeded = self.db.query(func.count(PostJob.id)).filter(
            PostJob.status == JobLifecycle.SUCCEEDED,
            PostJob.created_at >= day_ago
        ).scalar() or 0
        success_rate = (recent_succeeded / recent_total * 100) if recent_total > 0 else 0

        return {
            "timestamp": now.isoformat(),
            "system_status": "healthy" if dead_letter < 5 else "warning" if dead_letter < 20 else "critical",
            "members": {
                "total_users": active_members,
                "active_memberships": active_memberships,
                "active_accounts": active_accounts,
            },
            "content": {
                "campaigns": total_campaigns,
                "clips": total_clips,
                "pending_clips": pending_clips,
            },
            "queues": {
                "pending_captions": pending_captions,
                "pending_posts": pending_posts,
                "pending_submissions": pending_submissions,
                "failed_jobs": failed_jobs,
                "dead_letter": dead_letter,
            },
            "webhooks": {
                "pending": pending_webhooks,
                "failures": webhook_failures,
            },
            "activity_1h": {
                "posts": recent_posts,
                "captions": recent_captions,
            },
            "metrics_24h": {
                "success_rate": f"{success_rate:.1f}%",
                "total_posts": recent_total,
                "succeeded": recent_succeeded,
            },
        }

    def get_queue_status(self) -> Dict[str, int]:
        """Get detailed queue status."""
        from suno.common.models import CaptionJob, PostJob, SubmissionJob
        from suno.common.enums import JobLifecycle

        return {
            "caption_pending": self.db.query(func.count(CaptionJob.id)).filter(
                CaptionJob.status == JobLifecycle.PENDING
            ).scalar() or 0,
            "caption_processing": self.db.query(func.count(CaptionJob.id)).filter(
                CaptionJob.status == JobLifecycle.PROCESSING
            ).scalar() or 0,
            "post_pending": self.db.query(func.count(PostJob.id)).filter(
                PostJob.status == JobLifecycle.PENDING
            ).scalar() or 0,
            "post_processing": self.db.query(func.count(PostJob.id)).filter(
                PostJob.status == JobLifecycle.PROCESSING
            ).scalar() or 0,
            "submission_pending": self.db.query(func.count(SubmissionJob.id)).filter(
                SubmissionJob.status == JobLifecycle.PENDING
            ).scalar() or 0,
        }

    def get_recent_failures(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent failures for operator review."""
        from suno.common.models import DeadLetterJob

        jobs = self.db.query(DeadLetterJob).order_by(
            DeadLetterJob.created_at.desc()
        ).limit(limit).all()

        return [
            {
                "id": job.id,
                "type": job.original_job_type,
                "error": job.error_message,
                "retries": job.retry_count,
                "created": job.created_at.isoformat(),
                "payload": job.payload,
            }
            for job in jobs
        ]

    def get_member_status(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get status of active members."""
        from suno.common.models import Membership, Account, User
        from suno.common.enums import MembershipLifecycle

        memberships = self.db.query(Membership).filter(
            Membership.status == MembershipLifecycle.ACTIVE
        ).order_by(Membership.created_at.desc()).limit(limit).all()

        return [
            {
                "membership_id": m.id,
                "user_email": m.user.email,
                "tier": m.tier.name.value,
                "automation": m.account.automation_enabled if m.account else False,
                "created": m.created_at.isoformat(),
            }
            for m in memberships
        ]

    def pause_account(self, account_id: int, reason: str = "") -> bool:
        """Pause account automation."""
        from suno.common.models import Account

        try:
            account = self.db.query(Account).filter(Account.id == account_id).first()
            if not account:
                return False

            account.automation_enabled = False
            self.db.commit()

            logger.warning(f"Account {account_id} paused. Reason: {reason}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error pausing account: {e}")
            return False

    def resume_account(self, account_id: int) -> bool:
        """Resume account automation."""
        from suno.common.models import Account

        try:
            account = self.db.query(Account).filter(Account.id == account_id).first()
            if not account:
                return False

            account.automation_enabled = True
            self.db.commit()

            logger.info(f"Account {account_id} resumed")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error resuming account: {e}")
            return False

    def force_revoke_user(self, user_id: int, reason: str = "") -> bool:
        """Force revoke user and all accounts."""
        from suno.common.models import User, Membership, Account
        from suno.common.enums import MembershipLifecycle

        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return False

            # Revoke all memberships
            memberships = self.db.query(Membership).filter(
                Membership.user_id == user_id
            ).all()

            for m in memberships:
                m.status = MembershipLifecycle.REVOKED
                m.revoked_at = datetime.utcnow()

                # Disable associated accounts
                if m.account:
                    m.account.automation_enabled = False

            self.db.commit()

            logger.warning(f"User {user_id} force revoked. Reason: {reason}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error revoking user: {e}")
            return False
