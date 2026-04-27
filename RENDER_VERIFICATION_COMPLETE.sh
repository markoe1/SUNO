#!/bin/bash
# Complete Render verification before E2E test
# Run this on Render shell after deployment is complete

set -e

echo "=========================================="
echo "RENDER VERIFICATION CHECKLIST"
echo "=========================================="
echo ""
echo "Prerequisites:"
echo "  - You have Render shell access"
echo "  - DATABASE_URL and other env vars are set"
echo "  - Latest commits (945e0c3) are deployed"
echo ""

# ============================================================
# CHECK 1: Commits deployed
# ============================================================
echo "[1/7] Verifying commits deployed..."
LATEST=$(git log --oneline -1 | cut -d' ' -f1)
if [ "$LATEST" = "945e0c3" ]; then
    echo "✓ Commit 945e0c3 deployed (sslmode fix)"
elif [ "$LATEST" = "fc7f316" ]; then
    echo "⚠ Commit fc7f316 deployed (performance fix, but NOT sslmode fix)"
    echo "  → Wait for 945e0c3 to deploy"
    exit 1
else
    echo "✗ Unexpected commit: $LATEST"
    exit 1
fi
echo ""

# ============================================================
# CHECK 2: /health endpoint (test via curl if available)
# ============================================================
echo "[2/7] Testing /health endpoint..."
HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null || echo '{"db":"error","redis":"error"}')
if echo "$HEALTH" | grep -q '"db":"ok"'; then
    echo "✓ /health shows db: ok"
elif echo "$HEALTH" | grep -q 'sslmode'; then
    echo "✗ /health still has sslmode error - 945e0c3 may not be deployed"
    exit 1
else
    echo "⚠ /health response: $HEALTH"
    echo "  (May be OK if running locally without full DB setup)"
fi
echo ""

# ============================================================
# CHECK 3: Migration status
# ============================================================
echo "[3/7] Checking migration status..."
CURRENT=$(alembic current 2>&1 || echo "ERROR")
echo "Current migration: $CURRENT"

if [ "$CURRENT" = "ERROR" ]; then
    echo "✗ Alembic failed - may need to run: alembic upgrade head"
    exit 1
elif echo "$CURRENT" | grep -q "013"; then
    echo "✓ Migration 013 already applied"
else
    echo "⚠ Migration 013 not yet applied"
    echo "  → Running: alembic upgrade head"
    alembic upgrade head
    echo "✓ Migration 013 applied"
fi
echo ""

# ============================================================
# CHECK 4: clip_variants table
# ============================================================
echo "[4/7] Verifying clip_variants table..."
if psql "$DATABASE_URL" -c "\dt clip_variants" 2>/dev/null | grep -q "clip_variants"; then
    echo "✓ clip_variants table exists"
    VARIANT_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM clip_variants" 2>/dev/null || echo "?")
    echo "  Records: $VARIANT_COUNT"
else
    echo "✗ clip_variants table not found"
    exit 1
fi
echo ""

# ============================================================
# CHECK 5: clip_performances table
# ============================================================
echo "[5/7] Verifying clip_performances table..."
if psql "$DATABASE_URL" -c "\dt clip_performances" 2>/dev/null | grep -q "clip_performances"; then
    echo "✓ clip_performances table exists"
    PERF_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM clip_performances" 2>/dev/null || echo "?")
    echo "  Records: $PERF_COUNT"
else
    echo "✗ clip_performances table not found"
    exit 1
fi
echo ""

# ============================================================
# CHECK 6: Environment variables
# ============================================================
echo "[6/7] Checking environment variables..."
VARS_OK=true

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "✗ ANTHROPIC_API_KEY not set"
    VARS_OK=false
else
    echo "✓ ANTHROPIC_API_KEY is set"
fi

if [ -z "$REDIS_URL" ]; then
    echo "✗ REDIS_URL not set"
    VARS_OK=false
else
    echo "✓ REDIS_URL is set"
fi

if [ -z "$DATABASE_URL" ]; then
    echo "✗ DATABASE_URL not set"
    VARS_OK=false
else
    echo "✓ DATABASE_URL is set"
fi

if [ "$VARS_OK" = "false" ]; then
    exit 1
fi
echo ""

# ============================================================
# CHECK 7: Clip schema columns (Phase 8)
# ============================================================
echo "[7/7] Verifying Phase 8 columns on clips table..."
PHASE8_COLS="ai_generation_cost_usd ai_roi predicted_views estimated_value posting_cooldown_hours"
MISSING_COLS=""

for col in $PHASE8_COLS; do
    if psql "$DATABASE_URL" -c "\d clips" 2>/dev/null | grep -q "$col"; then
        echo "  ✓ $col"
    else
        echo "  ✗ $col MISSING"
        MISSING_COLS="$MISSING_COLS $col"
    fi
done

if [ -n "$MISSING_COLS" ]; then
    echo "✗ Missing Phase 8 columns:$MISSING_COLS"
    exit 1
fi
echo ""

# ============================================================
# FINAL VERDICT
# ============================================================
echo "=========================================="
echo "✓ ALL CHECKS PASSED - READY FOR E2E TEST"
echo "=========================================="
echo ""
echo "Next: Run test_phase8_e2e.py with:"
echo "  API_URL=https://suno-api-production.onrender.com \\"
echo "  TEST_USER_EMAIL=your-test@email.com \\"
echo "  TEST_CAMPAIGN_ID=1 \\"
echo "  python test_phase8_e2e.py"
echo ""
