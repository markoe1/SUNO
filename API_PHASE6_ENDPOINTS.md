# Phase 6 API Endpoints

**Status:** Production Ready
**Date:** April 26, 2026
**Auth:** X-User-Email header (required)

---

## POST /api/campaigns

Register a new clip source (TikTok/YouTube/etc.) as a campaign.

### Request

```http
POST /api/campaigns HTTP/1.1
Host: suno-api-production.onrender.com
X-User-Email: user@example.com
Content-Type: application/json

{
  "source_url": "https://www.tiktok.com/@creator/video/123",
  "source_type": "tiktok",
  "title": "My Campaign",
  "keywords": ["viral", "funny"],
  "target_platforms": ["tiktok", "instagram"],
  "tone": "casual",
  "style": "trending",
  "duration_seconds": 30
}
```

### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| source_url | string | Yes | URL of the source (TikTok, YouTube, etc.) |
| source_type | string | Yes | Platform type: `tiktok`, `youtube`, `instagram`, etc. |
| title | string | Yes | Campaign title (max 500 chars) |
| keywords | array[string] | No | Search keywords/tags |
| target_platforms | array[string] | No | Platforms to post to |
| tone | string | No | Tone: `casual`, `professional`, `funny`, etc. |
| style | string | No | Style: `trending`, `educational`, `entertaining`, etc. |
| duration_seconds | integer | No | Clip duration in seconds (default: 30) |

### Response (201 Created)

```json
{
  "id": 1,
  "source_id": "https://www.tiktok.com/@creator/video/123",
  "source_type": "tiktok",
  "title": "My Campaign",
  "keywords": ["viral", "funny"],
  "target_platforms": ["tiktok", "instagram"],
  "tone": "casual",
  "style": "trending",
  "duration_seconds": 30,
  "available": true
}
```

### Error Responses

**401 Unauthorized** - Missing or invalid X-User-Email header
```json
{"detail": "Missing X-User-Email header"}
```

**403 Forbidden** - No active membership
```json
{"detail": "No active membership"}
```

**403 Forbidden** - Daily clip limit exceeded
```json
{"detail": "Cannot create clip: Daily limit reached (10 clips)"}
```

**409 Conflict** - Campaign source already registered
```json
{"detail": "Campaign source already registered"}
```

### Logic

1. Validate X-User-Email header → find User
2. Check PENDING or ACTIVE membership → 403 if none
3. Check account exists → 403 if none
4. Check tier limits (can_create_clip) → 403 if exceeded
5. Check (source_url, source_type) unique constraint → 409 if exists
6. Create Campaign record
7. Return 201 with CampaignResponse

### Notes

- Duplicate campaigns are prevented via unique constraint on (source_id, source_type)
- Tier limits are enforced per day (resets at midnight UTC)
- STARTER tier: max 10 clips/day
- PRO tier: max 30 clips/day

---

## PATCH /api/me/workspace

Update workspace settings for the current user.

### Request

```http
PATCH /api/me/workspace HTTP/1.1
Host: suno-api-production.onrender.com
X-User-Email: user@example.com
Content-Type: application/json

{
  "automation_enabled": false
}
```

### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| automation_enabled | boolean | No | Enable/disable automation |

**Note:** Only fields that are explicitly set will be updated (partial updates supported).

### Response (200 OK)

```json
{
  "workspace_id": "ws_b69bbfeeb627",
  "status": "active",
  "automation_enabled": false,
  "created_at": "2026-04-26T09:55:26.031151+00:00"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| workspace_id | string | Unique workspace identifier |
| status | string | Current status: `active`, `paused`, `revoked` |
| automation_enabled | boolean | Automation enabled/disabled |
| created_at | string | ISO 8601 timestamp when account was created |

### Error Responses

**401 Unauthorized** - Missing or invalid X-User-Email header
```json
{"detail": "Missing X-User-Email header"}
```

**403 Forbidden** - No active membership
```json
{"detail": "No active membership"}
```

**403 Forbidden** - No account provisioned
```json
{"detail": "No account provisioned"}
```

### Logic

1. Validate X-User-Email header → find User
2. Check PENDING or ACTIVE membership → 403 if none
3. Find Account via membership_id → 403 if none
4. Apply only explicitly set fields (exclude_unset=True)
5. Update Account record
6. Return 200 with updated WorkspaceResponse

### Notes

- Only fields explicitly set in request are updated
- Omitted fields are not changed
- All workspace fields are immutable except `automation_enabled`
- Status changes require webhook events (purchase, cancellation, etc.)

---

## Error Handling

All endpoints follow these HTTP status codes:

| Status | Meaning | Example |
|--------|---------|---------|
| 200 OK | Success (for PATCH) | Workspace updated |
| 201 Created | Resource created | Campaign registered |
| 400 Bad Request | Invalid request format | Malformed JSON |
| 401 Unauthorized | Authentication failed | Missing header |
| 403 Forbidden | Permission denied | No membership |
| 409 Conflict | Resource conflict | Duplicate campaign |
| 500 Internal Server Error | Server error | Database error |

---

## Authentication

Both endpoints require the `X-User-Email` header:

```
X-User-Email: user@example.com
```

The email must match a User record in the database that:
- Has at least one PENDING or ACTIVE Membership
- Has a provisioned Account

---

## Testing

Use the provided test script:

```bash
python test_phase6_endpoints.py
```

This will test:
1. Campaign creation
2. Duplicate prevention
3. Workspace update
4. Partial update functionality

---

## Rate Limiting

- Campaign creation: 1 request per 2 seconds (per user)
- Workspace update: 1 request per 5 seconds (per user)

---

## Changelog

### v1.0 (2026-04-26)
- Initial release
- POST /api/campaigns endpoint
- PATCH /api/me/workspace endpoint
- Membership activation fix (status=ACTIVE)
- Plan_id → tier mapping fix
