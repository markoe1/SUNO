"""
Creator Registry
================
Management interface for creator approval/verification.

Functions:
- Discover creators from downloaded content
- Approve/block creators
- View creator stats
- Export/import creator lists
"""

import logging
from typing import List, Optional, Dict
from queue_manager import QueueManager, Creator

logger = logging.getLogger(__name__)


class CreatorRegistry:
    """Manage creator approvals and verification status."""

    def __init__(self):
        self.queue = QueueManager()

    def discover_creator(self, name: str, platform: str) -> Creator:
        """
        Discover a new creator (add to registry as unverified).

        Args:
            name: Creator/channel name
            platform: youtube, tiktok, instagram, etc

        Returns:
            Creator object
        """
        creator = self.queue.get_creator(name, platform)

        if creator:
            logger.info(f"Creator already in registry: {name} ({platform})")
            return creator

        # Create new unverified creator
        creator = Creator(
            name=name,
            platform=platform,
            is_approved=False,
            verification_status="unverified"
        )

        self.queue.upsert_creator(creator)
        logger.info(f"Discovered new creator: {name} ({platform})")
        return creator

    def approve_creator(self, name: str, platform: str, reason: str = "") -> bool:
        """
        Approve a creator for content extraction.

        Args:
            name: Creator name
            platform: youtube, tiktok, instagram, etc
            reason: Why approved (optional)

        Returns:
            True if approved successfully
        """
        # Ensure creator exists
        creator = self.queue.get_creator(name, platform)
        if not creator:
            self.discover_creator(name, platform)

        success = self.queue.approve_creator(name, platform, reason)

        if success:
            logger.info(f"Approved creator: {name} ({platform}). Reason: {reason or 'none'}")
        else:
            logger.warning(f"Failed to approve creator: {name} ({platform})")

        return success

    def block_creator(self, name: str, platform: str, reason: str = "") -> bool:
        """
        Block a creator from content extraction.

        Args:
            name: Creator name
            platform: youtube, tiktok, instagram, etc
            reason: Why blocked (e.g., "copyright violations", "explicit content")

        Returns:
            True if blocked successfully
        """
        # Ensure creator exists
        creator = self.queue.get_creator(name, platform)
        if not creator:
            self.discover_creator(name, platform)

        success = self.queue.block_creator(name, platform, reason)

        if success:
            logger.info(f"Blocked creator: {name} ({platform}). Reason: {reason or 'none'}")
        else:
            logger.warning(f"Failed to block creator: {name} ({platform})")

        return success

    def get_creator(self, name: str, platform: str) -> Optional[Creator]:
        """Get creator profile."""
        return self.queue.get_creator(name, platform)

    def list_approved_creators(self, platform: str = None) -> List[Creator]:
        """List all approved creators."""
        creators = self.queue.get_approved_creators(platform)
        logger.info(f"Found {len(creators)} approved creators")
        return creators

    def list_blocked_creators(self, platform: str = None) -> List[Creator]:
        """List all blocked creators."""
        creators = self.queue.get_blocked_creators(platform)
        logger.info(f"Found {len(creators)} blocked creators")
        return creators

    def get_creator_stats(self, name: str, platform: str) -> Optional[Dict]:
        """Get creator statistics."""
        creator = self.queue.get_creator(name, platform)
        if not creator:
            return None

        return {
            'name': creator.name,
            'platform': creator.platform,
            'status': 'approved' if creator.is_approved else creator.verification_status,
            'clips_extracted': creator.clips_extracted,
            'clips_posted': creator.clips_posted,
            'views_generated': creator.views_generated,
            'earnings_generated': creator.earnings_generated,
            'approval_reason': creator.approval_reason,
            'discovered_at': creator.discovered_at,
            'approved_at': creator.approved_at,
        }

    def print_creator_stats(self, name: str, platform: str):
        """Print creator statistics to logger."""
        stats = self.get_creator_stats(name, platform)
        if not stats:
            logger.info(f"Creator not found: {name} ({platform})")
            return

        logger.info(f"\n{'='*60}")
        logger.info(f"Creator: {stats['name']} ({stats['platform']})")
        logger.info(f"{'='*60}")
        logger.info(f"Status:            {stats['status']}")
        logger.info(f"Clips extracted:   {stats['clips_extracted']}")
        logger.info(f"Clips posted:      {stats['clips_posted']}")
        logger.info(f"Views generated:   {stats['views_generated']}")
        logger.info(f"Earnings generated:${stats['earnings_generated']:.2f}")
        logger.info(f"Approval reason:   {stats['approval_reason'] or 'none'}")
        logger.info(f"Discovered:        {stats['discovered_at']}")
        logger.info(f"Approved:          {stats['approved_at'] or 'not approved'}")
        logger.info(f"{'='*60}\n")

    def bulk_approve_creators(self, creators_list: List[Dict]) -> int:
        """
        Bulk approve creators from a list.

        Args:
            creators_list: List of {'name': str, 'platform': str, 'reason': str}

        Returns:
            Number of creators approved
        """
        approved = 0
        for item in creators_list:
            name = item.get('name')
            platform = item.get('platform', 'youtube')
            reason = item.get('reason', '')

            if name and self.approve_creator(name, platform, reason):
                approved += 1

        logger.info(f"Bulk approved {approved}/{len(creators_list)} creators")
        return approved

    def bulk_block_creators(self, creators_list: List[Dict]) -> int:
        """
        Bulk block creators from a list.

        Args:
            creators_list: List of {'name': str, 'platform': str, 'reason': str}

        Returns:
            Number of creators blocked
        """
        blocked = 0
        for item in creators_list:
            name = item.get('name')
            platform = item.get('platform', 'youtube')
            reason = item.get('reason', '')

            if name and self.block_creator(name, platform, reason):
                blocked += 1

        logger.info(f"Bulk blocked {blocked}/{len(creators_list)} creators")
        return blocked


def main():
    """Test creator registry."""
    logging.basicConfig(level=logging.INFO)

    registry = CreatorRegistry()

    # Test 1: Discover and approve a creator
    logger.info("=== TEST 1: Discover and approve creator ===")
    creator = registry.discover_creator("MrBeast", "youtube")
    logger.info(f"Discovered: {creator.name} ({creator.platform})")

    registry.approve_creator("MrBeast", "youtube", "Top-tier content creator")
    creator = registry.get_creator("MrBeast", "youtube")
    logger.info(f"Approved: {creator.is_approved}")

    # Test 2: Block a creator
    logger.info("\n=== TEST 2: Block creator ===")
    registry.discover_creator("FakeCreator", "tiktok")
    registry.block_creator("FakeCreator", "tiktok", "Copyright violations")
    creator = registry.get_creator("FakeCreator", "tiktok")
    logger.info(f"Blocked: {creator.verification_status == 'blocked'}")

    # Test 3: List approved creators
    logger.info("\n=== TEST 3: List approved creators ===")
    approved = registry.list_approved_creators()
    logger.info(f"Approved creators: {len(approved)}")
    for c in approved:
        logger.info(f"  - {c.name} ({c.platform})")

    # Test 4: Get stats
    logger.info("\n=== TEST 4: Creator stats ===")
    registry.print_creator_stats("MrBeast", "youtube")


if __name__ == "__main__":
    main()
