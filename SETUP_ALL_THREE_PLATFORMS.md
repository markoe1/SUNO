# Setup YouTube, Instagram, and TikTok — Phase 11

All three platforms are now ready to post. Follow this guide to set up credentials for each.

## Quick Setup (if you have credentials already)

```bash
# If you have tokens ready, add to .env:
INSTAGRAM_ACCESS_TOKEN=YOUR_TOKEN_HERE
INSTAGRAM_BUSINESS_ACCOUNT_ID=YOUR_ID_HERE
TIKTOK_ACCESS_TOKEN=YOUR_TOKEN_HERE

# Then test:
python phase11_test_posting.py
```

---

## Platform-by-Platform Setup

### 1. YouTube (OAuth) ⏳ Required

YouTube requires OAuth authentication with upload permissions.

**Step 1: Start OAuth Flow**
```bash
python setup_youtube_oauth.py
```

**Step 2: Authorize in Browser**
- Browser opens automatically
- Click "Authorize"
- Approve scopes: `youtube.upload` and `youtube.readonly`
- Browser closes, token saved

**Step 3: Verify**
```bash
python setup_youtube_oauth.py --validate
```

Expected: `✓ Token is valid with proper scopes`

**Troubleshooting:**
- If no browser opens: Run with `--force` flag
- If "Invalid client": Check `youtube_uploader/credentials.json` exists
- If "Insufficient scopes": Delete token and re-run: `python setup_youtube_oauth.py --reset`

---

### 2. TikTok (Official API) ⏳ Recommended

**Option A: Using Official API (Recommended)**

TikTok official API requires:
1. TikTok Developer Account
2. App with "User Posting" permissions
3. OAuth access token

**Steps:**
1. Go to https://developers.tiktok.com
2. Sign in with your TikTok account
3. Create a new app
4. Request "User Posting" permission
5. Get OAuth token from: https://developers.tiktok.com/tools/sandbox
6. Add to `.env`:
   ```
   TIKTOK_ACCESS_TOKEN=your_token_here
   ```

**Option B: Browser Automation (Fallback)**

If you don't have developer API:
```bash
python setup_all_platforms.py --tiktok
```

This will:
- Open browser and log in with TIKTOK_USERNAME/PASSWORD from .env
- Extract token from browser localStorage
- Save to .env

**Note:** May fail due to TikTok anti-bot detection. Official API is more reliable.

**Verify:**
```bash
python phase11_test_posting.py
```

---

### 3. Instagram (Meta Graph API) ⏳ Recommended

Instagram requires Meta's official Graph API (not browser username/password).

**Prerequisites:**
- Facebook/Meta account
- Business account (free to create)
- Instagram Business or Creator account

**Setup Steps:**

#### Step 1: Create Meta Business Account
1. Go to https://www.facebook.com/business/tools/meta-business-suite
2. Create new business account
3. Add Instagram account to it (switch to Business account type in Instagram)

#### Step 2: Create Meta App
1. Go to https://developers.facebook.com
2. Click "My Apps" → "Create App"
3. Choose "Business" type
4. Fill in app details
5. In Products, add "Instagram Graph API"

#### Step 3: Get Access Token
1. In your Meta app → Tools → Graph API Explorer
2. Select your app from dropdown
3. Click "Generate Access Token"
4. Permissions needed:
   - `instagram_basic`
   - `instagram_content_publish`
5. Copy the token (looks like `EAABC...`)

#### Step 4: Get Business Account ID
1. Graph API Explorer: https://developers.facebook.com/tools/explorer/
2. Run query: `GET /me/accounts`
3. Find your Instagram business account
4. Copy the `id` field

#### Step 5: Add to .env
```
INSTAGRAM_ACCESS_TOKEN=EAABC...xxx
INSTAGRAM_BUSINESS_ACCOUNT_ID=17841406338772
```

**Verify:**
```bash
python phase11_test_posting.py
```

**Detailed Video Guide:**
- See PHASE_11_SETUP_GUIDE.md sections 2 & 3

---

## Manual Token Entry

If you have tokens but need to add them:

**Edit `.env` file:**
```bash
# YouTube (auto-created, no manual entry needed)

# TikTok
TIKTOK_ACCESS_TOKEN=your_token_here

# Instagram
INSTAGRAM_ACCESS_TOKEN=your_token_here
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_account_id_here
```

Then reload and test:
```bash
python phase11_test_posting.py
```

---

## Validate All Three

```bash
python phase11_test_posting.py
```

**Expected Output:**
```
✓ PASS: adapter_registry
✓ PASS: youtube_token          ← After OAuth setup
✓ PASS: youtube_adapter
✓ PASS: youtube_payload
✓ PASS: instagram_creds        ← After .env update
✓ PASS: instagram_adapter
✓ PASS: tiktok_creds           ← After .env update
✓ PASS: tiktok_adapter

PLATFORM STATUS:
  YouTube:   ✓ Ready
  Instagram: ✓ Ready
  TikTok:    ✓ Ready
```

---

## Testing Posts

Once credentials are set:

```bash
# Dry run (validates without posting)
python test_platform_posting.py

# Actual posting (when video infrastructure ready)
# python test_post_video.py --platform youtube --video test.mp4
# python test_post_video.py --platform instagram --video test.mp4
# python test_post_video.py --platform tiktok --video test.mp4
```

---

## Troubleshooting

### YouTube Issues

| Problem | Solution |
|---------|----------|
| "Credentials.json not found" | Check `youtube_uploader/credentials.json` exists |
| "Invalid client" | Regenerate from Google Cloud Console |
| "Insufficient scopes" | Run `python setup_youtube_oauth.py --reset` |
| Browser doesn't open | Try `python setup_youtube_oauth.py --force` |

### TikTok Issues

| Problem | Solution |
|---------|----------|
| "Browser login failed" | Check TIKTOK_USERNAME/PASSWORD in .env |
| "Anti-bot detected" | Use official API instead of browser automation |
| No token appears in .env | Run again, check browser console errors |

### Instagram Issues

| Problem | Solution |
|---------|----------|
| "Invalid access token" | Check token hasn't expired (60 days for user tokens) |
| "Account not found" | Verify INSTAGRAM_BUSINESS_ACCOUNT_ID is numeric |
| "Insufficient permissions" | Check token has instagram_content_publish scope |
| "No permission to publish" | Ensure account is Business type, not Personal |

---

## Token Lifetimes

| Platform | Token Type | Duration | Refresh |
|----------|-----------|----------|---------|
| YouTube | OAuth refresh | Years | Auto (background) |
| TikTok | Access | 90 days | Manual re-auth |
| Instagram (User) | Access | 1 hour | Re-generate via API |
| Instagram (Page) | Access | Indefinite | Never |

**Recommended for Production:**
- YouTube: Refresh tokens (auto)
- TikTok: Use official API with long-lived tokens
- Instagram: Use Page access token (doesn't expire)

---

## Security Notes

**Never commit tokens to git:**
- `.env` file is in `.gitignore` ✓
- Tokens stored locally only
- Only used by your local scripts

**Tokens in this session are:**
- Stored in `.env` (local, not committed)
- Never transmitted to external servers (except to post)
- Never logged or printed (replaced with `...`)
- Automatically loaded from `.env` on startup

---

## Next Steps

1. ✓ YouTube: `python setup_youtube_oauth.py`
2. ✓ TikTok: Get token from https://developers.tiktok.com or run browser automation
3. ✓ Instagram: Get token from Meta developers console
4. ✓ Test: `python phase11_test_posting.py`
5. ✓ Post: Upload test video and verify all three platforms work

---

## FAQ

**Q: Can I use my regular Instagram password instead of API token?**
A: No. Instagram's official API requires Meta Graph API tokens. Browser passwords don't work with the API.

**Q: What if I don't have a Meta Business Account?**
A: Create one free at https://www.facebook.com/business/tools/meta-business-suite

**Q: Can I test without posting real videos?**
A: Yes! Adapters validate API connection before posting. See `test_platform_posting.py`.

**Q: Do I need all three platforms?**
A: No. YouTube is core. TikTok and Instagram are optional for Phase 11 (can be added individually).

**Q: How long do tokens last?**
A: YouTube (years), TikTok (90 days), Instagram (variable). See Token Lifetimes table above.

**Q: What happens when token expires?**
A: Posting fails. YouTube auto-refreshes. TikTok/Instagram need manual re-auth.
