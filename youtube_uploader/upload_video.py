#!/usr/bin/env python3
"""
YouTube Video Uploader using OAuth 2.0
Uploads SUNO clips to YouTube securely without storing passwords.
"""

import os
import pickle
from pathlib import Path
from dotenv import load_dotenv
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Load environment variables
load_dotenv()

# OAuth 2.0 Scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

class YouTubeUploader:
    def __init__(self, credentials_file='credentials.json', token_file='token.pickle'):
        """
        Initialize uploader with OAuth credentials.

        Args:
            credentials_file: Path to Google Cloud OAuth credentials JSON
            token_file: Path to store/load user authorization token
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.youtube = None

    def authenticate(self):
        """
        Authenticate user with Google OAuth 2.0.
        Returns valid credentials or None if authentication fails.
        """
        creds = None

        # Check if we have a saved token
        if os.path.exists(self.token_file):
            print(f"[INFO] Loading saved token from {self.token_file}")
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)

        # If no valid credentials, perform OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[INFO] Refreshing expired credentials...")
                creds.refresh(Request())
            else:
                print(f"[INFO] Starting OAuth flow using {self.credentials_file}")
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_file}\n"
                        f"See README.md for setup instructions."
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token for future use
            print(f"[INFO] Saving credentials token to {self.token_file}")
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)

        self.youtube = build('youtube', 'v3', credentials=creds)
        print("[OK] Authentication successful!")
        return creds

    def upload_video(self, file_path, title, description, tags=None,
                     category_id='10', privacy_status='private'):
        """
        Upload a video to YouTube.

        Args:
            file_path: Path to video file
            title: Video title (max 100 chars)
            description: Video description (max 5000 chars)
            tags: List of tags (max 500 chars total)
            category_id: YouTube category ID (10=Music, see docs for others)
            privacy_status: 'public', 'unlisted', or 'private'

        Returns:
            Video ID if successful, None if failed
        """
        if not self.youtube:
            print("[ERROR] Not authenticated. Call authenticate() first.")
            return None

        # Validate file
        if not os.path.exists(file_path):
            print(f"[ERROR] File not found: {file_path}")
            return None

        file_size = os.path.getsize(file_path)
        print(f"[INFO] Uploading: {file_path} ({file_size / 1024 / 1024:.2f} MB)")

        # Validate inputs
        if len(title) > 100:
            print(f"[WARNING] Title too long ({len(title)}). Truncating to 100 chars.")
            title = title[:100]

        if len(description) > 5000:
            print(f"[WARNING] Description too long. Truncating to 5000 chars.")
            description = description[:5000]

        # Build video metadata
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags or [],
                'categoryId': category_id,
            },
            'status': {
                'privacyStatus': privacy_status,
            },
        }

        # Prepare media upload
        media = MediaFileUpload(file_path, resumable=True, chunksize=1024*1024)

        try:
            print("[INFO] Starting upload...")
            request = self.youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    percent = int(status.progress() * 100)
                    print(f"[PROGRESS] {percent}%")

            video_id = response['id']
            print(f"[OK] Upload successful! Video ID: {video_id}")
            print(f"[INFO] View at: https://youtube.com/watch?v={video_id}")
            return video_id

        except Exception as e:
            print(f"[ERROR] Upload failed: {str(e)}")
            return None

def main():
    """Example usage"""
    uploader = YouTubeUploader(
        credentials_file='credentials.json',
        token_file='token.pickle'
    )

    # Authenticate
    uploader.authenticate()

    # Example upload (modify these)
    video_path = 'test_video.mp4'
    title = 'Test Upload from SUNO'
    description = 'This is a test upload using YouTube API'
    tags = ['suno', 'ai-music', 'automation']

    video_id = uploader.upload_video(
        file_path=video_path,
        title=title,
        description=description,
        tags=tags,
        category_id='10',  # Music
        privacy_status='unlisted'
    )

    if video_id:
        print(f"\n[SUCCESS] Video uploaded with ID: {video_id}")
    else:
        print("\n[FAILED] Video upload failed")

if __name__ == '__main__':
    main()
