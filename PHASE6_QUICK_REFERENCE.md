# Phase 6 Quick Reference

## What's New

**Two new write endpoints for user resources:**
1. Register clip sources (campaigns)
2. Update workspace settings

---

## Quick Examples

### Register a Campaign

```bash
curl -X POST https://suno-api-production.onrender.com/api/campaigns \
  -H "X-User-Email: user@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "source_url": "https://tiktok.com/@creator/video/123",
    "source_type": "tiktok",
    "title": "My Campaign",
    "keywords": ["viral"],
    "target_platforms": ["tiktok", "instagram"]
  }'
```

**Response (201 Created):**
```json
{
  "id": 1,
  "source_id": "https://tiktok.com/@creator/video/123",
  "source_type": "tiktok",
  "title": "My Campaign",
  "available": true
}
```

---

### Update Workspace Settings

```bash
curl -X PATCH https://suno-api-production.onrender.com/api/me/workspace \
  -H "X-User-Email: user@example.com" \
  -H "Content-Type: application/json" \
  -d '{"automation_enabled": false}'
```

**Response (200 OK):**
```json
{
  "workspace_id": "ws_...",
  "status": "active",
  "automation_enabled": false,
  "created_at": "2026-04-26T..."
}
```

---

## HTTP Status Codes

| Status | Meaning |
|--------|---------|
| 201 | Campaign created |
| 200 | Workspace updated |
| 401 | Missing/invalid X-User-Email |
| 403 | No membership or account |
| 409 | Duplicate campaign |

---

## Key Validations

### Campaign Creation
- ✓ User must have PENDING or ACTIVE membership
- ✓ Account must be provisioned
- ✓ Tier limits enforced (daily clip count)
- ✓ Duplicate sources blocked (same URL + type)

### Workspace Update
- ✓ User must have PENDING or ACTIVE membership
- ✓ Account must be provisioned
- ✓ Only set fields are updated (partial updates OK)

---

## Tier Limits

| Plan | Daily Clips | Platforms | Auto Posting |
|------|------------|-----------|-------------|
| STARTER | 10 | 3 | No |
| PRO | 30 | 6 | Yes |

---

## Membership Lifecycle

1. **User buys plan** → `membership.went_valid` webhook
2. **Webhook processed** → membership created with status=ACTIVE
3. **Account provisioned** → user can create campaigns
4. **API endpoints ready** → POST /campaigns, PATCH /workspace

---

## Testing

```bash
# Run full test suite
python test_phase6_endpoints.py

# Run webhook validation
WHOP_WEBHOOK_SECRET="ws_..." python webhook_membership_correct.py
```

---

## Common Errors

**"No active membership"**
- User hasn't purchased a plan yet
- Membership status is not PENDING/ACTIVE

**"Campaign source already registered"**
- Same source_url + source_type already exists
- Delete old campaign first (future feature)

**"Daily limit reached"**
- User has exceeded daily clip quota
- Quota resets at midnight UTC

**"No account provisioned"**
- Membership created but provisioning job failed
- Check worker logs

---

## Architecture

```
User buys plan (Whop)
    ↓
membership.went_valid webhook
    ↓
WebhookEventManager stores event
    ↓
RQ job: process_webhook_event
    ↓
MembershipLifecycleHandler.handle_purchase()
    ├─ Create User
    ├─ Discover Tier (plan_starter → STARTER, plan_pro → PRO)
    ├─ Create Membership (status=ACTIVE, activated_at=now)
    └─ Enqueue provision_account_job
         ↓
    AccountProvisioner.provision()
         ├─ Create Account
         ├─ Create Workspace on SUNO backend
         └─ Account ready for use
    ↓
POST /api/campaigns available
PATCH /api/me/workspace available
```

---

## Files

- `api/routes/user_resources.py` — Endpoint implementations
- `api/app.py` — Router registration
- `suno/billing/membership_lifecycle.py` — Tier mapping + membership logic
- `API_PHASE6_ENDPOINTS.md` — Full API documentation
- `test_phase6_endpoints.py` — Endpoint test suite
- `webhook_membership_correct.py` — Webhook validation test

---

## Key Fixes in Phase 6

1. **Membership Activation** ✓
   - Status now set to ACTIVE immediately on purchase
   - activated_at timestamp set
   - Fixed: Was staying in PENDING state

2. **Tier Mapping** ✓
   - plan_starter → STARTER (10 clips/day, 3 platforms)
   - plan_pro → PRO (30 clips/day, 6 platforms)
   - Fixed: Was using count-based heuristic (first plan=STARTER, others=PRO)

---

**Phase 6 Status:** COMPLETE ✓
**Production Ready:** Yes
**Last Updated:** 2026-04-26
