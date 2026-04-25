"""
TikTok OAuth Authorization URL Generator
Step 1: Generate the login URL
Step 2: User clicks it and authorizes
Step 3: Get the code back
"""

import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
REDIRECT_URI = "http://localhost:8000/auth/tiktok/callback"
SCOPES = "user.info.basic,video.upload"  # Permissions needed to post videos

if not CLIENT_KEY:
    print("ERROR: TIKTOK_CLIENT_KEY not found in .env")
    exit(1)

# Generate the authorization URL
auth_url = (
    f"https://www.tiktok.com/v1/oauth/authorize?"
    f"client_key={CLIENT_KEY}"
    f"&response_type=code"
    f"&scope={SCOPES}"
    f"&redirect_uri={REDIRECT_URI}"
)

print("=" * 80)
print("STEP 1: TIKTOK AUTHORIZATION")
print("=" * 80)
print()
print("Click this link in your browser:")
print()
print(auth_url)
print()
print("=" * 80)
print("After clicking, you'll authorize the app.")
print("You'll be redirected to a URL with a 'code' parameter.")
print("Copy that code and paste it in the next step.")
print("=" * 80)
