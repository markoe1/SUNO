"""
YouTube Data API v3 Sandbox Testing
====================================
Upload and publish videos to YouTube using existing credentials.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Use existing YouTube uploader from Phase 11
try:
    import sys
    youtube_uploader_path = Path(__file__).parent / 'youtube_uploader'
    if youtube_uploader_path not in sys.path:
        sys.path.insert(0, str(youtube_uploader_path))

    from suno_integration import SUNOYouTubeIntegration
    YOUTUBE_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import YouTube integration: {e}")
    YOUTUBE_AVAILABLE = False


def test_youtube_upload(video_path: str = None):
    """
    End-to-end YouTube sandbox test: upload and publish video.

    Args:
        video_path: Path to test video (defaults to first available clip)
    """

    logger.info("=" * 80)
    logger.info("YOUTUBE DATA API v3 SANDBOX TEST")
    logger.info("=" * 80)

    if not YOUTUBE_AVAILABLE:
        logger.error("YouTube integration not available")
        logger.error("Make sure youtube_uploader/suno_integration.py exists")
        return

    # Use provided video or find test clip
    if not video_path:
        clips_dir = Path("C:\\Users\\ellio\\SUNO-repo\\clips\\posted")
        test_clips = list(clips_dir.glob("*.mp4"))
        if test_clips:
            video_path = str(test_clips[0])
            logger.info(f"Using test video: {test_clips[0].name}\n")
        else:
            logger.error("No video provided and no test clips found")
            return

    video_file = Path(video_path)
    if not video_file.exists():
        logger.error(f"Video not found: {video_path}")
        return

    logger.info(f"Video: {video_file.name}")
    logger.info(f"Size: {video_file.stat().st_size / 1024 / 1024:.1f}MB")

    # Initialize uploader
    logger.info("\n[STEP 1] Initializing YouTube uploader...")
    try:
        uploader = SUNOYouTubeIntegration(
            suno_clips_dir=str(Path(__file__).parent / "clips"),
            credentials_file=str(Path(__file__).parent / 'youtube_uploader' / 'credentials.json'),
            token_file=str(Path(__file__).parent / 'youtube_uploader' / 'token.pickle')
        )
        logger.info("✅ Uploader initialized")
    except Exception as e:
        logger.error(f"Failed to initialize uploader: {e}")
        return

    # Authenticate
    logger.info("\n[STEP 2] Authenticating with YouTube...")
    try:
        uploader.authenticate_once()
        logger.info("✅ Authenticated")
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return

    # Upload
    logger.info("\n[STEP 3] Uploading video to YouTube...")
    try:
        title = "SUNO Clips - Sandbox Test"
        description = "Testing YouTube Data API v3 integration for SUNO clips automation"
        tags = ['suno', 'test', 'sandbox']

        video_id = uploader.upload_clip(
            clip_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status='unlisted'  # Start unlisted for testing
        )

        if video_id:
            watch_url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info(f"✅ Upload successful")
            logger.info(f"   Video ID: {video_id}")
            logger.info(f"   URL: {watch_url}")
        else:
            logger.error("Upload failed - no video ID returned")
            return

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return

    logger.info("\n" + "=" * 80)
    logger.info("✅ YOUTUBE SANDBOX TEST COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Video ID: {video_id}")
    logger.info(f"Watch URL: {watch_url}")
    logger.info("\nVideo is unlisted. Check YouTube to verify.")
    logger.info("=" * 80)


if __name__ == "__main__":
    import sys

    video_file = sys.argv[1] if len(sys.argv) > 1 else None
    test_youtube_upload(video_file)
