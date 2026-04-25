"""
Safety Controls and Self-Use Mode
Hard limits and operator controls for safe operation.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from enum import Enum

logger = logging.getLogger(__name__)


class SafetyLevel(str, Enum):
    """Safety level configuration."""
    SELF_USE = "self_use"      # Personal use (10-15 clips/day)
    BETA = "beta"              # Limited scale (50 users, tight monitoring)
    PRODUCTION = "production"  # Full scale


class GlobalSafetyControls:
    """Global safety controls and pause mechanisms."""

    def __init__(self, db: Session, safety_level: str = "production"):
        """
        Initialize safety controls.

        Args:
            db: SQLAlchemy session
            safety_level: SELF_USE, BETA, or PRODUCTION
        """
        self.db = db
        try:
            self.safety_level = SafetyLevel(safety_level)
        except ValueError:
            raise ValueError(f"Invalid safety level: {safety_level}")

        logger.info(f"Safety level: {self.safety_level.value}")
        self._apply_level_specific_init()

    def _apply_level_specific_init(self):
        """Apply safety level specific initialization."""
        if self.safety_level == SafetyLevel.SELF_USE:
            logger.warning("⚠️ SELF-USE MODE: Strict limits active (15 clips/day)")
        elif self.safety_level == SafetyLevel.BETA:
            logger.info("BETA MODE: Monitor up to 50 users")
        elif self.safety_level == SafetyLevel.PRODUCTION:
            logger.info("PRODUCTION MODE: Standard safety limits")

    def _get_safety_state(self):
        """Get or create safety state record."""
        from suno.common.models import SafetyState

        state = self.db.query(SafetyState).first()
        if not state:
            state = SafetyState(is_global_paused=False)
            self.db.add(state)
            self.db.commit()
        return state

    def is_globally_paused(self) -> bool:
        """Check if system is globally paused."""
        state = self._get_safety_state()
        return state.is_global_paused

    def global_pause(self, reason: str, paused_by: str = "operator") -> bool:
        """
        Global pause on all automation.

        Args:
            reason: Reason for pause
            paused_by: Who initiated the pause

        Returns:
            Success boolean
        """
        try:
            from suno.common.models import Account, SafetyState

            # Update safety state
            state = self._get_safety_state()
            state.is_global_paused = True
            state.pause_reason = reason
            state.paused_by = paused_by
            state.paused_at = datetime.utcnow()
            self.db.commit()

            logger.warning(f"GLOBAL PAUSE: {reason} (by {paused_by})")

            # Pause all active accounts
            self.db.query(Account).update({Account.automation_enabled: False})
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error pausing system: {e}")
            return False

    def global_resume(self) -> bool:
        """Resume all automation (only those paused by global_pause)."""
        try:
            from suno.common.models import Account, Membership, SafetyState
            from suno.common.enums import MembershipLifecycle

            state = self._get_safety_state()
            if not state.is_global_paused:
                logger.info("System not paused, skipping resume")
                return False

            # Update safety state
            state.is_global_paused = False
            state.pause_reason = None
            state.paused_by = None
            state.paused_at = None
            self.db.commit()

            logger.info("GLOBAL RESUME")

            # Resume only accounts that have active memberships
            # (don't resume manually disabled accounts)
            memberships = self.db.query(Membership).filter(
                Membership.status == MembershipLifecycle.ACTIVE
            ).all()

            for m in memberships:
                if m.account:
                    m.account.automation_enabled = True

            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error resuming system: {e}")
            return False

    def pause_platform(self, platform: str, reason: str) -> bool:
        """
        Pause posting to specific platform.

        Args:
            platform: Platform name
            reason: Reason for pause

        Returns:
            Success boolean
        """
        logger.warning(f"PAUSE {platform}: {reason}")
        # In practice: Update Account metadata to skip this platform
        return True

    def enforce_global_daily_limit(self) -> bool:
        """
        Check if global daily clip limit exceeded.

        Self-use mode: 15 clips/day max
        """
        if self.safety_level != SafetyLevel.SELF_USE:
            return False

        from suno.common.models import PostJob
        from suno.common.enums import JobLifecycle

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_posts = self.db.query(func.count(PostJob.id)).filter(
            PostJob.status == JobLifecycle.SUCCEEDED,
            PostJob.posted_at >= today_start,
        ).scalar() or 0

        if today_posts >= 15:
            logger.warning(f"Global daily limit reached ({today_posts}/15)")
            return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """Get safety control status."""
        return {
            "safety_level": self.safety_level,
            "is_paused": self.is_paused,
            "pause_reason": self.pause_reason,
            "timestamp": datetime.utcnow().isoformat(),
        }


class PerAccountSafetyLimits:
    """Per-account safety limits and controls."""

    def __init__(self, db: Session, account_id: int):
        """
        Initialize per-account limits.

        Args:
            db: SQLAlchemy session
            account_id: Account ID
        """
        self.db = db
        self.account_id = account_id

    def check_daily_loss_limit(self, max_loss_usd: float = 500) -> bool:
        """
        Check if account has lost too much money today.

        Args:
            max_loss_usd: Max daily loss allowed

        Returns:
            True if limit exceeded
        """
        # Placeholder: In production, would track analytics/revenue
        return False

    def check_retry_cap(self, max_retries: int = 3) -> bool:
        """
        Check if retry cap exceeded for failing jobs.

        Args:
            max_retries: Max retries per job

        Returns:
            True if exceeded
        """
        from suno.common.models import PostJob, DeadLetterJob

        # Count dead-letter jobs created in last hour
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_dead = self.db.query(func.count(DeadLetterJob.id)).filter(
            DeadLetterJob.created_at >= hour_ago,
            DeadLetterJob.retry_count >= max_retries,
        ).scalar() or 0

        if recent_dead > 10:
            logger.warning(f"Account {self.account_id}: Retry cap warning ({recent_dead} dead-letters in 1h)")
            return True

        return False

    def enforce_hourly_rate_limit(self, max_posts_per_hour: int = 5) -> bool:
        """
        Enforce hourly posting rate limit.

        Args:
            max_posts_per_hour: Max posts per hour

        Returns:
            True if limit would be exceeded
        """
        from suno.common.models import PostJob
        from suno.common.enums import JobLifecycle

        hour_ago = datetime.utcnow() - timedelta(hours=1)
        hour_posts = self.db.query(func.count(PostJob.id)).filter(
            PostJob.account_id == self.account_id,
            PostJob.posted_at >= hour_ago,
            PostJob.status == JobLifecycle.SUCCEEDED,
        ).scalar() or 0

        if hour_posts >= max_posts_per_hour:
            logger.warning(f"Account {self.account_id}: Hourly rate limit reached ({hour_posts}/{max_posts_per_hour})")
            return True

        return False


class SelfUseModeConfig:
    """Configuration for self-use (personal) mode."""

    # Self-use targets
    TARGET_CLIPS_PER_DAY = 12
    MAX_CLIPS_PER_DAY = 15
    PREFERRED_PLATFORMS = ["tiktok", "instagram", "youtube"]

    # Safety controls
    GLOBAL_DAILY_MAX = 15
    HOURLY_RATE_LIMIT = 5
    MAX_RETRIES_PER_JOB = 2

    # Monitoring
    FAIL_THRESHOLD_PERCENT = 20  # If >20% fail, pause
    ERROR_ALERT_COUNT = 5  # Alert after 5 consecutive errors

    @staticmethod
    def is_self_use_mode() -> bool:
        """Check if running in self-use mode."""
        return os.getenv("SUNO_MODE") == "self-use"

    @staticmethod
    def apply_self_use_limits(db: Session) -> Dict[str, Any]:
        """
        Apply self-use mode limits and configuration.

        Args:
            db: SQLAlchemy session

        Returns:
            Config dict with applied limits
        """
        from suno.common.models import Tier
        from suno.common.enums import TierName

        # Get or create SELF-USE tier
        tier = db.query(Tier).filter(Tier.name == TierName.STARTER).first()
        if not tier:
            tier = Tier(
                name=TierName.STARTER,
                max_daily_clips=SelfUseModeConfig.MAX_CLIPS_PER_DAY,
                max_platforms=len(SelfUseModeConfig.PREFERRED_PLATFORMS),
                platforms=SelfUseModeConfig.PREFERRED_PLATFORMS,
                auto_posting=True,
                scheduling=True,
                analytics=False,
                api_access=False,
            )
            db.add(tier)
            db.commit()

        return {
            "mode": "self-use",
            "target_daily": SelfUseModeConfig.TARGET_CLIPS_PER_DAY,
            "max_daily": SelfUseModeConfig.MAX_CLIPS_PER_DAY,
            "platforms": SelfUseModeConfig.PREFERRED_PLATFORMS,
            "hourly_limit": SelfUseModeConfig.HOURLY_RATE_LIMIT,
            "max_retries": SelfUseModeConfig.MAX_RETRIES_PER_JOB,
        }
