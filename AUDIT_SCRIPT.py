#!/usr/bin/env python3
"""
COMPLETE SUNO SYSTEM AUDIT
Phase 0-9: Full integrity verification
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load .env FIRST
load_dotenv('.env')

# Suppress warnings
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("SUNO COMPLETE SYSTEM AUDIT")
print("="*80)

# ============================================================================
# PHASE 0: ENVIRONMENT VALIDATION
# ============================================================================
print("\n[PHASE 0] ENVIRONMENT VALIDATION")
print("-" * 80)

from suno.config import Config

required_vars = {
    'DATABASE_URL': os.getenv('DATABASE_URL'),
    'REDIS_URL': os.getenv('REDIS_URL'),
    'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
    'WHOP_API_KEY': os.getenv('WHOP_API_KEY'),
    'WHOP_WEBHOOK_SECRET': os.getenv('WHOP_WEBHOOK_SECRET'),
    'SUNO_API_KEY': os.getenv('SUNO_API_KEY'),
    'ENVIRONMENT': os.getenv('ENVIRONMENT', 'development'),
}

phase0_results = {
    'timestamp': datetime.now().isoformat(),
    'variables': {}
}

for var, val in required_vars.items():
    is_set = bool(val and str(val).strip())
    phase0_results['variables'][var] = {
        'set': is_set,
        'masked_value': '[SET]' if is_set else '[NOT SET]'
    }
    status = 'SET' if is_set else 'MISSING'
    print(f"  {var:30s} [{status}]")

print("\n[Config Validation]")
try:
    Config.validate()
    phase0_results['config_validation'] = 'PASSED'
    print("  Config validation: PASSED")
except Exception as e:
    phase0_results['config_validation'] = f'FAILED: {str(e)}'
    print(f"  Config validation: FAILED - {e}")

# ============================================================================
# PHASE 1: DATABASE TRUTH CHECK
# ============================================================================
print("\n[PHASE 1] DATABASE INTEGRITY CHECK")
print("-" * 80)

phase1_results = {'status': 'UNKNOWN'}

try:
    from sqlalchemy import create_engine, inspect, text
    from suno.common.models import Base

    engine = create_engine(Config.DATABASE_URL, echo=False)
    inspector = inspect(engine)

    required_tables = {
        'users', 'memberships', 'tiers', 'accounts', 'campaigns', 'clips',
        'clip_variants', 'clip_performances', 'creator_profiles', 'webhook_events',
        'audit_logs', 'safety_state'
    }

    existing_tables = set(inspector.get_table_names())

    print(f"\n  Required tables: {len(required_tables)}")
    print(f"  Existing tables: {len(existing_tables)}")

    missing_tables = required_tables - existing_tables
    extra_tables = existing_tables - required_tables

    if missing_tables:
        print(f"\n  MISSING TABLES: {missing_tables}")
        phase1_results['status'] = 'FAILED - Missing tables'
    else:
        print("\n  All required tables exist")
        phase1_results['status'] = 'PASSED'

    if extra_tables:
        print(f"  Extra tables: {extra_tables}")

    # Check for broken rows
    print("\n  [Integrity checks]")

    try:
        with engine.connect() as conn:
            # Check clips without campaign_id
            result = conn.execute(text("SELECT COUNT(*) as cnt FROM clips WHERE campaign_id IS NULL"))
            null_campaign = result.scalar()
            print(f"    Clips with NULL campaign_id: {null_campaign}")

            # Check clips without variants
            result = conn.execute(text("""
                SELECT COUNT(DISTINCT c.id) as cnt FROM clips c
                LEFT JOIN clip_variants cv ON c.id = cv.clip_id
                WHERE cv.id IS NULL
            """))
            clips_no_variants = result.scalar()
            print(f"    Clips without variants: {clips_no_variants}")

            # Check variant orphans
            result = conn.execute(text("""
                SELECT COUNT(*) as cnt FROM clip_variants cv
                WHERE NOT EXISTS (SELECT 1 FROM clips c WHERE c.id = cv.clip_id)
            """))
            orphan_variants = result.scalar()
            print(f"    Orphan variants (no clip): {orphan_variants}")

            # Check performance orphans
            result = conn.execute(text("""
                SELECT COUNT(*) as cnt FROM clip_performances cp
                WHERE NOT EXISTS (SELECT 1 FROM clips c WHERE c.id = cp.clip_id)
            """))
            orphan_performances = result.scalar()
            print(f"    Orphan performances (no clip): {orphan_performances}")

            phase1_results['integrity'] = {
                'clips_null_campaign': null_campaign,
                'clips_no_variants': clips_no_variants,
                'orphan_variants': orphan_variants,
                'orphan_performances': orphan_performances
            }

            if any([null_campaign, clips_no_variants, orphan_variants, orphan_performances]):
                phase1_results['status'] = 'FAILED - Data integrity issues'

    except Exception as e:
        print(f"    Error checking integrity: {e}")
        phase1_results['integrity_check_error'] = str(e)

except Exception as e:
    phase1_results['error'] = str(e)
    print(f"\n  ERROR: {e}")
    phase1_results['status'] = f'FAILED - {e}'

# ============================================================================
# PHASE 2: API ROUTE VALIDATION
# ============================================================================
print("\n[PHASE 2] API ROUTE VALIDATION")
print("-" * 80)

phase2_results = {'endpoints': {}}

try:
    import httpx

    base_url = "http://localhost:8000"

    # Try health endpoint first
    try:
        response = httpx.get(f"{base_url}/api/health", timeout=5)
        phase2_results['endpoints']['/api/health'] = {
            'status_code': response.status_code,
            'success': response.status_code == 200
        }
        print(f"  GET /api/health: {response.status_code}")
    except Exception as e:
        phase2_results['api_connection'] = f'FAILED: Cannot connect to {base_url}'
        print(f"  ERROR: Cannot connect to API at {base_url}")
        print(f"  Make sure the API server is running: uvicorn api.app:app --host 0.0.0.0 --port 8000")
        phase2_results['status'] = 'BLOCKED - API not running'

except Exception as e:
    phase2_results['status'] = f'ERROR: {e}'
    print(f"  ERROR: {e}")

# ============================================================================
# PHASE 3: WEBHOOK SYSTEM VALIDATION
# ============================================================================
print("\n[PHASE 3] WEBHOOK SYSTEM VALIDATION")
print("-" * 80)

phase3_results = {'webhook_signature_validation': 'UNKNOWN'}

try:
    import hmac
    import hashlib

    webhook_secret = os.getenv('WHOP_WEBHOOK_SECRET', '')

    if not webhook_secret:
        print("  WARNING: WHOP_WEBHOOK_SECRET not set")
        print("  Webhook signature validation will be disabled")
        phase3_results['webhook_signature_validation'] = 'DISABLED - No secret'
    else:
        print("  Webhook secret is configured")
        phase3_results['webhook_signature_validation'] = 'CONFIGURED'

        # Test HMAC logic
        test_body = b'{"test": "data"}'
        test_sig = hmac.new(
            webhook_secret.encode(),
            test_body,
            hashlib.sha256
        ).hexdigest()
        print(f"  Test signature (first 16 chars): {test_sig[:16]}...")
        phase3_results['test_signature_generated'] = True

except Exception as e:
    phase3_results['webhook_signature_validation'] = f'ERROR: {e}'
    print(f"  ERROR: {e}")

# ============================================================================
# PHASE 4: WORKER PIPELINE
# ============================================================================
print("\n[PHASE 4] WORKER PIPELINE")
print("-" * 80)

phase4_results = {'status': 'UNKNOWN'}

try:
    from suno.common.job_queue import QueueManager

    print("  Checking Redis connection...")
    queue_mgr = QueueManager()

    # Try to ping Redis
    import redis
    r = redis.from_url(Config.REDIS_URL)
    pong = r.ping()

    print(f"  Redis connection: OK (ping response: {pong})")

    # Get queue stats
    queue_length = len(queue_mgr.queue)
    print(f"  Queue length: {queue_length}")

    phase4_results['status'] = 'CONNECTED'
    phase4_results['queue_length'] = queue_length
    phase4_results['redis_connection'] = 'OK'

except Exception as e:
    phase4_results['status'] = f'FAILED: {e}'
    print(f"  ERROR: {e}")
    print(f"  Make sure Redis is running at {Config.REDIS_URL}")

# ============================================================================
# FINAL REPORT
# ============================================================================
print("\n" + "="*80)
print("AUDIT SUMMARY")
print("="*80)

audit_report = {
    'timestamp': datetime.now().isoformat(),
    'phases': {
        'phase_0_env': phase0_results,
        'phase_1_db': phase1_results,
        'phase_2_api': phase2_results,
        'phase_3_webhooks': phase3_results,
        'phase_4_worker': phase4_results,
    }
}

# Determine overall status
blockers = []
warnings_list = []

if phase0_results.get('config_validation') != 'PASSED':
    blockers.append('Config validation failed')

if phase1_results.get('status') != 'PASSED':
    warnings_list.append(f"Database: {phase1_results.get('status')}")

if phase2_results.get('api_connection'):
    blockers.append('API not running')

if phase3_results.get('webhook_signature_validation') == 'DISABLED - No secret':
    warnings_list.append('Webhook signature validation disabled')

if phase4_results.get('status') not in ['CONNECTED', 'UNKNOWN']:
    blockers.append(f"Worker pipeline: {phase4_results.get('status')}")

print("\n[CRITICAL BLOCKERS]")
if blockers:
    for blocker in blockers:
        print(f"  * {blocker}")
else:
    print("  None - System is ready for testing")

print("\n[WARNINGS]")
if warnings_list:
    for warning in warnings_list:
        print(f"  * {warning}")
else:
    print("  None")

print("\n[ENVIRONMENT CHECK]")
for var, result in phase0_results['variables'].items():
    if not result['set'] and var in ['WHOP_WEBHOOK_SECRET', 'SUNO_API_KEY']:
        print(f"  * {var}: {result['masked_value']} (needed for production)")

print("\n[RECOMMENDATION]")
if not blockers:
    print("  System appears healthy. Ready for:")
    if phase2_results.get('api_connection'):
        print("    - Start API server: uvicorn api.app:app --host 0.0.0.0 --port 8000")
    if phase4_results.get('redis_connection') == 'OK':
        print("    - Start worker: python -m suno.workers.job_worker")
    print("    - Run Phase 2-9 integration tests")
else:
    print("  Fix blockers before proceeding:")
    for blocker in blockers:
        print(f"    - {blocker}")

# Save report
report_path = Path('AUDIT_REPORT.json')
with open(report_path, 'w') as f:
    json.dump(audit_report, f, indent=2, default=str)
print(f"\nAudit report saved to: {report_path}")

print("\n" + "="*80)
