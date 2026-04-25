# YouTube Upload Setup (OAuth 2.0)

SUNO now uses **YouTube Data API v3** for reliable video uploads with proper video_id extraction.

## Setup Required (One-Time)

### Step 1: Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (or select existing)
3. Enable the **YouTube Data API v3**:
   - Search "YouTube Data API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - Choose "Desktop app"
   - Download JSON file
5. Save as: `youtube_uploader/credentials.json`

### Step 2: First Upload (Manual OAuth)

On first upload, a browser window will open asking you to authorize. Click "Allow" and SUNO will save the token automatically.

```bash
python main.py --mode post --count 1
```

First upload will:
1. Open browser to authorize
2. You approve access
3. Token saved to `youtube_uploader/token.pickle`
4. Future uploads use cached token (no more browser popups)

### Step 3: Verify

If successful:
- Video appears in YouTube Studio (Unlisted)
- Returns real video_id and watch URL
- URL: `https://www.youtube.com/watch?v={video_id}`

---

## How It Works

```
1. Clip in clips/inbox/
   ↓
2. Quality gate checks (no file integrity issues)
   ↓
3. YouTube API uploads file
   ↓
4. API returns video_id
   ↓
5. SUNO logs real watch URL
   ↓
6. URL submitted to Whop
```

---

## Troubleshooting

### `credentials.json not found`
- Download from Google Cloud Console (see Step 1)
- Save to `youtube_uploader/credentials.json`

### OAuth authentication fails
- Make sure credentials.json is for "Desktop app" type
- Try deleting `youtube_uploader/token.pickle` and retry

### Video uploads but no video_id returned
- Check YouTube Studio for the video
- Verify API response is valid
- Check logs in `logs/`

---

## Privacy Settings

Videos are uploaded as **Unlisted** by default (only accessible via direct link).
You can change to Public/Private in YouTube Studio.

---

## Token Caching

After first authentication:
- Token saved to: `youtube_uploader/token.pickle`
- Token automatically refreshed if expired
- No more manual auth needed
- Can use from any device with same token.pickle

---

## If Using Multiple Accounts

Each account needs its own token.pickle. Currently SUNO supports one YouTube account.

To switch accounts:
1. Delete `youtube_uploader/token.pickle`
2. Run upload again (will prompt for OAuth)
3. Authorize with different account
4. New token saved
