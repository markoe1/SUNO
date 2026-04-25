#!/usr/bin/env python3
"""
Setup YouTube OAuth with proper scopes.
Handles YouTube re-authorization for Phase 11.

Usage:
  python setup_youtube_oauth.py                    # Normal auth
  python setup_youtube_oauth.py --force            # Force re-auth
  python setup_youtube_oauth.py --validate         # Check token
  python setup_youtube_oauth.py --reset            # Delete token and re-auth
"""

import sys
import logging
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

from suno.posting.youtube_oauth import YouTubeOAuthManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Setup YouTube OAuth")
    parser.add_argument("--force", action="store_true", help="Force re-authorization")
    parser.add_argument("--validate", action="store_true", help="Validate current token")
    parser.add_argument("--reset", action="store_true", help="Reset and re-authorize")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("YouTube OAuth Setup — Phase 11")
    logger.info("=" * 70)

    if args.validate:
        logger.info("\nValidating YouTube token...")
        if YouTubeOAuthManager.validate_scopes():
            logger.info("✓ Token is valid with proper scopes")
            return 0
        else:
            logger.error("✗ Token missing proper scopes")
            return 1

    if args.reset:
        logger.info("\nResetting YouTube token...")
        creds = YouTubeOAuthManager.reset()
        if creds:
            logger.info("✓ Token reset and re-authorized successfully")
            return 0
        else:
            logger.error("✗ Failed to reset token")
            return 1

    # Normal flow
    logger.info("\nAuthenticating with YouTube...")
    creds = YouTubeOAuthManager.authenticate(force_refresh=args.force)

    if creds:
        logger.info("✓ YouTube authentication successful")
        logger.info(f"  Access Token: {creds.token[:30]}..." if creds.token else "  No token")
        logger.info(f"  Expires: {creds.expiry}")

        # Validate scopes
        if YouTubeOAuthManager.validate_scopes():
            logger.info("✓ Token has proper scopes for upload")
            logger.info("\nSetup complete! You can now post to YouTube.")
            return 0
        else:
            logger.warning("⚠ Token might not have upload scope")
            logger.warning("  Please authorize with proper permissions")
            return 1
    else:
        logger.error("✗ YouTube authentication failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
