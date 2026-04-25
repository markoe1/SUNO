#!/usr/bin/env python3
"""
Test TikTok OAuth flow.
Run this to verify credentials are correct.
"""

import asyncio
import os
from dotenv import load_dotenv
from services.platform_oauth import TikTokOAuthService

load_dotenv()


async def test_tiktok_oauth():
    """Test TikTok OAuth credentials and generate auth URL."""
    print("\n" + "=" * 80)
    print("TIKTOK OAUTH TEST")
    print("=" * 80)

    # Check credentials
    client_id = os.getenv("TIKTOK_CLIENT_ID")
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET")

    print(f"\nCredentials from .env:")
    print(f"  CLIENT_ID: {client_id[:20] if client_id else 'NOT SET'}...")
    print(f"  CLIENT_SECRET: {client_secret[:20] if client_secret else 'NOT SET'}...")

    if not client_id or not client_secret:
        print("\n❌ ERROR: TikTok credentials not set in .env")
        print("   Add these to .env:")
        print("   TIKTOK_CLIENT_ID=awowp6fq5jjcprre")
        print("   TIKTOK_CLIENT_SECRET=XVOSE91xHwginkKSAPigsjX2mpVJLJD3")
        return False

    try:
        # Generate auth URL
        redirect_uri = "http://localhost:8000/api/oauth/tiktok/callback"
        auth_url = TikTokOAuthService.get_authorization_url(redirect_uri)

        print(f"\n✅ Auth URL generated successfully!")
        print(f"\n📱 Click this link to authorize:\n")
        print(f"{auth_url}\n")
        print(f"Then the callback will go to: {redirect_uri}")

        # Instructions
        print("\n" + "=" * 80)
        print("NEXT STEPS:")
        print("=" * 80)
        print("\n1. Click the auth URL above")
        print("2. Authorize the TikTok app")
        print("3. You'll be redirected to: /api/oauth/tiktok/callback?code=...")")
        print("4. The code is used to exchange for an access token")
        print("\n✅ If you see the callback, credentials are CORRECT!")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_tiktok_oauth())
    exit(0 if result else 1)
