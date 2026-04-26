"""
Tier-based feature gating and limit checking.
Helpers for enforcing tier rules.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from suno.common.models import User, Membership, Tier
from suno.common.enums import MembershipLifecycle, TierName


def get_user_tier(user_id, db: Session) -> Tier:
    """Get user's current tier. Returns None if no active membership."""
    membership = db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.status == MembershipLifecycle.ACTIVE,
    ).first()

    if not membership:
        return None

    return db.query(Tier).filter(Tier.id == membership.tier_id).first()


def require_tier(user_id, minimum_tier: str, db: Session) -> bool:
    """Check if user has minimum tier level. Returns True if met, False otherwise."""
    tier = get_user_tier(user_id, db)

    if not tier:
        return False

    tier_hierarchy = {
        TierName.STARTER.value: 1,
        TierName.PRO.value: 2,
    }

    required_level = tier_hierarchy.get(minimum_tier, 0)
    user_level = tier_hierarchy.get(tier.name.value, 0)

    return user_level >= required_level


def get_tier_limits(tier_name: str) -> Dict[str, Any]:
    """Get tier limits configuration."""
    limits = {
        TierName.STARTER.value: {
            "max_daily_clips": 10,
            "max_platforms": 3,
            "features": {
                "scheduling": False,
                "analytics": False,
                "api_access": False,
                "auto_posting": False,
            }
        },
        TierName.PRO.value: {
            "max_daily_clips": 30,
            "max_platforms": 6,
            "features": {
                "scheduling": True,
                "analytics": True,
                "api_access": True,
                "auto_posting": True,
            }
        },
    }

    return limits.get(tier_name, {})


def can_create_clip(user_id, db: Session) -> tuple[bool, str]:
    """
    Check if user can create a new clip.
    Returns (can_create, reason).
    """
    membership = db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.status == MembershipLifecycle.ACTIVE,
    ).first()

    if not membership:
        return False, "No active membership"

    tier = db.query(Tier).filter(Tier.id == membership.tier_id).first()

    if not tier:
        return False, "Tier not found"

    if membership.clips_today_count >= tier.max_daily_clips:
        return False, f"Daily limit reached ({tier.max_daily_clips} clips)"

    return True, "OK"


def can_use_platform(user_id, platform: str, db: Session) -> tuple[bool, str]:
    """
    Check if user's tier supports a platform.
    Returns (can_use, reason).
    """
    tier = get_user_tier(user_id, db)

    if not tier:
        return False, "No active tier"

    if platform not in tier.platforms:
        return False, f"Platform '{platform}' not available in {tier.name.value} tier"

    return True, "OK"


def has_feature(user_id, feature: str, db: Session) -> bool:
    """Check if user's tier has access to a feature."""
    tier = get_user_tier(user_id, db)

    if not tier:
        return False

    feature_mapping = {
        "scheduling": tier.scheduling,
        "analytics": tier.analytics,
        "api_access": tier.api_access,
        "auto_posting": tier.auto_posting,
    }

    return feature_mapping.get(feature, False)
