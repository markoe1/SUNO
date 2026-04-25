# Phase 11 Setup Guide — Get TikTok/Instagram at YouTube's Level

## Status
- ✅ All platform adapters built and registered
- ✅ Posting orchestrator with retry logic built
- ⚠️ YouTube: Re-authorization needed
- ✅ Instagram: Possible (you have Meta account)
- ❌ TikTok: Skipped (no developer app)

---

## 1. YouTube Setup (Required)

### Issue
Old YouTube token was removed because it had insufficient API scopes (403 error).

### Fix
Re-authorize YouTube with proper scopes:

#### Option A: Automatic (Recommended)
```bash
# Navigate to SUNO-repo
cd ~/SUNO-repo

# Run the main daemon with --auth-setup (pseudo-code)
# This will open browser and guide you through OAuth
python main.py --setup youtube
```

#### Option B: Manual
1. **Delete the token** (already done):
   ```bash
   rm youtube_uploader/token.pickle
   ```

2. **Run any SUNO command** that uses YouTube API:
   ```bash
   python main.py --mode test
   ```
   This will:
   - Detect missing token
   - Open browser
   - Show Google OAuth consent screen
   - Request scopes: `youtube.upload`, `youtube.readonly`
   - Save token to `youtube_uploader/token.pickle`

3. **Verify**:
   ```bash
   python test_platform_posting.py
   ```
   Should show: `✓ PASS: youtube`

### What Scopes You Need
When Google shows the OAuth consent screen, approve:
- **View your YouTube account** (youtube.readonly)
- **Manage your YouTube videos** (youtube.upload)

These are the only scopes needed. If there are additional prompts, you can skip them.

---

## 2. Instagram Setup (Required for Full Coverage)

### Prerequisites
You need to have:
- ✅ Meta/Facebook Business Account (you said yes)
- ✅ Instagram account linked to that Business Account
- ✅ Instagram switched to "Business" or "Creator" account type

### What You Need to Provide
To get Instagram working, I need these credentials:

1. **Instagram Business Account ID**
   - Location: Facebook Business Suite → Instagram Accounts
   - Format: Numeric ID, like `17841406338772`

2. **Meta Graph API Access Token** (Long-lived)
   - Location: https://developers.facebook.com → Your App → Tokens
   - Permissions needed: `instagram_basic,instagram_content_publish`
   - Format: `EAABC...xxx` (long string)

3. **Your Instagram Business Account ID** (alternative: username)
   - If you have Business Account ID, we can get the account ID from the API

### How to Get These

#### Step 1: Create Meta App (if needed)
```
1. Go to https://developers.facebook.com
2. Click "My Apps"
3. Create App → Choose "Business" type
4. In the app, add "Instagram Graph API" product
5. Go to Settings → Basic → Copy App ID and App Secret
```

#### Step 2: Generate Access Token
```
1. In your Meta app, go to Tools → Graph API Explorer
2. Select your app from dropdown (top-left)
3. Click "Get Token" → "Get User Access Token"
4. Check permissions:
   - instagram_basic
   - instagram_content_publish
   - pages_read_engagement (optional)
5. Click "Generate Access Token"
6. Copy the token (looks like: EAABC...xxx)
7. Note: This token expires. For production, get a "Page Access Token"
```

#### Step 3: Get Instagram Business Account ID
```
1. Graph API Explorer: https://developers.facebook.com/tools/explorer/
2. Make query: GET /me/accounts
3. Find your Instagram business account
4. Copy the "id" field (numeric)
```

### Verification Command
Once you have the token and account ID:

```bash
# Set in .env
INSTAGRAM_ACCESS_TOKEN=YOUR_TOKEN_HERE
INSTAGRAM_BUSINESS_ACCOUNT_ID=YOUR_ACCOUNT_ID_HERE

# Test
python test_platform_posting.py
```

Should show: `✓ PASS: instagram`

---

## 3. TikTok (Skipped)

You don't have a TikTok Developer app, so we're **skipping TikTok for Phase 11**.

### If you want TikTok later:
1. Apply for TikTok Developer Account
2. Create an app and get Client ID/Secret
3. Implement OAuth flow
4. Update `suno/posting/adapters/tiktok.py` with proper OAuth handling
5. Test with real TikTok account

---

## Testing

### Test Individual Platforms
```bash
python test_platform_posting.py
```

### Test Actual Posting
Once YouTube is re-authorized and Instagram is set up:

```bash
# This will be implemented next
python test_post_video.py --platform youtube --test-video test.mp4
python test_post_video.py --platform instagram --test-video test.mp4
```

---

## FAQ

### Q: Why does YouTube need re-authorization?
**A:** The old token had insufficient scopes (it couldn't actually post videos, only read). We deleted it so you can authorize with proper upload permissions.

### Q: What if I don't have a Meta Business Account?
**A:** Then Instagram posting won't work. You'd need to:
1. Create a Facebook Business Account
2. Create a Business Instagram Account
3. Get API credentials from Meta developers

### Q: Can I test without posting real videos?
**A:** Yes! We can add mock/test mode that validates the API connection without actually uploading.

### Q: How long do access tokens last?
- YouTube: Refresh token (lasts years, auto-refreshes)
- Instagram: Depends on token type
  - User token: 1 hour
  - Long-lived: 60 days
  - Page token: Doesn't expire (recommended for production)

---

## Next Steps

1. ✅ **Re-authorize YouTube**
   - Run `python test_platform_posting.py` or `python main.py --mode test`
   - Approve OAuth scopes
   - Verify token saved: `ls -la youtube_uploader/token.pickle`

2. ⏳ **Provide Instagram credentials**
   - Give me the Access Token and Business Account ID
   - Or the Facebook Business Account details so I can guide you

3. 🚀 **Test posting**
   - Once both are ready, run the posting tests
   - Upload real test video to YouTube and Instagram
   - Verify we get back post IDs and URLs

---

## Troubleshooting

### YouTube token refresh fails
- Delete token: `rm youtube_uploader/token.pickle`
- Re-authorize: `python main.py --mode test`
- Check logs for errors

### Instagram API returns 403
- Verify token is still valid (hasn't expired)
- Check permissions in Meta app settings
- Ensure account is Business type, not Personal

### Test returns "Validation result: False"
- Check internet connection
- Verify token is valid (not expired)
- Check error logs in SUNO_REPO/logs/
