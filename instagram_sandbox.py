"""
Instagram Graph API Sandbox Testing
====================================
Upload and post videos to Instagram using Meta Graph API.
"""

import os
import requests
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Meta/Instagram credentials
META_APP_ID = os.getenv("META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

# Graph API endpoints
GRAPH_API_VERSION = "v18.0"
BASE_URL = f"https://graph.instagram.com/{GRAPH_API_VERSION}"

# Get access token
ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")  # From Access Token Tool in console


def get_account_info(access_token):
    """Get Instagram Business Account info."""
    url = f"{BASE_URL}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}"
    params = {
        'fields': 'id,username,name,biography,followers_count',
        'access_token': access_token
    }

    logger.info("Fetching account info...")
    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()
    logger.info(f"Account: {data.get('username')}")
    logger.info(f"  Name: {data.get('name')}")
    logger.info(f"  Followers: {data.get('followers_count')}")

    return data


def upload_video_to_instagram(video_path: str, caption: str, access_token: str):
    """
    Upload video to Instagram as a Reel/Video.

    Args:
        video_path: Path to video file (.mp4)
        caption: Video caption
        access_token: Instagram Graph API access token

    Returns:
        dict: Upload response with video ID or error
    """

    video_file = Path(video_path)
    if not video_file.exists():
        logger.error(f"Video file not found: {video_path}")
        return {"success": False, "error": "File not found"}

    logger.info(f"Uploading video: {video_file.name}")
    logger.info(f"  Size: {video_file.stat().st_size / 1024 / 1024:.1f}MB")
    logger.info(f"  Caption: {caption}")

    # Step 1: Create upload session (for video files)
    url = f"{BASE_URL}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"

    with open(video_file, 'rb') as f:
        files = {'video': f}
        data = {
            'media_type': 'VIDEO',
            'caption': caption,
            'access_token': access_token
        }

        logger.info("Creating upload session...")
        response = requests.post(url, files=files, data=data)

    try:
        response.raise_for_status()
        result = response.json()

        if 'error' in result:
            logger.error(f"Upload error: {result['error']}")
            return {"success": False, "error": result['error']}

        video_id = result.get('id')
        logger.info(f"✅ Video uploaded successfully")
        logger.info(f"   Media ID: {video_id}")

        return {
            "success": True,
            "media_id": video_id,
            "raw_response": result
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Upload failed: {e}")
        if hasattr(e, 'response') and e.response.text:
            logger.error(f"  Response: {e.response.text}")
        return {"success": False, "error": str(e)}


def publish_video(media_id: str, access_token: str):
    """
    Publish uploaded video to Instagram feed.

    Args:
        media_id: ID from upload
        access_token: Instagram Graph API access token

    Returns:
        dict: Publish response
    """

    url = f"{BASE_URL}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
    data = {
        'creation_id': media_id,
        'access_token': access_token
    }

    logger.info("Publishing video...")
    response = requests.post(url, data=data)

    try:
        response.raise_for_status()
        result = response.json()

        if 'error' in result:
            logger.error(f"Publish error: {result['error']}")
            return {"success": False, "error": result['error']}

        logger.info(f"✅ Video published successfully")
        logger.info(f"   Post ID: {result.get('id')}")

        return {
            "success": True,
            "post_id": result.get('id'),
            "raw_response": result
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Publish failed: {e}")
        if hasattr(e, 'response') and e.response.text:
            logger.error(f"  Response: {e.response.text}")
        return {"success": False, "error": str(e)}


def test_sandbox(video_path: str = None, access_token: str = None):
    """
    End-to-end sandbox test: upload video + publish.

    Args:
        video_path: Path to test video
        access_token: Instagram access token (from Meta console)
    """

    logger.info("=" * 80)
    logger.info("INSTAGRAM GRAPH API SANDBOX TEST")
    logger.info("=" * 80)

    # Use provided token or from env
    token = access_token or ACCESS_TOKEN

    if not token:
        logger.error("No access token provided")
        logger.info("\nTo get an access token:")
        logger.info("1. Go to: https://developers.facebook.com/tools/accesstoken/")
        logger.info("2. Select your SUNO CLIPS app")
        logger.info("3. Copy the User Token or App Token")
        logger.info("4. Run: python instagram_sandbox.py --token YOUR_TOKEN /path/to/video.mp4")
        return

    # Step 0: Get account info
    logger.info("\n[STEP 0] Getting account info...")
    try:
        account_info = get_account_info(token)
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        logger.error("Make sure your access token is valid and has the right permissions")
        return

    # If no video provided, use existing test video
    if not video_path:
        # Look for existing clips
        test_clips = list(Path("C:\\Users\\ellio\\SUNO-repo\\clips\\posted").glob("*.mp4"))
        if test_clips:
            video_path = str(test_clips[0])
            logger.info(f"\nUsing test video: {test_clips[0].name}")
        else:
            logger.error("No video provided and no test clips found")
            return

    # Step 1: Upload
    logger.info("\n[STEP 1] Uploading video...")
    upload_result = upload_video_to_instagram(
        video_path,
        caption="Testing Instagram Graph API 📱 #suno #test",
        access_token=token
    )

    if not upload_result.get("success"):
        logger.error(f"Upload failed: {upload_result.get('error')}")
        return

    media_id = upload_result.get("media_id")

    # Step 2: Publish
    logger.info("\n[STEP 2] Publishing video...")
    publish_result = publish_video(media_id, token)

    if not publish_result.get("success"):
        logger.error(f"Publish failed: {publish_result.get('error')}")
        return

    logger.info("\n" + "=" * 80)
    logger.info("✅ INSTAGRAM SANDBOX TEST COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Media ID: {media_id}")
    logger.info(f"Post ID: {publish_result.get('post_id')}")
    logger.info("\nCheck your Instagram account to see the posted video")
    logger.info("=" * 80)


if __name__ == "__main__":
    import sys

    # Parse arguments
    access_token = None
    video_file = None

    if "--token" in sys.argv:
        idx = sys.argv.index("--token")
        if idx + 1 < len(sys.argv):
            access_token = sys.argv[idx + 1]

    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if not arg.startswith("--") and arg not in sys.argv[sys.argv.index(arg) - 1:sys.argv.index(arg)]:
                if Path(arg).exists():
                    video_file = arg

    test_sandbox(video_file, access_token)
