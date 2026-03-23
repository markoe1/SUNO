# Suno v2 Models - Clip Operator Platform
# These models extend the existing system to support client management

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, 
    String, Text, JSON, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.engine import Base
import uuid
from datetime import datetime, timezone
import enum


class ClientStatus(enum.Enum):
    LEAD = "LEAD"
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CHURNED = "CHURNED"


class ClipStatus(enum.Enum):
    RAW = "RAW"
    EDITING = "EDITING"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    POSTED = "POSTED"
    REJECTED = "REJECTED"


class Client(Base):
    """Creator/Client who pays for clip management services"""
    __tablename__ = "clients"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )  # The operator managing this client
    
    # Client info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=True)
    niche: Mapped[str] = mapped_column(String(100), nullable=True)  # fitness, finance, etc.
    status: Mapped[ClientStatus] = mapped_column(SQLEnum(ClientStatus), default=ClientStatus.LEAD)
    
    # Billing
    monthly_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1500.0)
    view_guarantee: Mapped[int] = mapped_column(Integer, nullable=False, default=1000000)
    clips_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    
    # Platform accounts
    tiktok_username: Mapped[str] = mapped_column(String(100), nullable=True)
    instagram_username: Mapped[str] = mapped_column(String(100), nullable=True)
    youtube_channel: Mapped[str] = mapped_column(String(255), nullable=True)
    
    # Content sources
    drive_folder: Mapped[str] = mapped_column(Text, nullable=True)
    content_notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Tracking
    onboarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    churned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    # Relationships
    clips: Mapped[list["ClientClip"]] = relationship(back_populates="client")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="client")
    performance_reports: Mapped[list["PerformanceReport"]] = relationship(back_populates="client")


class Editor(Base):
    """Clip editors in your team"""
    __tablename__ = "editors"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )  # The operator who manages this editor
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    rate_per_clip: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    
    # Performance metrics
    total_clips_edited: Mapped[int] = mapped_column(Integer, default=0)
    avg_turnaround_hours: Mapped[float] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, nullable=True)  # 0-5
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    # Relationships
    assigned_clips: Mapped[list["ClientClip"]] = relationship(back_populates="editor")


class ClientClip(Base):
    """Individual clips for clients (not campaigns)"""
    __tablename__ = "client_clips"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )
    editor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("editors.id"), nullable=True, index=True
    )

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    raw_file_path: Mapped[str] = mapped_column(Text, nullable=True)
    edited_file_path: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Status tracking
    status: Mapped[ClipStatus] = mapped_column(SQLEnum(ClipStatus), default=ClipStatus.RAW)
    
    # Posting
    tiktok_url: Mapped[str] = mapped_column(Text, nullable=True)
    instagram_url: Mapped[str] = mapped_column(Text, nullable=True)
    youtube_url: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Performance
    total_views: Mapped[int] = mapped_column(Integer, default=0)
    total_likes: Mapped[int] = mapped_column(Integer, default=0)
    total_comments: Mapped[int] = mapped_column(Integer, default=0)
    total_shares: Mapped[int] = mapped_column(Integer, default=0)
    
    # Metadata
    hook_used: Mapped[str] = mapped_column(Text, nullable=True)
    hashtags: Mapped[str] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    # Relationships
    client: Mapped["Client"] = relationship(back_populates="clips")
    editor: Mapped["Editor"] = relationship(back_populates="assigned_clips")


class Invoice(Base):
    """Monthly invoices for clients"""
    __tablename__ = "invoices"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )

    month: Mapped[str] = mapped_column(String(7), nullable=False)  # "2024-03"
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Performance bonus
    base_amount: Mapped[float] = mapped_column(Float, nullable=False, default=1500.0)
    performance_bonus: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    # Metrics
    clips_delivered: Mapped[int] = mapped_column(Integer, nullable=False)
    total_views: Mapped[int] = mapped_column(Integer, nullable=False)
    view_guarantee_met: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Payment
    whop_transaction_id: Mapped[str] = mapped_column(String(255), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    # Relationships
    client: Mapped["Client"] = relationship(back_populates="invoices")


class PerformanceReport(Base):
    """Weekly/Monthly performance reports for clients"""
    __tablename__ = "performance_reports"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "weekly" or "monthly"
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Metrics
    total_clips: Mapped[int] = mapped_column(Integer, default=0)
    total_views: Mapped[int] = mapped_column(Integer, default=0)
    total_likes: Mapped[int] = mapped_column(Integer, default=0)
    total_comments: Mapped[int] = mapped_column(Integer, default=0)
    total_shares: Mapped[int] = mapped_column(Integer, default=0)
    
    # Top performers
    top_clips_json: Mapped[dict] = mapped_column(JSON, nullable=True)  # [{clip_id, views, url}]
    best_hooks_json: Mapped[dict] = mapped_column(JSON, nullable=True)  # [{hook, avg_views}]
    
    # Insights
    insights_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    # Relationships
    client: Mapped["Client"] = relationship(back_populates="performance_reports")


class ClipTemplate(Base):
    """Reusable templates and hooks that work"""
    __tablename__ = "clip_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    niche: Mapped[str] = mapped_column(String(100), nullable=True)

    hook_text: Mapped[str] = mapped_column(Text, nullable=False)
    structure_notes: Mapped[str] = mapped_column(Text, nullable=True)

    # Performance
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    avg_views: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))


class ClientPortalToken(Base):
    """Magic-link tokens for client portal access.

    Operator generates a token → sends portal invite link to client.
    Client clicks the link → gets a client_access_token JWT cookie.
    Tokens expire after 7 days; each access generates a fresh JWT.
    """
    __tablename__ = "client_portal_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    # SHA-256 hash of the random URL-safe token (never store plaintext)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    client: Mapped["Client"] = relationship()