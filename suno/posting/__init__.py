"""Posting and submission orchestration for SUNO"""

from suno.posting.adapters import (
    PlatformAdapter,
    PostingResult,
    PostingStatus,
    get_adapter,
    get_supported_platforms,
    is_platform_supported,
)
from suno.posting.submission import SubmissionFlow, SubmissionStatus
from suno.posting.orchestrator import PostingOrchestrator

__all__ = [
    "PlatformAdapter",
    "PostingResult",
    "PostingStatus",
    "SubmissionFlow",
    "SubmissionStatus",
    "PostingOrchestrator",
    "get_adapter",
    "get_supported_platforms",
    "is_platform_supported",
]
