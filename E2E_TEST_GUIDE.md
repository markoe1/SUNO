# SUNO Production E2E Test Guide

## Prerequisites
- WHOP_WEBHOOK_SECRET configured on Render (from Whop dashboard)
- PostgreSQL (Neon) with Alembic migrations applied
- Redis (Upstash) connection working
- Worker service running on Render

## Full Pipeline Flow
```
Webhook Received (POST /webhooks/whop)
    ↓ (signature verified with WHOP_WEBHOOK_SECRET)
    ↓ (payload parsed)
Event Stored in webhook_events table
    ↓
Job Enqueued to Redis Queue
    ↓
Worker Picks Up Job (from suno.workers.job_worker)
    ↓
Webhook Handler Executes (process_webhook_event)
    ↓
Membership Status Updated
    ↓
Test Complete
```

## Test 1: Verify API Health

```bash
# Check webhook receiver is responding
curl https://suno-api-production.onrender.com/webhooks/whop/status

# Expected: {"status":"ok","service":"whop_webhook_receiver"}
```

## Test 2: Send Signed Test Webhook

Replace `YOUR_WHOP_WEBHOOK_SECRET` with the actual secret from your Whop dashboard.

```bash
#!/bin/bash
WHOP_WEBHOOK_SECRET="YOUR_WHOP_WEBHOOK_SECRET"

# Create test payload
PAYLOAD='{
  "id": "evt_e2e_test_'$(date +%s)'",
  "action": "membership.went_valid",
  "data": {
    "customer_id": "cust_e2e_test",
    "user_id": "usr_e2e_test",
    "email": "e2etest@example.com",
    "plan": {"id": "plan_starter_test"},
    "membership_id": "mem_e2e_test"
  }
}'

# Compute HMAC signature
BODY=$(echo -n "$PAYLOAD")
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$WHOP_WEBHOOK_SECRET" | sed 's/^.* //')

echo "Webhook Payload:"
echo "$PAYLOAD" | python -m json.tool

echo ""
echo "Signature: $SIGNATURE"
echo ""

# Send webhook
echo "Sending webhook..."
RESPONSE=$(curl -X POST https://suno-api-production.onrender.com/webhooks/whop \
  -H "Content-Type: application/json" \
  -H "Whop-Signature: $SIGNATURE" \
  -d "$PAYLOAD" \
  -w "\n%{http_code}")

BODY=$(echo "$RESPONSE" | head -n -1)
STATUS=$(echo "$RESPONSE" | tail -n 1)

echo "Response Status: $STATUS"
echo "Response Body: $BODY"

if [ "$STATUS" = "200" ]; then
  echo "✓ Webhook accepted!"
else
  echo "✗ Webhook rejected. Check:"
  echo "  1. WHOP_WEBHOOK_SECRET is correct"
  echo "  2. Payload is valid JSON"
  echo "  3. Signature is computed correctly"
  exit 1
fi
```

## Test 3: Verify Database Storage

Once webhook is accepted, check if event was stored in webhook_events table:

```sql
-- Connect to production Neon database
SELECT
  id,
  whop_event_id,
  event_type,
  status,
  created_at
FROM webhook_events
WHERE whop_event_id LIKE 'evt_e2e_%'
ORDER BY created_at DESC
LIMIT 5;
```

Expected: One row with:
- `whop_event_id`: matches your test payload ID
- `status`: "validated" or "enqueued"
- `event_type`: "membership.went_valid"

## Test 4: Verify Redis Queue

Check if job was enqueued to the queue:

```python
import redis
import os

redis_url = os.getenv("REDIS_URL")
r = redis.from_url(redis_url)

# List jobs in critical queue
jobs = r.lrange("queue:critical", 0, -1)
print(f"Jobs in critical queue: {len(jobs)}")

# List most recent job IDs
queue_keys = r.keys("queue:*")
for key in queue_keys:
    length = r.llen(key)
    print(f"{key}: {length} jobs")
```

Expected:
- At least 1 job in "queue:critical"
- Job data contains webhook event information

## Test 5: Monitor Worker Processing

Check worker logs on Render:

1. Go to https://dashboard.render.com
2. Select your SUNO service
3. Go to "Logs"
4. Search for: `evt_e2e_test`

Expected log entries:
- `Enqueued webhook evt_e2e_test_* as job ...`
- Worker picking up the job
- `Processing membership.went_valid event`
- Job completion status

## Test 6: Verify Job Completion

Check webhook_events status after worker processes:

```sql
SELECT
  id,
  whop_event_id,
  event_type,
  status,
  job_id,
  completed_at
FROM webhook_events
WHERE whop_event_id LIKE 'evt_e2e_%'
ORDER BY created_at DESC
LIMIT 1;
```

Expected: `status` should be one of:
- "enqueued" → job queued, waiting for worker
- "processing" → worker is processing
- "completed" → job completed successfully
- "failed" → job failed (check error_message column)

## Troubleshooting

### 401 Invalid Signature
- Verify WHOP_WEBHOOK_SECRET is correct
- Verify signature is computed with the FULL JSON payload
- Check signature hasn't been whitespace-trimmed

### 400 Missing Event ID
- Verify payload has `"id"` field at top level
- Verify `"id"` is not empty

### 500 Database Error
- Check PostgreSQL connection on Render
- Verify Alembic migrations are applied: `alembic current`
- Check if sslmode parameter issue exists (see FIXES.md)

### Job Not Processing
- Verify Redis connection is working
- Check worker service is running on Render
- Check worker logs for errors
- Verify REDIS_URL environment variable is set

### Event Not Stored
- Check database migrations have been applied
- Verify DATABASE_URL format is correct
- Check Neon PostgreSQL is accessible

## Success Criteria

End-to-end test is successful when:
✓ Webhook endpoint accepts signed request (HTTP 202)
✓ Event stored in database with correct status
✓ Job enqueued to Redis
✓ Worker picks up job from queue
✓ Job completes (status: completed)
✓ Database records final status
