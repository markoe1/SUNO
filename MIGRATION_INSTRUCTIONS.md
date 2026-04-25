# Database Migration Instructions

## Overview

SUNO uses Alembic for database schema management. Migrations are **strictly non-destructive** - they only create tables and indexes.

## Migrations Overview

| Revision | Name | Tables Created |
|----------|------|-----------------|
| 001_initial | Initial schema | users, user_secrets, campaigns, jobs, submissions, audit_log |
| 002_add_client_management | Client management | clients, editors, client_clips, invoices, performance_reports, clip_templates |
| 003_rename_paddle_to_whop | Rename payment provider | (schema changes only) |
| 004_add_whop_membership_id | Whop membership tracking | (schema changes only) |
| 005_add_webhook_events | Webhook event tracking | **webhook_events** (CRITICAL for production) |

## Running Migrations

### Local Development

```bash
cd /path/to/SUNO-repo
alembic upgrade head
```

### Production (Render)

**Option 1: Pre-Deploy Hook** (Recommended)
1. Go to Render dashboard → SUNO API PRODUCTION service
2. Settings → Build & Deploy
3. Add to "Pre-deploy command":
   ```bash
   cd /opt/render/project/src && alembic upgrade head
   ```
4. Save and redeploy

**Option 2: Manual Run via SSH**
```bash
# Connect to Render
render logs suno-api-production

# Then run migrations (requires database access via environment variables)
cd /opt/render/project/src
alembic upgrade head
```

## Verifying Migrations

After running migrations, verify all tables exist:

```bash
# Test the verification endpoint
curl -H "Authorization: Bearer YOUR_ADMIN_VERIFY_TOKEN" \
  https://suno-api-production.onrender.com/admin/verify-production

# Look for:
# "TABLES": "PASS"
# "WEBHOOK_STORAGE": "PASS"
```

## Migration Safety

✅ **Safe to run repeatedly** - Alembic tracks which migrations have been applied
✅ **Non-destructive** - Only creates tables, never drops them
✅ **Reversible** - Each migration can be rolled back if needed

### Rollback (Emergency Only)

```bash
# Revert to previous migration
alembic downgrade -1

# Revert to specific revision
alembic downgrade 004_add_whop_membership_id
```

## Troubleshooting

### Migration fails with "table already exists"
- This is normal - Alembic tracks applied migrations
- Run `alembic current` to see which migrations are applied
- If a migration is stuck, check the `alembic_version` table in PostgreSQL

### Connection refused
- Verify DATABASE_URL environment variable is set
- Ensure Neon PostgreSQL instance is running
- Check that DATABASE_URL uses `postgresql+asyncpg://` format

## Critical: webhook_events Table

The `webhook_events` table is essential for:
- Storing incoming Whop webhook events
- Tracking webhook lifecycle (received → validated → enqueued → processing → completed)
- Linking webhooks to RQ jobs for processing
- Enabling webhook replay and debugging

**This table MUST exist before processing any webhooks.**
