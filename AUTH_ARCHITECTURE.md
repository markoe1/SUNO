# PRODUCTION AUTH ARCHITECTURE — SUNO Clips (April 18, 2026)

## OVERVIEW

Current state: Mixed auth methods across platforms (YouTube ✅ proper OAuth, TikTok 🟡 browser automation, Instagram 🟡 browser automation).

**Mission:** Transition TikTok and Instagram to proper OAuth by end of Phase 5.

---

## YOUTUBE ✅ PRODUCTION-READY

### Current State
- **Flow:** google-auth-oauthlib (InstalledAppFlow)
- **Token Storage:** `youtube_uploader/token.pickle` (binary)
- **Scopes:** youtube.upload, youtube.readonly
- **Refresh:** Automatic token refresh with Request() manager
- **Status:** ✅ PRODUCTION-READY

### Architecture
```
1. First run: User clicks auth link → OAuth browser flow
2. Token saved to token.pickle
3. On API calls: Check if expired → refresh if needed
4. Credentials object passed to adapter
```

### No Changes Needed
YouTube OAuth is complete and working. Keep as-is for production.

---

## TIKTOK 🟡 SANDBOX → PRODUCTION PATH

### Current State
- **Flow:** Browser automation via Playwright (NOT OAuth)
- **Method:** Extract token from browser localStorage after login
- **Credentials:** SANDBOX API from .env (sbaw0bwtvs0v1gfjha)
- **Password Auth:** TIKTOK_USERNAME/TIKTOK_PASSWORD in plaintext .env ⚠️
- **Token Storage:** `data/platform_credentials/tiktok_tokens.json`
- **Status:** 🟡 SANDBOX ONLY (not production)

### Why Current Method Fails for Production
1. TikTok blocks token extraction from browser (security measure)
2. Browser automation is fragile (breaks with UI changes)
3. Sandbox credentials have limited rate limits
4. No refresh token handling

### Production Path: OAuth 3-Legged Flow
```
GOAL: Implement proper TikTok OAuth 3.0 (Server-Side Auth Code Flow)

Steps:
1. Register TikTok Developer App (if not already done)
   - URL: https://developer.tiktok.com/
   - Get: CLIENT_ID, CLIENT_SECRET
   - Redirect URI: https://yourdomain.com/auth/tiktok/callback

2. Create Endpoint: /auth/tiktok/start
   - Redirect user to: https://www.tiktok.com/v1/oauth/authorize
   - Include: client_id, scope, state, redirect_uri

3. Create Callback: /auth/tiktok/callback
   - Receive auth_code from TikTok
   - Exchange code for access_token (backend, POST to /v1/oauth/token)
   - Store access_token (NOT password) in database

4. Refresh Flow
   - Check token expiry before posting
   - Use refresh_token to get new access_token
   - Store refreshed token

5. Move to Environment
   - .env: TIKTOK_CLIENT_ID, TIKTOK_CLIENT_SECRET, TIKTOK_REDIRECT_URI
   - Remove: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET (old sandbox)
   - Remove: TIKTOK_USERNAME, TIKTOK_PASSWORD (plaintext passwords)
```

### Implementation Order
1. **Phase 4A:** Set up TikTok app on developer portal
2. **Phase 4B:** Create /auth/tiktok/start and /auth/tiktok/callback endpoints
3. **Phase 4C:** Implement token exchange and storage
4. **Phase 4D:** Update TikTokCredentialManager to use OAuth tokens
5. **Phase 5:** Test with production TikTok account

### Code Location
- Current: `suno/posting/credential_manager.py` (TikTokCredentialManager class)
- Will migrate to: `suno/auth/tiktok_oauth.py` (new file)
- Update adapter: `suno/posting/adapters/tiktok.py` (expects access_token)

---

## INSTAGRAM/META 🟡 SANDBOX → PRODUCTION PATH

### Current State
- **Flow:** Browser automation via Playwright (NOT OAuth)
- **Method:** Extract Instagram user ID from browser localStorage after login
- **Credentials:** Temporary Graph API token in .env (EAASLGLkPnwkBR...) ⚠️
- **Business Account ID:** Hardcoded 78145398358 (test account)
- **Password Auth:** INSTAGRAM_USERNAME/INSTAGRAM_PASSWORD in plaintext .env ⚠️
- **Status:** 🟡 SANDBOX ONLY (not production, temp token)

### Why Current Method Fails for Production
1. Temporary Graph API token will expire (already near expiry)
2. Browser automation doesn't work with 2FA
3. Sandbox account is test-only
4. No proper OAuth flow from Meta Business Platform

### Production Path: Meta OAuth for Instagram Business
```
GOAL: Implement Meta Business Integrations OAuth (System User or App Flow)

Steps:
1. Create Meta Business App (if not already done)
   - URL: https://developers.facebook.com/
   - Create App → Business type
   - Get: APP_ID, APP_SECRET
   - Setup redirect_uri for callback

2. Two Options for Auth:

   OPTION A: System User (Recommended for single business account)
   - Create System User in Meta Business Manager
   - Grant permissions to: Instagram Business Account, Pages
   - Generate system user token (long-lived, no expiry)
   - Store directly in .env as: META_SYSTEM_USER_TOKEN
   - Pro: Simple, long-lived token, no refresh needed
   - Con: One token per business, not per-user

   OPTION B: App Flow (Multi-user / Multi-account)
   - Create endpoint: /auth/meta/start
   - Redirect to: https://www.facebook.com/v18.0/dialog/oauth
   - Get access_token after user grants permission
   - Exchange for long-lived token
   - Pro: Multi-account support, scalable
   - Con: More complex, requires user interaction

3. Obtain Facebook Page ID + Instagram Business Account ID
   - Call: GET /me/accounts (pages)
   - Call: GET {page_id}/instagram_business_account (IG account)
   - Store both IDs in database or .env

4. Token Refresh (if using App Flow)
   - Check if token expires within 7 days
   - Call: /oauth/access_token with client_id, client_secret
   - Use refresh_token if available (60-day refresh tokens)

5. Migrate to Environment
   - .env: META_APP_ID, META_APP_SECRET, META_SYSTEM_USER_TOKEN (OR Meta OAuth)
   - .env: META_PAGE_ID, META_INSTAGRAM_BUSINESS_ACCOUNT_ID
   - Remove: INSTAGRAM_ACCESS_TOKEN (temporary token)
   - Remove: INSTAGRAM_BUSINESS_ACCOUNT_ID=78145398358 (test account)
   - Remove: INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD (plaintext)
```

### RECOMMENDED: System User Approach (Simpler)
For a single business account (SUNO clips):
- No user auth flow needed
- Token doesn't expire
- Single .env var: META_SYSTEM_USER_TOKEN
- Setup once in Meta Business Manager, done

### Implementation Order
1. **Phase 4A:** Create Meta Business App + System User (or choose App Flow)
2. **Phase 4B:** Obtain and validate System User Token
3. **Phase 4C:** Get Facebook Page ID + Instagram Business Account ID
4. **Phase 4D:** Update InstagramCredentialManager to use OAuth token
5. **Phase 5:** Test with production Instagram Business Account

### Code Location
- Current: `suno/posting/credential_manager.py` (InstagramCredentialManager class)
- Will migrate to: `suno/auth/meta_oauth.py` (new file)
- Update adapter: `suno/posting/adapters/instagram.py` (expects access_token, business account ID)

---

## CREDENTIALS DATABASE SCHEMA (TODO)

Currently credentials are stored in plaintext .env. Move to database:

```python
# suno/common/models_v2.py - ADD THIS TABLE

class PlatformCredential(Base):
    __tablename__ = "platform_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    platform: Mapped[str]  # 'youtube', 'tiktok', 'instagram', 'twitter', 'bluesky'

    # Token storage (encrypted)
    access_token: Mapped[str]  # encrypted
    refresh_token: Mapped[Optional[str]]  # encrypted
    token_expires_at: Mapped[Optional[datetime]]

    # Platform-specific IDs
    platform_account_id: Mapped[Optional[str]]  # TikTok user ID, Instagram account ID, etc.
    platform_username: Mapped[Optional[str]]  # Display name

    # Metadata
    obtained_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_refreshed_at: Mapped[Optional[datetime]]
    is_valid: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
```

Migration: Alembic script to create table + migrate from .env

---

## SECURITY CRITICAL FIXES (IMMEDIATE)

### 🔴 HIGH PRIORITY: Remove Plaintext Passwords

Current .env has:
```
TIKTOK_USERNAME=elliottmarko70@gmail.com
TIKTOK_PASSWORD=Happyandtik13!        ← PLAINTEXT PASSWORD
INSTAGRAM_USERNAME=elliottmarko70@gmail.com
INSTAGRAM_PASSWORD=Fatalnikki17!       ← PLAINTEXT PASSWORD
YOUTUBE_EMAIL=elliott@elegantsolarinc.com
YOUTUBE_PASSWORD=agve ekvj ycoa zalf  ← PLAINTEXT PASSWORD
```

**Action:**
1. Delete these from .env immediately after migrating to OAuth
2. For development: Use OAuth flows instead
3. For testing: Create test credentials with limited permissions

### 🟡 MEDIUM PRIORITY: Encrypt Credentials at Rest

Once in database:
- Use `Fernet` symmetric encryption for access_tokens
- Key: Environment variable `ENCRYPTION_KEY` (already in .env)
- Implement in `suno/common/encryption.py`

### 🟡 MEDIUM PRIORITY: Rotate Existing API Keys

After OAuth migration:
- YouTube: Keep current (OAuth-based, no static keys)
- TikTok: Get new production credentials (replace sandbox)
- Instagram: Delete temp token, get System User token

---

## PHASE ROADMAP

### PHASE 4: OAuth Migration (Weeks 3-4)
**4A:** TikTok App Setup + OAuth endpoints
**4B:** Instagram/Meta System User Setup + OAuth endpoints
**4C:** Credential Manager refactoring
**4D:** Database migrations for credentials

### PHASE 5: Testing & Validation (Week 5)
**5A:** Test TikTok OAuth with production credentials
**5B:** Test Instagram OAuth with production account
**5C:** Token refresh edge cases
**5D:** Fallback mechanisms (what if OAuth fails)

### PHASE 6: Deployment (Week 6)
**6A:** Remove plaintext passwords from .env
**6B:** Deploy credential database
**6C:** Rotation of old credentials
**6D:** Monitoring + alerting for token expiry

---

## SUMMARY TABLE

| Platform | Current | Production | Changes | Priority |
|----------|---------|------------|---------|----------|
| **YouTube** | OAuth ✅ | OAuth ✅ | None | ✅ Done |
| **TikTok** | Browser + Sandbox 🟡 | OAuth 3-Leg | New endpoints + token storage | Phase 4 |
| **Instagram** | Browser + Temp token 🟡 | Meta System User | OAuth setup + Business Account IDs | Phase 4 |
| **Twitter** | Not started | OAuth 2.0 | Implement from scratch | Phase 4 |
| **Bluesky** | Not started | OAuth 2.0 | Implement from scratch | Phase 4 |

---

## NEXT STEPS

1. ✅ **Document** (THIS FILE) — Understanding architecture
2. **Phase 4A:** Set up TikTok app on developer portal
3. **Phase 4B:** Set up Meta Business App + System User token
4. **Phase 4C:** Implement OAuth endpoints (/auth/tiktok/start, /auth/meta/start)
5. **Phase 5:** Test with real accounts before going live

