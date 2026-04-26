# SUNO Production Pipeline Test Instructions

## Current Status

✅ **API Service**: Responding at https://suno-api-production.onrender.com/webhooks/whop/status
⚠️ **Signature Verification**: Enabled (requires valid WHOP_WEBHOOK_SECRET)
📋 **Test Framework**: Ready (E2E_TEST_GUIDE.md + test_e2e_webhook.py)

## What You Need to Run the Test

1. **WHOP_WEBHOOK_SECRET** from your Whop dashboard
   - Go to https://dashboard.whop.com
   - Navigate to Webhooks
   - Copy your webhook signing secret

2. **Python 3.8+** with requests library
   ```bash
   pip install requests
   ```

## Quick Start (5 minutes)

### Option A: Python Script (Recommended)

```bash
cd /c/Users/ellio/SUNO-repo

python test_e2e_webhook.py --secret YOUR_WHOP_WEBHOOK_SECRET
```

This will:
- ✓ Check API health
- ✓ Generate valid test webhook payload
- ✓ Compute correct HMAC signature
- ✓ Send to production API
- ✓ Show next verification steps

### Option B: Manual curl Command

1. Get your WHOP_WEBHOOK_SECRET
2. Run the test script in E2E_TEST_GUIDE.md section "Test 2"
3. Verify response is HTTP 200/202 with status: "accepted"

## Verification Checklist

After sending the webhook, verify the full pipeline:

- [ ] **API accepts webhook** (HTTP 200/202 response)
- [ ] **Database stores event** (check webhook_events table)
- [ ] **Job enqueued** (check Redis queue for "critical" queue jobs)
- [ ] **Worker picks up job** (check Render logs for job processing)
- [ ] **Status updates** (check webhook_events.status = "completed")

See **E2E_TEST_GUIDE.md** for detailed verification SQL and commands.

## Expected Results

**Success**: Event flows through entire pipeline:
```
Webhook Accepted (API)
  ↓
Event Stored (Database)
  ↓
Job Queued (Redis)
  ↓
Worker Processes (Render Background Worker)
  ↓
Status Updated (Database: "completed")
```

**Response from API**:
```json
{"status": "accepted"}
```

**Check Render Logs**:
- Search for webhook event ID (evt_e2e_*)
- Look for: "Enqueued webhook ... as job ..."
- Look for: "Processing membership.went_valid event"

## Troubleshooting

### 401 Invalid Signature
**Problem**: Webhook rejected with invalid signature
**Fix**:
- Verify WHOP_WEBHOOK_SECRET is exactly correct (no extra spaces)
- Check it matches what's in Render environment
- Regenerate signature with correct secret

### 500 Database Error
**Problem**: API returns database error
**Fix**:
- Verify PostgreSQL migrations applied: `alembic current`
- Check DATABASE_URL in Render (shouldn't have ?sslmode=require)
- See /fixes/db_connection_fix.md for sslmode parameter issue

### Job Not Processing
**Problem**: Event stored but job never completes
**Fix**:
- Verify worker service is running on Render
- Check REDIS_URL in Render (Upstash connection)
- Monitor Render logs: https://dashboard.render.com

## Next Steps

1. **Run the test** with your WHOP_WEBHOOK_SECRET
2. **Verify each stage** using SQL + Render logs
3. **Check worker logs** for any errors
4. **Document any issues** found

Once complete, you'll have verified:
- Webhook signature verification ✓
- Database connectivity ✓
- Redis queue system ✓
- Worker processing ✓
- Full end-to-end pipeline ✓

## Files Reference

- `E2E_TEST_GUIDE.md` - Detailed step-by-step guide with SQL queries
- `test_e2e_webhook.py` - Automated test script with diagnostics
- `api/routes/webhooks.py` - Webhook handler implementation
- `suno/billing/webhook_events.py` - Event storage logic
- `suno/common/job_queue.py` - Job queue manager
- `suno/workers/job_worker.py` - Worker processor

## Support

If you encounter issues:
1. Check Render logs: https://dashboard.render.com/services
2. Verify env vars are set: DATABASE_URL, REDIS_URL, WHOP_WEBHOOK_SECRET
3. Check database migrations: `alembic status`
4. Review E2E_TEST_GUIDE.md troubleshooting section
