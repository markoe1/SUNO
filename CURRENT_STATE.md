# SUNO CURRENT STATE — Phase 1 Inventory (April 18, 2026)

## 1. PROJECT OVERVIEW

**Project Name:** SUNO Clips / WhopClipper
**Purpose:** Autonomous social media clipping system with YouTube, Instagram/Meta, and TikTok integration
**Status:** Post-revived, under stabilization for live mode
**Latest Commit:** 79d3a77 (fix: missing os import, oauth_manager.py, TikTok creds)
**Location:** `C:\Users\ellio\SUNO-repo`

---

## 2. ENTRY POINTS & EXECUTION MODES

### Main CLI: `main.py`

```
python main.py [MODE] [OPTIONS]
```

**Available modes:**
- `campaigns` — List/refresh Whop campaigns
- `post` — Post pending clips from queue
- `run` — Full cycle (campaigns + post)
- `daemon` — 24/7 automated loop
- `status` — Show queue + account status
- `dashboard` — Earnings overview
- `test` — Verify config + credentials

**Verified working:** `python youtube_sandbox.py` ✅ (YouTube OAuth + upload test)

---

## 3. ACTIVE PLATFORMS & ADAPTERS

### YouTube ✅ READY
- **Adapter:** `suno/posting/adapters/youtube.py`
- **OAuth:** `suno/posting/youtube_oauth.py`
- **Entry:** `youtube_sandbox.py` (testing)
- **Status:** OAuth working with `access_type=offline` ✅
- **Credentials:** `youtube_uploader/credentials.json` + `token.pickle`
- **Integration:** `youtube_uploader/suno_integration.py` (full upload pipeline)

### Instagram / Meta 🟡 PARTIAL
- **Adapter:** `suno/posting/adapters/instagram.py`
- **OAuth:** via `oauth_manager.py`
- **Entry:** `instagram_sandbox.py` (testing)
- **Status:** Basic adapter exists, but production token flow unclear
- **Issues:**
  - Still relies on Graph API Explorer tokens (testing pattern)
  - No proper production OAuth flow documented
  - Missing Facebook Page ID + Instagram Business Account ID storage

### TikTok 🟡 PARTIAL
- **Adapter:** `suno/posting/adapters/tiktok.py`
- **OAuth:** via `oauth_manager.py`
- **Credentials:** TikTok sandbox keys in `.env` and `TIK TAK TOE.txt`
- **Status:** Basic adapter exists, refresh token handling unclear
- **Issues:**
  - Sandbox credentials used (not production)
  - No refresh flow documented
  - Missing proper re-auth handling

### Other Platforms (OUT OF SCOPE)
- Twitter: `suno/posting/adapters/twitter.py` (not in Phase plan)
- Bluesky: `suno/posting/adapters/bluesky.py` (not in Phase plan)

---

## 4. ARCHITECTURE LAYERS

### Backend/API
- **Framework:** FastAPI (in `api/app.py`)
- **Port:** 8000 (configured in `.env`)
- **Database:** PostgreSQL (via Alembic migrations in `alembic/`)

### Queue System
- **Manager:** `queue_manager.py` (RQ + Redis)
- **Database:** `db/models.py`, `db/models_v2.py`

### Platform Posting
- **Orchestrator:** `suno/posting/orchestrator.py`
- **Poster:** `platform_poster.py` (async batch posting to multiple platforms)
- **Credentials:** `suno/posting/credential_manager.py`

### Background Services
- **Daemon:** `daemon.py` (24/7 automation)
- **Whop Integration:** `services/whop_client.py` (campaign discovery)
- **Monitoring:** `monitoring.py`
- **Earnings Tracker:** `earnings_tracker.py`

### Support Services
- **Billing:** `billing_server.py` (Stripe integration, separate port :5001)
- **Config:** `config.py` (centralized settings)

---

## 5. DIRECTORY STRUCTURE

```
C:\Users\ellio\SUNO-repo/
├── main.py                          [ENTRY]
├── youtube_sandbox.py               [YOUTUBE TEST]
├── instagram_sandbox.py             [INSTAGRAM TEST]
├── platform_poster.py               [POSTING ORCHESTRATOR]
├── oauth_manager.py                 [PLATFORM OAUTH]
├── daemon.py                        [24/7 AUTOMATION]
├── config.py                        [SETTINGS]
│
├── api/                             [FASTAPI APP]
│   ├── app.py
│   ├── deps.py
│   ├── middleware.py
│   ├── routes/
│   │   ├── campaigns.py
│   │   ├── jobs.py
│   │   ├── submissions.py
│   │   └── auth.py
│   └── __init__.py
│
├── db/                              [DATABASE MODELS]
│   ├── engine.py
│   ├── models.py
│   ├── models_v2.py
│   └── seed.py
│
├── suno/                            [MAIN PACKAGE]
│   ├── posting/                     [PLATFORM-AGNOSTIC POSTING]
│   │   ├── adapters/
│   │   │   ├── base.py              [ABSTRACT BASE]
│   │   │   ├── youtube.py           [YOUTUBE ADAPTER]
│   │   │   ├── instagram.py         [INSTAGRAM ADAPTER]
│   │   │   ├── tiktok.py            [TIKTOK ADAPTER]
│   │   │   ├── twitter.py           [OUT OF SCOPE]
│   │   │   └── bluesky.py           [OUT OF SCOPE]
│   │   ├── youtube_oauth.py         [YOUTUBE OAUTH]
│   │   ├── credential_manager.py    [CREDENTIAL STORAGE]
│   │   ├── orchestrator.py          [POSTING ORCHESTRATOR]
│   │   ├── submission.py
│   │   └── submission_orchestrator.py
│   │
│   ├── campaigns/                   [CAMPAIGN DISCOVERY]
│   │   ├── orchestrator.py
│   │   ├── job_executor.py
│   │   └── eligibility.py
│   │
│   ├── billing/                     [BILLING/PAYMENTS]
│   │   ├── webhook_events.py
│   │   ├── membership_lifecycle.py
│   │   └── provisioning/
│   │
│   ├── workers/                     [BACKGROUND JOBS]
│   │   └── job_worker.py
│   │
│   ├── common/                      [SHARED UTILITIES]
│   │   ├── job_queue.py
│   │   └── constants.py
│   │
│   ├── dashboard/                   [CUSTOMER DASHBOARD]
│   │   └── customer.py
│   │
│   └── __init__.py
│
├── youtube_uploader/                [YOUTUBE-SPECIFIC]
│   ├── credentials.json             [YOUTUBE OAUTH CREDENTIALS]
│   ├── token.pickle                 [YOUTUBE USER TOKEN]
│   ├── upload_video.py
│   ├── simple_upload.py
│   ├── suno_integration.py          [SUNO-INTEGRATED UPLOADER]
│   └── batch_upload.py
│
├── services/                        [EXTERNAL SERVICE CLIENTS]
│   ├── whop_client.py               [WHOP API]
│   └── auth.py
│
├── tests/                           [TEST SUITE]
│   └── test_*.py files
│
├── alembic/                         [DATABASE MIGRATIONS]
│   ├── env.py
│   ├── versions/
│   └── alembic.ini
│
├── .env                             [LIVE SECRETS]
├── .env.example                     [TEMPLATE]
├── .env.production.example          [PRODUCTION TEMPLATE]
├── .env.template                    [LEGACY TEMPLATE]
│
├── clips/                           [VIDEO STORAGE]
│   ├── posted/
│   └── failed/
│
├── data/                            [LOCAL DATA]
│   ├── oauth_tokens.json
│   └── quality_log.json
│
├── logs/                            [LOG FILES]
│   └── *.log
│
├── templates/                       [HTML TEMPLATES]
├── public/                          [STATIC ASSETS]
├── web/                             [FRONTEND/WEBSITE]
└── venv/                            [PYTHON VIRTUAL ENV]
```

---

## 6. CONFIGURATION & SECRETS

### Environment Variables (`.env`)
```
DATABASE_URL=postgresql+asyncpg://suno:suno@db:5432/suno_clips
REDIS_URL=redis://redis:6379/0
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
BASE_URL=http://localhost:8000

# Encryption/JWT
ENCRYPTION_KEY=...
JWT_SECRET_KEY=...
JWT_REFRESH_SECRET_KEY=...
SESSION_COOKIE_SECRET=...

# Platform Credentials
WHOP_API_KEY=apik_T2XFPiNXTrR7k_C4285839_C_... [IN TIK TAK TOE.txt]
TIKTOK_CLIENT_KEY=sbaw0bwtvs0v1gfjha [SANDBOX]
TIKTOK_CLIENT_SECRET=SIBd4OlXl1GlGxrgr2HGut6TDS3sNOXv [SANDBOX]
STRIPE_API_KEY=[REDACTED - see .env.production.example]
STRIPE_SECRET_KEY=[REDACTED - see .env.production.example]
```

### Secrets Storage Issues ⚠️
- ❌ API keys in plaintext in `TIK TAK TOE.txt` (should be .env only)
- ❌ TikTok using SANDBOX keys (not production)
- ❌ Stripe keys exposed in both .env and backup file
- ❌ No .env file marked as git-ignored properly

---

## 7. ACTIVE vs LEGACY CODE

### ACTIVE (Recently used / Phase 8-11)
✅ `main.py` — Main CLI
✅ `suno/posting/adapters/` — Platform posting
✅ `suno/campaigns/` — Campaign discovery
✅ `suno/billing/` — Whop integration
✅ `youtube_sandbox.py` — YouTube testing
✅ `platform_poster.py` — Async posting
✅ `daemon.py` — 24/7 automation
✅ `oauth_manager.py` — OAuth token management
✅ `queue_manager.py` — Job queue
✅ `db/models.py` — Database schema

### LEGACY / UNCLEAR STATUS
🟡 `instagram_sandbox.py` — Last tested unknown
🟡 `api/routes/auth.py` — May be legacy
🟡 `db/models_v2.py` — Why v2? Still used?
🟡 `Fix_files/` directory — Quarantine for what?
🟡 `billing_server.py` — Separate Stripe server - still needed?
🟡 `project_notes/` — Old session notes, not current context

### OUT OF SCOPE (Per Phase plan)
❌ `suno/posting/adapters/twitter.py`
❌ `suno/posting/adapters/bluesky.py`
❌ Other platforms not in Phase plan

---

## 8. KNOWN ISSUES

### YouTube
- ✅ OAuth with `offline` access type working
- ✅ Token persistence working
- ⚠️ Need to verify refresh token auto-refresh on expiry

### Instagram/Meta
- ❌ No production OAuth flow documented
- ❌ Still using Graph API Explorer test tokens
- ❌ Missing Page ID + Business Account ID storage
- ❌ No re-auth path if token expires

### TikTok
- ❌ Using SANDBOX credentials (not production)
- ❌ No refresh token handling documented
- ❌ No scope approval status documented
- ❌ No re-auth path if token expires

### General
- ❌ Plaintext secrets in `TIK TAK TOE.txt` (security risk)
- ❌ Multiple `.env` templates confusing (.env.example, .template, .production.example)
- ❌ `.env` file may have hardcoded localhost URLs
- ❌ Database looks like PostgreSQL (needs local setup) or Docker

---

## 9. DEPLOYMENT READINESS

### Current Setup
- **Type:** Local development
- **Database:** Expects PostgreSQL (not SQLite)
- **Redis:** Expects Redis (not in-memory)
- **Frontend:** Static files in `public/` and `templates/`

### Gaps for "Live"
- ❌ No documented local-served setup (file:// assumptions?)
- ❌ No domain name configured
- ❌ No production environment setup
- ❌ No deploy script or runbook
- ❌ Platform credentials need production versions (TikTok, Meta)

---

## 10. NEXT STEPS (PHASES 2-7)

### Phase 2: Clean the local SUNO site
- Remove stale files from `Fix_files/`
- Verify `models_v2.py` usage
- Document or remove unused legacy code
- Fix `.env` template confusion

### Phase 3: Production auth architecture
- YouTube: Verify refresh token handling
- Meta: Design production OAuth flow (not Explorer tokens)
- TikTok: Switch from sandbox to production credentials

### Phase 4: Configuration hardening
- Consolidate `.env*` files
- Move secrets from `TIK TAK TOE.txt` to `.env.example`
- Remove hardcoded localhost URLs

### Phase 5: Local deployment readiness
- Verify site runs on local server (not file://)
- Document local setup steps

### Phase 6: Domain transition prep
- Identify all hardcoded origins
- Make domain configurable

### Phase 7: Live mode validation
- Test each platform with production credentials
- Document known limitations
- Create launch checklist

---

## STATUS: READY FOR PHASE 2 ✅

Current state is documented. No blockers for cleanup phase.
