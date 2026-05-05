"""
PHASE 1: SQLAlchemy ORM models for SUNO rebuild.
Core data models for the autonomous clip automation system.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey,
    Text, JSON, Float, Enum as SQLEnum, UniqueConstraint,
    Index, Table, Numeric, VARCHAR
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from suno.common.enums import (
    MembershipLifecycle, ClipLifecycle, JobLifecycle, TierName, AccountStatus,
    VariantType, VariantStatus
)

# Use the shared database Base from db.engine
from db.engine import Base


class User(Base):
    """User account in system."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # For email/password auth
    whop_user_id = Column(String(255), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memberships = relationship("Membership", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_whop_id", "whop_user_id"),
    )


class Tier(Base):
    """Service tier (Starter, Pro)."""
    __tablename__ = "tiers"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    max_daily_clips = Column(Integer, nullable=False)
    max_platforms = Column(Integer, nullable=False)
    platforms = Column(JSON, nullable=False)  # List[str]
    auto_posting = Column(Boolean, default=False)
    scheduling = Column(Boolean, default=False)
    analytics = Column(Boolean, default=False)
    api_access = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship("Membership", back_populates="tier")


class Membership(Base):
    """User's membership/subscription."""
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    tier_id = Column(Integer, ForeignKey("tiers.id"), nullable=False)
    whop_membership_id = Column(String(255), unique=True, nullable=False, index=True)
    whop_plan_id = Column(String(255), nullable=True, index=True)  # Track plan ID for tier discovery
    status = Column(String, nullable=False, default="ACTIVE")
    activated_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="memberships")
    tier = relationship("Tier", back_populates="memberships")
    account = relationship("Account", uselist=False, back_populates="membership")
    clips_today_count = Column(Integer, default=0)

    __table_args__ = (
        Index("idx_membership_user", "user_id"),
        Index("idx_membership_whop_id", "whop_membership_id"),
        UniqueConstraint("user_id", "whop_membership_id", name="uq_user_whop_membership"),
    )


class Account(Base):
    """SUNO workspace account for a membership."""
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    membership_id = Column(Integer, ForeignKey("memberships.id"), nullable=False, unique=True, index=True)
    workspace_id = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False)
    automation_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    membership = relationship("Membership", back_populates="account")
    clips = relationship("Clip", back_populates="account")
    creator_profile = relationship("CreatorProfile", uselist=False, back_populates="account")

    __table_args__ = (
        Index("idx_account_workspace", "workspace_id"),
    )


class CreatorProfile(Base):
    """Creator profile with style, tone, and niche preferences."""
    __tablename__ = "creator_profiles"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, unique=True, index=True)
    niche = Column(String(255), nullable=True)  # e.g. "fitness", "finance"
    tone = Column(String(100), nullable=True)  # e.g. "aggressive", "educational"
    content_style = Column(String(100), nullable=True)  # e.g. "talking head", "b-roll"
    hook_style = Column(String(100), nullable=True)  # e.g. "shock", "question", "story"
    avg_clip_length = Column(Integer, nullable=True)  # seconds
    do_not_use = Column(JSON, nullable=False, default=list)  # List[str]
    platform_focus = Column(JSON, nullable=False, default=list)  # List[str]
    winning_clip_ids = Column(JSON, nullable=False, default=list)  # List[int]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = relationship("Account", back_populates="creator_profile")

    __table_args__ = (
        Index("idx_creator_profile_account", "account_id"),
    )


class WebhookEvent(Base):
    """Raw webhook event storage with full lifecycle tracking."""
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True)
    whop_event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(50), default="received", nullable=False)  # received, validated, enqueued, processing, completed, failed, dead_letter
    job_id = Column(String(255), nullable=True, index=True)  # RQ job ID
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    processing_result = Column(JSON, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    validated_at = Column(DateTime, nullable=True)
    enqueued_at = Column(DateTime, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    dead_lettered_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_webhook_event_id", "whop_event_id"),
        Index("idx_webhook_status", "status"),
        Index("idx_webhook_job_id", "job_id"),
    )


class Campaign(Base):
    """Campaign containing clips to be posted."""
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True)
    whop_campaign_id = Column(String(255), nullable=True, index=True)
    name = Column(String(500), nullable=False)
    cpm = Column(Float, nullable=True)
    budget_remaining = Column(Float, nullable=True)
    is_free = Column(Boolean, default=False)
    drive_url = Column(String(2000), nullable=True)
    youtube_url = Column(String(2000), nullable=True)
    allowed_platforms = Column(Text, nullable=True)
    available = Column(Boolean, default=True)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    min_duration_seconds = Column(Integer, nullable=True)
    max_duration_seconds = Column(Integer, nullable=True)
    ideal_duration_seconds = Column(Integer, nullable=True)
    audience = Column(String(255), nullable=True)
    cta = Column(Text, nullable=True)
    forbidden_topics = Column(JSON, nullable=False, default=list)  # List[str]
    approval_required = Column(Boolean, default=False)

    clips = relationship("Clip", back_populates="campaign")


class Clip(Base):
    """Individual clip discovered/ingested from source."""
    __tablename__ = "clips"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True, index=True)
    source_url = Column(String(2000), nullable=False, unique=True, index=True)
    source_platform = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    creator = Column(String(255), nullable=True)
    view_count = Column(Integer, default=0)
    engagement_score = Column(Float, default=0.0)
    trending_category = Column(String(100), nullable=True)
    hashtags = Column(JSON, nullable=False, default=list)  # List[str]
    audio_source = Column(String(255), nullable=True)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String, nullable=False, default="discovered")
    platform_eligible = Column(Boolean, default=True)
    available = Column(Boolean, default=True)
    clip_metadata = Column(JSON, nullable=False, default=dict)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    hook_score = Column(Float, nullable=True)
    relevance_score = Column(Float, nullable=True)
    platform_fit_score = Column(Float, nullable=True)
    duration_score = Column(Float, nullable=True)
    brand_alignment_score = Column(Float, nullable=True)
    viral_score = Column(Float, nullable=True)
    social_proof_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)
    monetization_score = Column(Float, nullable=True)
    emotional_trigger_type = Column(String(50), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    hook_start_ms = Column(Integer, nullable=True)
    # Phase 8: Intelligence + Distribution Engine
    predicted_views = Column(Integer, nullable=True)
    estimated_value = Column(Float, nullable=True)
    ai_generation_cost_usd = Column(Float, nullable=True)
    ai_roi = Column(Float, nullable=True)
    predicted_watch_time = Column(Float, nullable=True)
    predicted_completion_rate = Column(Float, nullable=True)
    predicted_dropoff_ms = Column(Integer, nullable=True)
    posting_cooldown_hours = Column(Integer, default=2)

    campaign = relationship("Campaign", back_populates="clips")
    account = relationship("Account", back_populates="clips")
    assignments = relationship("ClipAssignment", back_populates="clip")
    post_jobs = relationship("PostJob", back_populates="clip")
    variants = relationship("ClipVariant", back_populates="clip", order_by="ClipVariant.created_at")
    performances = relationship("ClipPerformance", back_populates="clip")

    __table_args__ = (
        Index("idx_clip_campaign", "campaign_id"),
        Index("idx_clip_status", "status"),
        Index("idx_clip_content_hash", "content_hash"),
        Index("idx_clip_account_status", "account_id", "status"),
    )


class ClipAssignment(Base):
    """Assignment of clip to account/platform for posting."""
    __tablename__ = "clip_assignments"

    id = Column(Integer, primary_key=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    target_platform = Column(String(50), nullable=False)
    status = Column(String, nullable=False, default="eligible")
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clip = relationship("Clip", back_populates="assignments")
    account = relationship("Account")
    caption_jobs = relationship("CaptionJob", back_populates="assignment")

    __table_args__ = (
        Index("idx_assignment_clip", "clip_id"),
        Index("idx_assignment_account", "account_id"),
        Index("idx_assignment_status", "status"),
        UniqueConstraint("clip_id", "account_id", "target_platform", name="uq_assignment_clip_account_platform"),
    )


class CaptionJob(Base):
    """Job to generate captions for a clip assignment."""
    __tablename__ = "caption_jobs"

    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("clip_assignments.id"), nullable=False, index=True)
    status = Column(SQLEnum(JobLifecycle), default=JobLifecycle.PENDING, nullable=False)
    caption = Column(Text, nullable=True)
    hashtags = Column(JSON, nullable=True)  # List[str]
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignment = relationship("ClipAssignment", back_populates="caption_jobs")

    __table_args__ = (
        Index("idx_caption_job_assignment", "assignment_id"),
        Index("idx_caption_job_status", "status"),
    )


class PostJob(Base):
    """Job to post a clip to a platform."""
    __tablename__ = "post_jobs"

    id = Column(Integer, primary_key=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    target_platform = Column(String(50), nullable=False)
    status = Column(SQLEnum(JobLifecycle), default=JobLifecycle.PENDING, nullable=False)
    scheduled_for = Column(DateTime, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    posted_url = Column(String(2000), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clip = relationship("Clip", back_populates="post_jobs")
    account = relationship("Account")

    __table_args__ = (
        Index("idx_post_job_clip", "clip_id"),
        Index("idx_post_job_account", "account_id"),
        Index("idx_post_job_status", "status"),
        Index("idx_post_job_scheduled", "scheduled_for"),
    )


class ClipVariant(Base):
    """Clip variant (hook, caption, duration, subtitles) with signal tracking."""
    __tablename__ = "clip_variants"

    id = Column(Integer, primary_key=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False, index=True)
    variant_group_id = Column(String(64), nullable=True, index=True)
    variant_type = Column(SQLEnum(VariantType), nullable=False)
    content = Column(Text, nullable=False)
    model_used = Column(String(100), nullable=True)
    quality_tier = Column(String(20), nullable=True)  # "draft" or "elite"
    hook_type = Column(String(50), nullable=True)  # curiosity, controversial, emotional, authority
    predicted_engagement = Column(Float, nullable=True)  # 0.0-1.0
    status = Column(SQLEnum(VariantStatus), default=VariantStatus.DRAFT, nullable=False)
    signal_status = Column(String(20), default="pending", nullable=False)  # pending, strong, weak, paused
    scheduled_for = Column(DateTime, nullable=True)
    first_signal_at = Column(DateTime, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    posted_platform = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clip = relationship("Clip", back_populates="variants")

    __table_args__ = (
        Index("idx_variant_clip", "clip_id"),
        Index("idx_variant_status", "status"),
        Index("idx_variant_scheduled", "scheduled_for"),
        Index("idx_variant_group", "variant_group_id"),
    )


class ClipPerformance(Base):
    """Performance metrics recorded for a clip or variant."""
    __tablename__ = "clip_performances"

    id = Column(Integer, primary_key=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("clip_variants.id"), nullable=True, index=True)
    platform = Column(String(50), nullable=False, index=True)
    views = Column(Integer, default=0)
    watch_time_seconds = Column(Float, nullable=True)
    completion_rate = Column(Float, nullable=True)  # 0.0-1.0
    likes = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    revenue_estimate = Column(Float, nullable=True)
    recorded_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clip = relationship("Clip", back_populates="performances")

    __table_args__ = (
        Index("idx_perf_clip", "clip_id"),
        Index("idx_perf_variant", "variant_id"),
        Index("idx_perf_platform", "platform"),
    )


class SubmissionJob(Base):
    """Job to submit posted clip back to source."""
    __tablename__ = "submission_jobs"

    id = Column(Integer, primary_key=True)
    post_job_id = Column(Integer, ForeignKey("post_jobs.id"), nullable=False, unique=True, index=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False, index=True)
    source_platform = Column(String(50), nullable=False)
    status = Column(SQLEnum(JobLifecycle), default=JobLifecycle.PENDING, nullable=False)
    submission_url = Column(String(2000), nullable=True)
    submission_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_submission_post_job", "post_job_id"),
        Index("idx_submission_clip", "clip_id"),
        Index("idx_submission_status", "status"),
    )


class AuditLog(Base):
    """Audit trail for compliance."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    actor = Column(String(255), nullable=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_created", "created_at"),
    )


class DeadLetterJob(Base):
    """Failed jobs that couldn't be recovered."""
    __tablename__ = "dead_letter_jobs"

    id = Column(Integer, primary_key=True)
    original_job_type = Column(String(50), nullable=False)  # caption, post, submission
    original_job_id = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=False)
    error_message = Column(Text, nullable=False)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_dead_letter_job_type", "original_job_type"),
        Index("idx_dead_letter_created", "created_at"),
    )


class SafetyState(Base):
    """Persistent global safety state."""
    __tablename__ = "safety_state"

    id = Column(Integer, primary_key=True)
    is_global_paused = Column(Boolean, default=False, nullable=False)
    pause_reason = Column(String(500), nullable=True)
    paused_by = Column(String(255), nullable=True)  # "operator", "system", etc
    paused_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_safety_state_paused", "is_global_paused"),
    )
