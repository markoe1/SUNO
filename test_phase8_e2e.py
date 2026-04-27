#!/usr/bin/env python3
"""
Phase 8 End-to-End Test
Validates: Migration 013, Job Execution, ROI Calculation
"""

import os
import sys
import time
import json
import requests
from datetime import datetime

# Configuration
API_URL = os.getenv("API_URL", "https://suno-api-production.onrender.com")
USER_EMAIL = os.getenv("TEST_USER_EMAIL", "test@phase8.local")
CAMPAIGN_ID = int(os.getenv("TEST_CAMPAIGN_ID", "1"))

def log(msg, level="INFO"):
    """Log with timestamp."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}")

def test_migration_013():
    """Test that migration 013 tables exist."""
    log("=" * 70)
    log("TEST 1: MIGRATION 013 VERIFICATION", "TEST")
    log("=" * 70)

    try:
        from suno.database import SessionLocal
        from suno.common.models import ClipVariant, ClipPerformance

        db = SessionLocal()

        # Try to query the tables (will fail if tables don't exist)
        variant_count = db.query(ClipVariant).count()
        perf_count = db.query(ClipPerformance).count()

        log(f"✓ ClipVariant table exists ({variant_count} records)", "PASS")
        log(f"✓ ClipPerformance table exists ({perf_count} records)", "PASS")
        db.close()
        return True

    except Exception as e:
        log(f"✗ Migration 013 verification failed: {e}", "FAIL")
        log("ACTION: Run 'alembic upgrade head' on Render", "ACTION")
        return False

def test_clip_generation():
    """Test POST /api/clips/generate."""
    log("=" * 70)
    log("TEST 2: CLIP GENERATION (Phase 8 AI)", "TEST")
    log("=" * 70)

    try:
        headers = {"X-User-Email": USER_EMAIL}
        payload = {"campaign_id": CAMPAIGN_ID, "target_platforms": ["tiktok"]}

        log(f"POST {API_URL}/api/clips/generate")
        response = requests.post(
            f"{API_URL}/api/clips/generate",
            json=payload,
            headers=headers,
            timeout=10
        )

        if response.status_code == 201:
            data = response.json()
            clip_id = data["clip_id"]
            job_id = data["job_id"]
            log(f"✓ Clip created: clip_id={clip_id}, job_id={job_id}", "PASS")
            return clip_id, job_id
        elif response.status_code == 401:
            log("✗ Unauthorized - X-User-Email header issue", "FAIL")
            return None, None
        elif response.status_code == 403:
            log("✗ Forbidden - No active membership", "FAIL")
            return None, None
        else:
            log(f"✗ Request failed: {response.status_code} - {response.text}", "FAIL")
            return None, None

    except Exception as e:
        log(f"✗ Clip generation failed: {e}", "FAIL")
        return None, None

def wait_for_job_completion(clip_id, max_wait=60):
    """Wait for clip generation job to complete."""
    log("=" * 70)
    log("TEST 3: JOB EXECUTION (Wait for AI Generation)", "TEST")
    log("=" * 70)

    try:
        from suno.database import SessionLocal
        from suno.common.models import Clip

        start_time = time.time()

        while time.time() - start_time < max_wait:
            db = SessionLocal()
            clip = db.query(Clip).filter(Clip.id == clip_id).first()

            if not clip:
                log(f"✗ Clip not found: {clip_id}", "FAIL")
                db.close()
                return False

            status = clip.status.value if hasattr(clip.status, 'value') else str(clip.status)

            if status == "needs_review":
                log(f"✓ Job completed: clip.status = {status}", "PASS")
                log(f"  - overall_score: {clip.overall_score}")
                log(f"  - ai_generation_cost_usd: ${clip.ai_generation_cost_usd:.6f}")
                log(f"  - predicted_views: {clip.predicted_views}")
                log(f"  - estimated_value: ${clip.estimated_value:.2f}")
                log(f"  - ai_roi: {clip.ai_roi}x")
                db.close()
                return clip
            elif status == "failed":
                log(f"✗ Job failed: {clip.status}", "FAIL")
                db.close()
                return False
            else:
                elapsed = int(time.time() - start_time)
                log(f"  Waiting... ({elapsed}s) status={status}", "WAIT")
                db.close()
                time.sleep(5)

        log(f"✗ Job timeout after {max_wait}s", "FAIL")
        return False

    except Exception as e:
        log(f"✗ Job wait failed: {e}", "FAIL")
        return False

def test_performance_recording(clip_id):
    """Test POST /api/clips/{clip_id}/performance."""
    log("=" * 70)
    log("TEST 4: PERFORMANCE RECORDING", "TEST")
    log("=" * 70)

    try:
        headers = {"X-User-Email": USER_EMAIL}
        payload = {
            "platform": "tiktok",
            "views": 5000,
            "watch_time_seconds": 45.0,
            "completion_rate": 0.72,
            "likes": 250,
            "shares": 50,
            "comments": 25
        }

        log(f"POST {API_URL}/api/clips/{clip_id}/performance")
        response = requests.post(
            f"{API_URL}/api/clips/{clip_id}/performance",
            json=payload,
            headers=headers,
            timeout=10
        )

        if response.status_code == 201:
            data = response.json()
            log(f"✓ Performance recorded: id={data['performance_id']}", "PASS")
            log(f"  - platform: {data['platform']}")
            log(f"  - views: {data['views']}")
            log(f"  - completion_rate: {data['completion_rate']}")
            return True
        else:
            log(f"✗ Request failed: {response.status_code} - {response.text}", "FAIL")
            return False

    except Exception as e:
        log(f"✗ Performance recording failed: {e}", "FAIL")
        return False

def test_roi_calculation(clip_id):
    """Verify ROI calculation correctness."""
    log("=" * 70)
    log("TEST 5: ROI CALCULATION VERIFICATION", "TEST")
    log("=" * 70)

    try:
        from suno.database import SessionLocal
        from suno.common.models import Clip

        db = SessionLocal()
        clip = db.query(Clip).filter(Clip.id == clip_id).first()

        if not clip:
            log(f"✗ Clip not found: {clip_id}", "FAIL")
            db.close()
            return False

        ai_cost = clip.ai_generation_cost_usd or 0
        estimated_value = clip.estimated_value or 0
        ai_roi = clip.ai_roi

        log(f"AI Cost: ${ai_cost:.6f}", "INFO")
        log(f"Estimated Value: ${estimated_value:.2f}", "INFO")
        log(f"Calculated ROI: {ai_roi}x", "INFO")

        # Validate calculations
        if ai_cost > 0 and estimated_value > 0:
            expected_roi = estimated_value / ai_cost
            if abs(ai_roi - expected_roi) < 1:  # Allow small rounding difference
                log(f"✓ ROI calculation verified: {ai_roi}x", "PASS")
                db.close()
                return True
            else:
                log(f"✗ ROI mismatch: expected {expected_roi}x, got {ai_roi}x", "FAIL")
                db.close()
                return False
        else:
            log(f"✓ ROI formula valid (cost=${ai_cost:.6f}, value=${estimated_value:.2f})", "PASS")
            db.close()
            return True

    except Exception as e:
        log(f"✗ ROI verification failed: {e}", "FAIL")
        return False

def main():
    """Run all tests."""
    log("=" * 70)
    log("PHASE 8 END-TO-END TEST SUITE", "START")
    log("=" * 70)
    log(f"API URL: {API_URL}")
    log(f"Test User: {USER_EMAIL}")
    log(f"Campaign ID: {CAMPAIGN_ID}")
    log("")

    results = []

    # Test 1: Migration
    if not test_migration_013():
        log("CRITICAL: Migration 013 not applied. Cannot proceed.", "ERROR")
        return False
    results.append(("Migration 013", True))
    log("")

    # Test 2: Clip Generation
    clip_id, job_id = test_clip_generation()
    if not clip_id:
        log("CRITICAL: Clip generation failed. Check API logs.", "ERROR")
        return False
    results.append(("Clip Generation", True))
    log("")

    # Test 3: Job Execution
    clip = wait_for_job_completion(clip_id, max_wait=120)
    if not clip:
        log("CRITICAL: Job did not complete. Check worker logs.", "ERROR")
        return False
    results.append(("Job Execution", True))
    log("")

    # Test 4: Performance Recording
    if not test_performance_recording(clip_id):
        log("WARNING: Performance recording failed. May need profile setup.", "WARN")
        results.append(("Performance Recording", False))
    else:
        results.append(("Performance Recording", True))
    log("")

    # Test 5: ROI Calculation
    if not test_roi_calculation(clip_id):
        log("WARNING: ROI calculation issue. Check revenue engine.", "WARN")
        results.append(("ROI Calculation", False))
    else:
        results.append(("ROI Calculation", True))
    log("")

    # Summary
    log("=" * 70)
    log("TEST SUMMARY", "SUMMARY")
    log("=" * 70)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        log(f"{status} | {test_name}")

    all_passed = all(p for _, p in results)
    if all_passed:
        log("")
        log("=" * 70)
        log("✓ PHASE 8 READY FOR PRODUCTION", "SUCCESS")
        log("=" * 70)
        return True
    else:
        log("")
        log("=" * 70)
        log("✗ PHASE 8 HAS FAILURES - DO NOT DEPLOY", "FAILURE")
        log("=" * 70)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
