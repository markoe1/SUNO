"""Platform adapters for posting to various social media platforms."""

import logging
from typing import Dict, Optional
from suno.posting.adapters.base import PlatformAdapter, PostingResult, PostingStatus
from suno.posting.adapters.tiktok import TikTokAdapter
from suno.posting.adapters.instagram import InstagramAdapter
from suno.posting.adapters.youtube import YouTubeAdapter
from suno.posting.adapters.twitter import TwitterAdapter
from suno.posting.adapters.bluesky import BlueSkyAdapter

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry of platform adapters."""

    def __init__(self):
        """Initialize adapter registry."""
        self.adapters: Dict[str, PlatformAdapter] = {
            "tiktok": TikTokAdapter(),
            "instagram": InstagramAdapter(),
            "youtube": YouTubeAdapter(),
            "twitter": TwitterAdapter(),
            "bluesky": BlueSkyAdapter(),
        }
        logger.info(f"Loaded {len(self.adapters)} platform adapters")

    def get_adapter(self, platform: str) -> Optional[PlatformAdapter]:
        """
        Get adapter for platform.

        Args:
            platform: Platform name (lowercase)

        Returns:
            PlatformAdapter or None if not found
        """
        adapter = self.adapters.get(platform.lower())
        if not adapter:
            logger.warning(f"No adapter found for platform: {platform}")
        return adapter

    def supported_platforms(self) -> list:
        """Get list of supported platforms."""
        return list(self.adapters.keys())

    def is_supported(self, platform: str) -> bool:
        """Check if platform is supported."""
        return platform.lower() in self.adapters


# Global registry
_registry = AdapterRegistry()


def get_adapter(platform: str) -> Optional[PlatformAdapter]:
    """Get adapter for platform from global registry."""
    return _registry.get_adapter(platform)


def get_supported_platforms() -> list:
    """Get list of all supported platforms."""
    return _registry.supported_platforms()


def is_platform_supported(platform: str) -> bool:
    """Check if platform is supported."""
    return _registry.is_supported(platform)


__all__ = [
    "PlatformAdapter",
    "PostingResult",
    "PostingStatus",
    "AdapterRegistry",
    "TikTokAdapter",
    "InstagramAdapter",
    "YouTubeAdapter",
    "TwitterAdapter",
    "BlueSkyAdapter",
    "get_adapter",
    "get_supported_platforms",
    "is_platform_supported",
]
