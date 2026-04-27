#!/bin/bash
# Verify migration 013 is applied and tables exist
# Run this on Render service shell

set -e

echo "=========================================="
echo "MIGRATION 013 VERIFICATION"
echo "=========================================="
echo ""

# Check current migration
echo "[1/4] Checking current Alembic revision..."
CURRENT=$(alembic current)
echo "Current revision: $CURRENT"
echo ""

# List last 3 migrations
echo "[2/4] Last 3 applied migrations..."
alembic history -r 3:
echo ""

# Check for clip_variants table
echo "[3/4] Checking clip_variants table..."
if psql "$DATABASE_URL" -c "\dt clip_variants" | grep -q "clip_variants"; then
    echo "✓ clip_variants table EXISTS"
    psql "$DATABASE_URL" -c "\d clip_variants" | head -20
else
    echo "✗ clip_variants table NOT FOUND"
    echo "ACTION: Run: alembic upgrade head"
    exit 1
fi
echo ""

# Check for clip_performances table
echo "[4/4] Checking clip_performances table..."
if psql "$DATABASE_URL" -c "\dt clip_performances" | grep -q "clip_performances"; then
    echo "✓ clip_performances table EXISTS"
    psql "$DATABASE_URL" -c "\d clip_performances" | head -20
else
    echo "✗ clip_performances table NOT FOUND"
    echo "ACTION: Run: alembic upgrade head"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ MIGRATION 013 VERIFIED - READY FOR PHASE 8"
echo "=========================================="
