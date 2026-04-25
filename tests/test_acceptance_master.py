"""
SUNO ACCEPTANCE TEST MASTER
Runs all 6 test gates and provides final production readiness report.
"""

import sys
from datetime import datetime

def run_all_gates():
    """Execute all 6 acceptance test gates."""

    results = {
        "gate_1": None,  # Webhook Auth + Idempotency
        "gate_2": None,  # Queue Priority
        "gate_3": None,  # Provisioning Failure
        "gate_4": None,  # Caption Generation + Retry
        "gate_5": None,  # Platform Adapters
        "gate_6": None,  # End-to-End Lifecycle
    }

    print("\n" + "="*70)
    print("🚀 SUNO SYSTEM - PRODUCTION READINESS ACCEPTANCE TEST")
    print("="*70)
    print(f"Test Start: {datetime.utcnow().isoformat()}")
    print("="*70)

    # GATE 1
    print("\n[GATE 1/6] WEBHOOK AUTHENTICITY + IDEMPOTENCY")
    try:
        from tests.test_acceptance_gate1 import test_webhook_signature_verification, test_webhook_signature_rejection, test_webhook_idempotency, test_event_status_transitions
        from suno.database import SessionLocal

        test_webhook_signature_verification()
        test_webhook_signature_rejection()

        db = SessionLocal()
        try:
            test_webhook_idempotency(db)
            test_event_status_transitions(db)
        finally:
            db.close()

        results["gate_1"] = "PASS"
        print("Result: ✅ PASS\n")
    except Exception as e:
        results["gate_1"] = "FAIL"
        print(f"Result: ❌ FAIL - {e}\n")

    # GATE 2
    print("[GATE 2/6] QUEUE PRIORITY EXECUTION")
    try:
        from tests.test_acceptance_gate2 import test_queue_priority
        test_queue_priority()
        results["gate_2"] = "PASS"
        print("Result: ✅ PASS\n")
    except Exception as e:
        results["gate_2"] = "FAIL"
        print(f"Result: ❌ FAIL - {e}\n")

    # GATE 3
    print("[GATE 3/6] PROVISIONING FAILURE BEHAVIOR")
    try:
        from tests.test_acceptance_gate3 import test_provisioning_without_api_key, test_provisioning_with_stub_api, test_provisioning_idempotency
        from suno.database import SessionLocal

        db = SessionLocal()
        try:
            test_provisioning_without_api_key(db)
            test_provisioning_with_stub_api(db)
            test_provisioning_idempotency(db)
        finally:
            db.close()

        results["gate_3"] = "PASS"
        print("Result: ✅ PASS\n")
    except Exception as e:
        results["gate_3"] = "FAIL"
        print(f"Result: ❌ FAIL - {e}\n")

    # GATE 4
    print("[GATE 4/6] CAPTION GENERATION + RETRY")
    try:
        from tests.test_acceptance_gate4 import test_caption_generation_success, test_caption_retry_logic, test_caption_clean_failure
        from suno.database import SessionLocal

        db = SessionLocal()
        try:
            test_caption_generation_success(db)
            test_caption_retry_logic(db)
            test_caption_clean_failure(db)
        finally:
            db.close()

        results["gate_4"] = "PASS"
        print("Result: ✅ PASS\n")
    except Exception as e:
        results["gate_4"] = "FAIL"
        print(f"Result: ❌ FAIL - {e}\n")

    # GATE 5
    print("[GATE 5/6] PLATFORM ADAPTER EXECUTION")
    try:
        from tests.test_acceptance_gate5 import (
            test_adapter_interface, test_adapter_payload_validation,
            test_adapter_error_classification, test_adapter_result_structure,
            test_adapter_doesnt_crash_on_failure
        )

        test_adapter_interface()
        test_adapter_payload_validation()
        test_adapter_error_classification()
        test_adapter_result_structure()
        test_adapter_doesnt_crash_on_failure()

        results["gate_5"] = "PASS"
        print("Result: ✅ PASS\n")
    except Exception as e:
        results["gate_5"] = "FAIL"
        print(f"Result: ❌ FAIL - {e}\n")

    # GATE 6
    print("[GATE 6/6] END-TO-END LIFECYCLE")
    try:
        from tests.test_acceptance_gate6 import test_full_success_path, test_failure_path, test_observability
        from suno.database import SessionLocal

        db = SessionLocal()
        try:
            test_full_success_path(db)
            test_failure_path(db)
            test_observability(db)
        finally:
            db.close()

        results["gate_6"] = "PASS"
        print("Result: ✅ PASS\n")
    except Exception as e:
        results["gate_6"] = "FAIL"
        print(f"Result: ❌ FAIL - {e}\n")

    # Generate Report
    print("\n" + "="*70)
    print("ACCEPTANCE TEST REPORT")
    print("="*70)

    print("\n📊 SUMMARY TABLE:")
    print("-" * 70)
    print(f"{'Gate':<8} | {'Test':<45} | {'Status':<8}")
    print("-" * 70)

    gates = [
        ("1", "Webhook Authenticity + Idempotency", results["gate_1"]),
        ("2", "Queue Priority Execution", results["gate_2"]),
        ("3", "Provisioning Failure Behavior", results["gate_3"]),
        ("4", "Caption Generation + Retry", results["gate_4"]),
        ("5", "Platform Adapter Execution", results["gate_5"]),
        ("6", "End-to-End Lifecycle", results["gate_6"]),
    ]

    for gate, test, status in gates:
        status_icon = "✅ PASS" if status == "PASS" else "❌ FAIL"
        print(f"{gate:<8} | {test:<45} | {status_icon:<8}")

    print("-" * 70)

    # Final Verdict
    all_pass = all(v == "PASS" for v in results.values())
    fail_count = sum(1 for v in results.values() if v == "FAIL")
    pass_count = sum(1 for v in results.values() if v == "PASS")

    print(f"\nTotal: {pass_count}/6 PASS, {fail_count}/6 FAIL")
    print(f"Test Completion: {datetime.utcnow().isoformat()}")

    print("\n" + "="*70)
    if all_pass:
        print("🎉 FINAL VERDICT: READY FOR PRODUCTION USE")
        print("="*70)
        print("""
✅ ALL 6 GATES PASSED

System Capabilities Verified:
✅ Webhook authenticity and duplicate prevention
✅ Queue priority execution (CRITICAL > HIGH > NORMAL > LOW)
✅ Graceful provisioning failure handling
✅ Caption generation with retry and dead-letter support
✅ All 5 platform adapters working correctly
✅ Complete end-to-end pipeline from webhook to posting

System Properties Validated:
✅ OBSERVABLE - Every stage tracked and visible
✅ RETRYABLE - Smart retry logic with dead-letter fallback
✅ DURABLE - RQ + Redis + PostgreSQL persistence
✅ IDEMPOTENT - No duplicate effects from repeated operations

Status: PRODUCTION READY 🚀
        """)
    else:
        print("❌ FINAL VERDICT: NEEDS FIXES")
        print("="*70)
        print(f"\n{fail_count} gate(s) failed. See details above.")

    print("="*70 + "\n")

    return all_pass

if __name__ == "__main__":
    success = run_all_gates()
    sys.exit(0 if success else 1)
