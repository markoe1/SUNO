# SUNO Background Worker Service Setup

## Service Configuration

**Type**: Background Worker
**Name**: `suno-worker`
**Repository**: `https://github.com/markoe1/SUNO.git`
**Branch**: `main`
**Runtime**: Python

## Build & Start Commands

**Build Command**:
```bash
pip install -r requirements.txt
```

**Start Command**:
```bash
python -m suno.workers.job_worker
```

## Environment Variables

Copy these from SUNO API PRODUCTION service:

| Variable | Value | Source |
|----------|-------|--------|
| `DATABASE_URL` | postgresql+asyncpg://... | From API service |
| `REDIS_URL` | rediss://... | From API service |
| `ANTHROPIC_API_KEY` | sk-... | From API service |
| `WHOP_API_KEY` | ... | From API service |
| `WHOP_WEBHOOK_SECRET` | ... | From API service |

## Service Settings

- **Disk**: Default (not needed for worker)
- **Healthcheck**: Disable (worker runs continuously, doesn't expose HTTP)
- **Auto-deploy**: Yes (from git)
- **Memory**: Default

## What This Worker Does

The job worker:
1. **Connects to Redis queue** - Listens for enqueued jobs
2. **Processes jobs in priority order**:
   - CRITICAL: Provisioning, revocation
   - HIGH: Caption generation
   - NORMAL: Posting, scheduling
   - LOW: Analytics, cleanup
3. **Runs continuously** - Doesn't stop unless manually killed
4. **Handles retries** - Automatic retry logic on failures
5. **Logs output** - Visible in Render logs

## How to Verify It's Working

After deploying:

1. **Check Render logs**:
   ```
   Dashboard → suno-worker → Logs
   ```
   Look for:
   ```
   Started SUNO worker
   Listening on queues...
   Processing job...
   ```

2. **Send a test webhook**:
   ```bash
   curl -X POST https://suno-api-production.onrender.com/webhooks/whop \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Signature: YOUR_HMAC_HERE" \
     -d '{"event":"order.completed","data":{...}}'
   ```

3. **Check database**:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://suno-api-production.onrender.com/admin/verify-production
   ```

4. **Worker processes job**:
   - Event stored in webhook_events table ✅
   - Job created and queued in Redis ✅
   - Worker picks up and processes ✅
   - Status updated in database ✅

## Troubleshooting

### Worker doesn't start

Check logs for:
- Missing environment variables
- Connection errors to Redis/PostgreSQL
- Import errors in suno module

### Jobs not processing

- Verify Redis URL is correct
- Check worker logs for errors
- Ensure DATABASE_URL is valid

### High memory usage

Worker maintains connection pools. Normal behavior.
Adjust if necessary via Render service settings.

## Critical Notes

⚠️ **Worker must run continuously** - It's a background process
⚠️ **Do NOT use web service type** - Use Background Worker type
⚠️ **Do NOT set a healthcheck** - Worker doesn't expose HTTP
⚠️ **Environment vars must match API service** - Same credentials
