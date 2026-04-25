"""
Base Platform Adapter Interface
Abstract base class for all platform posting adapters.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PostingStatus(str, Enum):
    """Result of a posting attempt."""
    SUCCESS = "success"
    RETRYABLE_ERROR = "retryable_error"
    PERMANENT_ERROR = "permanent_error"


@dataclass
class PostingResult:
    """Result of a posting attempt."""
    status: PostingStatus
    posted_url: Optional[str] = None
    post_id: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # Platform-specific data

    def is_success(self) -> bool:
        return self.status == PostingStatus.SUCCESS

    def is_retryable(self) -> bool:
        return self.status == PostingStatus.RETRYABLE_ERROR

    def is_permanent_failure(self) -> bool:
        return self.status == PostingStatus.PERMANENT_ERROR


class PlatformAdapter(ABC):
    """
    Abstract base class for platform posting adapters.

    Each platform (TikTok, Instagram, etc.) implements this interface
    to handle account validation, payload preparation, and posting.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Platform name (lowercase, unique)."""
        pass

    @abstractmethod
    def validate_account(self, account_credentials: Dict[str, str]) -> bool:
        """
        Validate that account credentials are valid and account is ready to post.

        Args:
            account_credentials: Platform-specific credentials (API key, token, etc.)

        Returns:
            True if account is valid and ready, False otherwise

        Raises:
            Exception if validation fails unexpectedly
        """
        pass

    @abstractmethod
    def prepare_payload(
        self,
        clip_url: str,
        caption: str,
        hashtags: list,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepare posting payload for platform.

        Args:
            clip_url: URL of clip video
            caption: Post caption/text
            hashtags: List of hashtags
            metadata: Additional metadata (duration, etc.)

        Returns:
            Platform-specific payload dict

        Raises:
            ValueError if payload cannot be prepared
        """
        pass

    @abstractmethod
    def post(
        self,
        account_credentials: Dict[str, str],
        payload: Dict[str, Any],
    ) -> PostingResult:
        """
        Post to platform.

        Args:
            account_credentials: Platform-specific credentials
            payload: Prepared payload from prepare_payload()

        Returns:
            PostingResult with status, posted_url, and error details

        Raises:
            Exception for unexpected errors
        """
        pass

    @abstractmethod
    def submit_result(
        self,
        account_credentials: Dict[str, str],
        posted_url: str,
        source_clip_url: str,
    ) -> bool:
        """
        Submit posted URL back to source platform (if supported).

        Args:
            account_credentials: Platform-specific credentials
            posted_url: URL of posted content
            source_clip_url: URL of original source clip

        Returns:
            True if submission successful, False otherwise

        Raises:
            Exception for unexpected errors
        """
        pass

    def _classify_error(self, error_code: int, error_message: str) -> PostingStatus:
        """
        Classify an error as retryable or permanent.

        Default implementation. Subclasses can override for platform-specific logic.

        Args:
            error_code: HTTP status code or platform error code
            error_message: Error message

        Returns:
            PostingStatus.RETRYABLE_ERROR or PostingStatus.PERMANENT_ERROR

        Rules:
        - 429 (rate limit): RETRYABLE
        - 503 (service unavailable): RETRYABLE
        - 5xx (server error): RETRYABLE
        - 401/403 (auth): PERMANENT
        - 400 (bad request): PERMANENT
        """
        if error_code in [429, 503, 502, 504]:
            return PostingStatus.RETRYABLE_ERROR
        elif error_code >= 500:
            return PostingStatus.RETRYABLE_ERROR
        elif error_code in [401, 403]:
            return PostingStatus.PERMANENT_ERROR
        elif error_code in [400, 404]:
            return PostingStatus.PERMANENT_ERROR
        else:
            # Assume retryable for unknown errors
            return PostingStatus.RETRYABLE_ERROR
