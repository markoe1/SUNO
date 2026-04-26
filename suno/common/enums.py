"""
PHASE 1: State machine enums for membership, clip, and job lifecycles.
"""

from enum import Enum


class MembershipLifecycle(str, Enum):
    """Membership state machine."""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    REVOKED = "revoked"


class ClipLifecycle(str, Enum):
    """Clip processing state machine."""
    DISCOVERED = "discovered"
    ELIGIBLE = "eligible"
    QUEUED = "queued"
    GENERATED = "generated"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    CAPTIONED = "captioned"
    SCHEDULED = "scheduled"
    POSTED = "posted"
    SUBMITTED = "submitted"
    TRACKED = "tracked"
    REJECTED = "rejected"
    FAILED = "failed"
    EXPIRED = "expired"


class JobLifecycle(str, Enum):
    """Background job state machine."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class TierName(str, Enum):
    """Tier types."""
    STARTER = "starter"
    PRO = "pro"


class AccountStatus(str, Enum):
    """Account status states."""
    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"
    DISABLED = "disabled"


class VariantType(str, Enum):
    """Clip variant types."""
    HOOK = "hook"
    CAPTION = "caption"
    DURATION = "duration"
    SUBTITLES = "subtitles"


class VariantStatus(str, Enum):
    """Clip variant lifecycle."""
    DRAFT = "draft"
    ELITE = "elite"
    ELECTED = "elected"
    POSTED = "posted"
    REJECTED = "rejected"
