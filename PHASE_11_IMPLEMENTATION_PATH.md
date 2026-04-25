# Phase 11 Implementation Path — Get YouTube, Instagram, TikTok Working

## Status

**Infrastructure:** ✓ Complete
**Credentials:** ⏳ Need setup
**Test Suite:** ✓ Ready

## Three Setup Paths

Choose the best path for each platform:

---

## Path 1: YouTube (Browser OAuth)

**Easiest — Just click "Authorize"**

```bash
python setup_youtube_oauth.py
```

This:
1. Opens Google OAuth in browser
2. You click "Authorize"
3. Approves scopes (youtube.upload + youtube.readonly)
4. Token saved → Done

**Verify:**
```bash
python setup_youtube_oauth.py --validate
```

Expected: `✓ Token is valid with proper scopes`

---

## Path 2: TikTok (Choose One)

### Option A: Official API (Recommended — Most Reliable)
```
1. Go to https://developers.tiktok.com
2. Create app with "User Posting" permission
3. Get access token
4. Add to .env: TIKTOK_ACCESS_TOKEN=token_here
```

### Option B: Browser Automation (Fallback)
```bash
python setup_all_platforms.py --tiktok
```

This:
1. Opens browser
2. Logs in with TIKTOK_USERNAME/PASSWORD from .env
3. Extracts token
4. Saves to .env

**Warning:** May fail due to TikTok anti-bot detection. Use Option A if possible.

**Verify:**
```bash
python phase11_test_posting.py
```

---

## Path 3: Instagram (Meta Graph API)

**Most Complex — But Worth It**

### Step 1: Create Meta Business Account (if needed)
```
https://www.facebook.com/business/tools/meta-business-suite
- Free to create
- Add Instagram account to it
- Switch Instagram to Business type
```

### Step 2: Create Meta App
```
https://developers.facebook.com
1. My Apps → Create App
2. Type: Business
3. Add "Instagram Graph API" product
```

### Step 3: Get Access Token
```
In Meta app → Tools → Graph API Explorer
1. Generate Access Token
2. Permissions: instagram_basic, instagram_content_publish
3. Copy token (EAABC...xxx format)
```

### Step 4: Get Account ID
```
Graph API Explorer query: GET /me/accounts
Find Instagram account → Copy "id" field (numeric)
```

### Step 5: Add to .env
```
INSTAGRAM_ACCESS_TOKEN=EAABC...xxx
INSTAGRAM_BUSINESS_ACCOUNT_ID=17841406338772
```

**Verify:**
```bash
python phase11_test_posting.py
```

---

## Quick Setup Script

If you have tokens ready:

```bash
# Edit .env file and add:
TIKTOK_ACCESS_TOKEN=your_token
INSTAGRAM_ACCESS_TOKEN=your_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_id

# Then test all three:
python phase11_test_posting.py
```

---

## Testing

### Test Individual Platforms
```bash
# Just test (no posting)
python test_platform_posting.py

# Full validation suite
python phase11_test_posting.py
```

### Expected Output After Setup
```
TEST SUMMARY
==========================================
✓ PASS: adapter_registry          5 platforms
✓ PASS: youtube_token             Token exists with proper scopes
✓ PASS: youtube_adapter           Account valid
✓ PASS: youtube_payload           Payload format correct
✓ PASS: instagram_creds           Credentials found
✓ PASS: instagram_adapter         Adapter ready
✓ PASS: tiktok_creds              Credentials found
✓ PASS: tiktok_adapter            Adapter ready

PLATFORM STATUS:
  YouTube:   ✓ Ready
  Instagram: ✓ Ready
  TikTok:    ✓ Ready

TOTAL: 8/8 tests passed
```

---

## Implementation Timeline

### Now (15 minutes)
1. **YouTube:** Run `python setup_youtube_oauth.py` (30 seconds)
2. **TikTok:** Get token from https://developers.tiktok.com or run browser automation
3. **Instagram:** Get Meta Graph API token and account ID
4. **Verify:** Run `python phase11_test_posting.py`

### Next Phase (Post Videos)
1. Upload test video
2. Post to each platform via unified interface
3. Verify post_id and URL returned
4. Document results

### Phase 12+ (Hardening)
- Multi-platform testing
- Error handling
- Retry logic
- Content validation

---

## File Reference

**Setup Tools:**
- `setup_youtube_oauth.py` — YouTube OAuth
- `setup_all_platforms.py` — Automated setup for TikTok/Instagram

**Test/Validation:**
- `phase11_test_posting.py` — Full test suite
- `test_platform_posting.py` — Individual adapter tests

**Documentation:**
- `SETUP_ALL_THREE_PLATFORMS.md` — Detailed step-by-step guides
- `PHASE_11_SETUP_GUIDE.md` — Original Phase 11 guide
- `PHASE_11_COMPLETION.md` — Technical spec
- This file — Quick reference

**Code:**
- `suno/posting/adapters/youtube.py` — YouTube adapter
- `suno/posting/adapters/instagram.py` — Instagram adapter
- `suno/posting/adapters/tiktok.py` — TikTok adapter
- `suno/posting/youtube_oauth.py` — YouTube OAuth manager
- `suno/posting/credential_manager.py` — Browser automation for TikTok/Instagram

---

## Common Issues & Fixes

### YouTube
| Issue | Fix |
|-------|-----|
| Browser doesn't open | `python setup_youtube_oauth.py --force` |
| "Insufficient scopes" | `python setup_youtube_oauth.py --reset` |
| "Invalid client" | Check credentials.json exists |

### TikTok
| Issue | Fix |
|-------|-----|
| Browser automation fails | Use official API instead |
| No token in .env | Check browser console errors |
| "Anti-bot detected" | Official API more reliable |

### Instagram
| Issue | Fix |
|-------|-----|
| "Invalid token" | Token may have expired |
| "Account not found" | Verify account ID is numeric |
| "Insufficient permissions" | Check token scopes in Meta app |

---

## Success Criteria

Phase 11 Complete when:
- [ ] YouTube token created with proper scopes
- [ ] TikTok token obtained (API or automation)
- [ ] Instagram token + account ID in .env
- [ ] `phase11_test_posting.py` shows all platforms ready
- [ ] Can post sample video to each platform
- [ ] Get back post_id and posted_url for each

---

## Next Command

Start here:

```bash
python setup_youtube_oauth.py
```

Then:

```bash
python phase11_test_posting.py
```

Then add TikTok and Instagram tokens to .env and re-run test.

Done!
