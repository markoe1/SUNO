"""
TikTok Sandbox API Testing Module
==================================
Authorization Code flow for sandbox video uploads.
"""

import os
import json
import requests
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Sandbox credentials from .env
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")

# TikTok Sandbox API endpoints (v2)
TOKEN_URL = "https://open.tiktokapis.com/v1/oauth/token/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
UPLOAD_URL = "https://open.tiktokapis.com/v1/post/publish/action/upload/"
CREATE_URL = "https://open.tiktokapis.com/v1/post/publish/create/"

# Redirect URI for OAuth callback
REDIRECT_URI = "https://localhost:8000/auth/tiktok/callback"

# Store token in memory for this session
_access_token = None
_token_info = None


def generate_auth_url():
    """Generate the OAuth authorization URL for user to click."""
    scopes = "user.info.basic,video.upload"
    # Try developer portal OAuth for sandbox
    auth_url = (
        f"https://developer.tiktok.com/oauth/authorize?"
        f"client_key={TIKTOK_CLIENT_KEY}"
        f"&scope={scopes}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return auth_url


def exchange_code_for_token(auth_code: str):
    """
    Exchange authorization code for access token.

    Args:
        auth_code: Authorization code from OAuth redirect

    Returns:
        dict: Token response with access_token, expires_in, open_id, etc.
    """
    global _access_token, _token_info

    logger.info("Exchanging authorization code for access token...")

    payload = {
        "client_key": TIKTOK_CLIENT_KEY,
        "client_secret": TIKTOK_CLIENT_SECRET,
        "code": auth_code,
        "grant_type": "authorization_code",
    }

    try:
        response = requests.post(TOKEN_URL, json=payload, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Check for error in response
        if data.get("error") or data.get("error_code") != 0:
            error_msg = data.get("description") or data.get("error_description", "Unknown error")
            logger.error(f"Token error: {error_msg}")
            return None

        # Extract from 'data' wrapper (TikTok's response format)
        token_data = data.get("data", data)

        _access_token = token_data.get("access_token")
        _token_info = token_data

        logger.info(f"✅ Access token obtained")
        logger.info(f"   Open ID: {token_data.get('open_id')}")
        logger.info(f"   Expires in: {token_data.get('expires_in')} seconds")

        return token_data

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to exchange code: {e}")
        return None


def get_or_cache_token(auth_code: str = None):
    """
    Get cached token or exchange code for new token.

    Args:
        auth_code: Optional authorization code to exchange

    Returns:
        dict: Token info or None
    """
    global _access_token, _token_info

    if _access_token:
        logger.info("Using cached access token")
        return _token_info

    if not auth_code:
        logger.error("No access token cached and no auth code provided")
        logger.info("\nTo get a token, visit this URL in your browser:")
        logger.info(generate_auth_url())
        logger.info("\nAfter authorizing, you'll be redirected. Copy the 'code' parameter and run:")
        logger.info("  python tiktok_sandbox.py --code YOUR_CODE_HERE")
        return None

    return exchange_code_for_token(auth_code)


def upload_video_to_sandbox(video_path: str, caption: str = "Test clip", hashtags: str = "#suno #test"):
    """
    Upload video to TikTok sandbox.

    Args:
        video_path: Path to video file (.mp4, .mov, etc.)
        caption: Video caption
        hashtags: Space-separated hashtags

    Returns:
        dict: Upload response with video_id or error
    """

    # Check if we have token
    if not _access_token:
        logger.error("No access token available")
        return {"success": False, "error": "No access token"}

    # Check file exists
    video_file = Path(video_path)
    if not video_file.exists():
        logger.error(f"Video file not found: {video_path}")
        return {"success": False, "error": "File not found"}

    logger.info(f"Uploading video: {video_file.name}")
    logger.info(f"  Size: {video_file.stat().st_size / 1024 / 1024:.1f}MB")
    logger.info(f"  Caption: {caption}")

    try:
        # Upload video file
        headers = {
            "Authorization": f"Bearer {_access_token}",
        }

        with open(video_file, 'rb') as f:
            files = {
                'file': (video_file.name, f, 'video/mp4')
            }
            data = {
                'description': caption,
            }

            logger.info("Uploading to TikTok sandbox...")
            response = requests.post(
                UPLOAD_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=60  # Video upload can take longer
            )

        response.raise_for_status()
        result = response.json()

        if "error" in result:
            logger.error(f"Upload error: {result['error']}")
            logger.error(f"  Details: {result.get('error_description', 'N/A')}")
            return {"success": False, "error": result.get('error_description', 'Unknown error')}

        logger.info(f"✅ Video uploaded successfully")
        logger.info(f"   Video ID: {result.get('data', {}).get('video_id')}")

        return {
            "success": True,
            "video_id": result.get('data', {}).get('video_id'),
            "raw_response": result
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Upload failed: {e}")
        return {"success": False, "error": str(e)}


def create_post(video_id: str, caption: str = "Test clip", hashtags: str = "#suno #test"):
    """
    Create a post using uploaded video.

    Args:
        video_id: Video ID from upload
        caption: Post caption
        hashtags: Space-separated hashtags

    Returns:
        dict: Post creation response
    """

    headers = {
        "Authorization": f"Bearer {_access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "source_type": "UPLOAD_ID",
        "video_id": video_id,
        "text": f"{caption}\n\n{hashtags}",
        "disable_duet": False,
        "disable_stitch": False,
        "disable_comment": False,
    }

    logger.info("Creating post...")

    try:
        response = requests.post(
            CREATE_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()

        result = response.json()

        if "error" in result:
            logger.error(f"Post creation error: {result['error']}")
            return {"success": False, "error": result.get('error_description')}

        logger.info(f"✅ Post created successfully")
        logger.info(f"   Post ID: {result.get('data', {}).get('post_id')}")

        return {
            "success": True,
            "post_id": result.get('data', {}).get('post_id'),
            "raw_response": result
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Post creation failed: {e}")
        return {"success": False, "error": str(e)}


def test_sandbox(video_path: str = None):
    """
    End-to-end sandbox test: upload video + create post.

    Args:
        video_path: Path to test video (if None, creates a minimal test file)
    """

    logger.info("=" * 80)
    logger.info("TIKTOK SANDBOX API TEST")
    logger.info("=" * 80)

    # If no video provided, create a minimal test file
    if not video_path:
        logger.info("\nNo video provided. Creating minimal test video...")
        # Create a 1-frame MP4 (minimal valid video)
        import subprocess
        test_video = Path("test_video.mp4")

        # Use ffmpeg to create a silent 1-second black video
        cmd = [
            "ffmpeg", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=1",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=1",
            "-pix_fmt", "yuv420p",
            "-y",  # Overwrite without asking
            str(test_video)
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=10)
            video_path = str(test_video)
            logger.info(f"✓ Test video created: {test_video}")
        except Exception as e:
            logger.error(f"Failed to create test video: {e}")
            logger.info("(Make sure ffmpeg is installed)")
            return

    # Step 1: Upload
    logger.info("\n[STEP 1] Uploading video...")
    upload_result = upload_video_to_sandbox(
        video_path,
        caption="Testing TikTok Sandbox API 🚀",
        hashtags="#sandbox #test #suno"
    )

    if not upload_result.get("success"):
        logger.error(f"Upload failed: {upload_result.get('error')}")
        return

    video_id = upload_result.get("video_id")

    # Step 2: Create post
    logger.info("\n[STEP 2] Creating post with uploaded video...")
    post_result = create_post(
        video_id,
        caption="Testing TikTok Sandbox API 🚀",
        hashtags="#sandbox #test #suno"
    )

    if not post_result.get("success"):
        logger.error(f"Post creation failed: {post_result.get('error')}")
        return

    logger.info("\n" + "=" * 80)
    logger.info("✅ SANDBOX TEST COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Video ID: {video_id}")
    logger.info(f"Post ID: {post_result.get('post_id')}")
    logger.info("\nYou can view the post in TikTok Sandbox Dashboard")
    logger.info("=" * 80)


if __name__ == "__main__":
    import sys

    # Parse arguments
    auth_code = None
    video_file = None

    if "--code" in sys.argv:
        idx = sys.argv.index("--code")
        if idx + 1 < len(sys.argv):
            auth_code = sys.argv[idx + 1]
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        video_file = sys.argv[1]

    # Step 1: Get access token
    logger.info("=" * 80)
    logger.info("STEP 1: GET ACCESS TOKEN")
    logger.info("=" * 80)

    token_info = get_or_cache_token(auth_code)

    if not token_info:
        logger.error("\n❌ Failed to get access token")
        logger.info("\nGo to the URL above, authorize, then run:")
        logger.info("  python tiktok_sandbox.py --code YOUR_CODE_HERE /path/to/video.mp4")
        sys.exit(1)

    logger.info("✅ Token ready\n")

    # Step 2: Upload video
    logger.info("=" * 80)
    logger.info("STEP 2: UPLOAD VIDEO")
    logger.info("=" * 80)

    test_sandbox(video_file)
