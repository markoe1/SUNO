# Phase 8 E2E Test Setup Guide

## Environment Variables Required

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `API_URL` | No | `https://suno-api-production.onrender.com` | Render API endpoint |
| `TEST_USER_EMAIL` | **YES** | `test@phase8.local` | Email of user with active membership |
| `TEST_CAMPAIGN_ID` | **YES** | `1` | ID of available campaign (must exist!) |

## Critical: TEST_CAMPAIGN_ID and TEST_USER_EMAIL

❌ **DO NOT guess or invent these values**

- **TEST_CAMPAIGN_ID** must be a real campaign ID where:
  - Campaign exists in database
  - `Campaign.available = True`
  - User has not already created a clip for this campaign

- **TEST_USER_EMAIL** must be:
  - Real user in system
  - Has active Membership (status = ACTIVE)
  - Has Account provisioned
  - Has available clip quota

---

## Step 1: Find Valid Test Data

**On Render shell, run:**
```bash
python find_test_data.py
```

This will:
- Query database for available campaigns
- Find users with active membership
- Output the exact commands to run the test

**Expected output:**
```
[1] Available Campaigns:
  Campaign ID: 1
    Title: TikTok Fitness Content
    Brief: Generate engaging fitness tips...

[2] Users with Active Membership & Account:
  Email: creator@example.com
    Membership Status: active
    Clips Today: 0

COMMANDS TO RUN E2E TEST

Windows CMD:
  set API_URL=https://suno-api-production.onrender.com
  set TEST_USER_EMAIL=creator@example.com
  set TEST_CAMPAIGN_ID=1
  python test_phase8_e2e.py
```

---

## Step 2: Run E2E Test

### Windows CMD

```batch
set API_URL=https://suno-api-production.onrender.com
set TEST_USER_EMAIL=creator@example.com
set TEST_CAMPAIGN_ID=1
python test_phase8_e2e.py
```

### PowerShell

```powershell
$env:API_URL="https://suno-api-production.onrender.com"
$env:TEST_USER_EMAIL="creator@example.com"
$env:TEST_CAMPAIGN_ID="1"
python test_phase8_e2e.py
```

### Bash/Unix (Render)

```bash
export API_URL="https://suno-api-production.onrender.com"
export TEST_USER_EMAIL="creator@example.com"
export TEST_CAMPAIGN_ID="1"
python test_phase8_e2e.py
```

---

## What the Test Validates

1. **Migration 013** - ClipVariant and ClipPerformance tables exist
2. **Clip Generation** - POST /api/clips/generate works
3. **Job Execution** - Phase 8 AI runs (hooks, retention, variants, revenue)
4. **Performance Recording** - POST /api/clips/{id}/performance works
5. **ROI Calculation** - `ai_roi = estimated_value / ai_generation_cost_usd` is correct

---

## Expected Success Output

```
[HH:MM:SS] [TEST] TEST 1: MIGRATION 013 VERIFICATION
[HH:MM:SS] [PASS] ✓ ClipVariant table exists (0 records)
[HH:MM:SS] [PASS] ✓ ClipPerformance table exists (0 records)

[HH:MM:SS] [TEST] TEST 2: CLIP GENERATION (Phase 8 AI)
[HH:MM:SS] [PASS] ✓ Clip created: clip_id=123, job_id=abc-def-ghi

[HH:MM:SS] [TEST] TEST 3: JOB EXECUTION (Wait for AI Generation)
[HH:MM:SS] [WAIT] Waiting... (5s) status=queued
[HH:MM:SS] [PASS] ✓ Job completed: clip.status = needs_review
  - overall_score: 0.73
  - ai_generation_cost_usd: $0.01245
  - predicted_views: 12500
  - estimated_value: $15.62
  - ai_roi: 1256x

[HH:MM:SS] [TEST] TEST 4: PERFORMANCE RECORDING
[HH:MM:SS] [PASS] ✓ Performance recorded: id=456
  - platform: tiktok
  - views: 5000
  - completion_rate: 0.72

[HH:MM:SS] [TEST] TEST 5: ROI CALCULATION VERIFICATION
[HH:MM:SS] [PASS] ✓ ROI calculation verified: 1256x

[HH:MM:SS] [SUMMARY] SUMMARY
[HH:MM:SS] [PASS] ✓ PASS | Migration 013
[HH:MM:SS] [PASS] ✓ PASS | Clip Generation
[HH:MM:SS] [PASS] ✓ PASS | Job Execution
[HH:MM:SS] [PASS] ✓ PASS | Performance Recording
[HH:MM:SS] [PASS] ✓ PASS | ROI Calculation

[HH:MM:SS] [SUCCESS] ✓ PHASE 8 READY FOR PRODUCTION
```

---

## Troubleshooting

### Test Fails: "Campaign not found"
- `TEST_CAMPAIGN_ID` doesn't exist or `available=False`
- Run `find_test_data.py` to get valid ID

### Test Fails: "No active membership"
- `TEST_USER_EMAIL` exists but has no active membership
- Run `find_test_data.py` to get valid email

### Test Fails: "Clip already in progress"
- User already created a clip for this campaign
- Either: use different user, different campaign, or wait 2+ hours

### Test Fails: Job times out (120s)
- Worker not processing jobs
- Check: `redis-cli LLEN critical` on Render
- Check worker logs on Render

### Test Fails: ANTHROPIC_API_KEY error
- API key not set or expired
- Check: `env | grep ANTHROPIC` on Render

---

## Next Steps After Success

Once E2E test passes:
1. ✅ Phase 8 is LIVE
2. ✅ Production can handle clip generation with AI
3. ✅ ROI tracking is operational
4. ✅ Performance recording works
5. Next: Phase 9 (real platform webhooks, live posting)
