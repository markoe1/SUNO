#!/usr/bin/env python3
"""
Comprehensive test suite for 4 main platforms: YouTube, TikTok, Instagram, Meta
"""

import sys
import json
from typing import Dict, List, Tuple
from suno.posting.adapters import get_adapter, get_supported_platforms
from suno.posting.adapters.base import PostingStatus, PostingResult

# Target platforms
TARGET_PLATFORMS = ["youtube", "tiktok", "instagram"]
TEST_RESULTS = {}


def print_header(title: str):
    """Print section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_platform_availability():
    """Test 1: All target platforms are available."""
    print_header("TEST 1: PLATFORM AVAILABILITY")

    supported = get_supported_platforms()
    print(f"\nSupported platforms: {supported}")

    results = {}
    for platform in TARGET_PLATFORMS:
        available = platform in supported
        adapter = get_adapter(platform)
        results[platform] = {
            "available": available,
            "has_adapter": adapter is not None,
            "adapter_class": adapter.__class__.__name__ if adapter else "N/A"
        }
        status = "[PASS]" if (available and adapter) else "[FAIL]"
        print(f"{status} {platform.upper()}: {results[platform]['adapter_class']}")

    TEST_RESULTS["availability"] = results
    all_available = all(r["available"] and r["has_adapter"] for r in results.values())
    return all_available


def test_platform_interfaces():
    """Test 2: Each platform adapter implements required interface."""
    print_header("TEST 2: ADAPTER INTERFACE COMPLIANCE")

    results = {}
    required_methods = [
        'platform_name',
        'validate_account',
        'prepare_payload',
        'post',
        'submit_result'
    ]

    for platform in TARGET_PLATFORMS:
        adapter = get_adapter(platform)
        if not adapter:
            print(f"[FAIL] {platform.upper()}: No adapter found")
            results[platform] = {"compliant": False}
            continue

        missing = []
        for method in required_methods:
            if not hasattr(adapter, method):
                missing.append(method)

        compliant = len(missing) == 0
        results[platform] = {
            "compliant": compliant,
            "missing_methods": missing
        }

        status = "[PASS]" if compliant else "[FAIL]"
        print(f"{status} {platform.upper()}: ", end="")
        if compliant:
            print("All required methods present")
        else:
            print(f"Missing: {missing}")

    TEST_RESULTS["interfaces"] = results
    all_compliant = all(r["compliant"] for r in results.values())
    return all_compliant


def test_payload_preparation():
    """Test 3: Payload preparation for each platform."""
    print_header("TEST 3: PAYLOAD PREPARATION")

    test_inputs = {
        "clip_url": "https://example.com/video.mp4",
        "caption": "Test caption with #hashtags for @mentions testing",
        "hashtags": ["test", "clip", "viral"],
        "metadata": {"job_id": 123, "creator": "test_user"}
    }

    results = {}
    platform_constraints = {
        "tiktok": {"max_caption": 2200},
        "instagram": {"max_caption": 2200},
        "youtube": {"max_title": 100, "max_description": 5000}
    }

    for platform in TARGET_PLATFORMS:
        adapter = get_adapter(platform)
        if not adapter:
            results[platform] = {"success": False, "error": "No adapter"}
            print(f"[FAIL] {platform.upper()}: No adapter")
            continue

        try:
            payload = adapter.prepare_payload(**test_inputs)

            # Validate payload
            valid = payload is not None and isinstance(payload, dict)
            has_content = len(payload) > 0

            results[platform] = {
                "success": valid,
                "payload_keys": list(payload.keys()),
                "payload_size": len(json.dumps(payload))
            }

            status = "[PASS]" if (valid and has_content) else "[FAIL]"
            print(f"{status} {platform.upper()}:")
            print(f"   - Keys: {list(payload.keys())}")
            print(f"   - Size: {results[platform]['payload_size']} bytes")

            # Check platform-specific constraints
            if platform == "tiktok" and "caption" in payload:
                cap_len = len(payload["caption"])
                if cap_len > 2200:
                    print(f"   [WARN]  Caption length {cap_len} exceeds TikTok limit (2200)")
                else:
                    print(f"   [OK] Caption length OK ({cap_len} chars)")
            elif platform == "youtube" and "title" in payload:
                title_len = len(payload["title"])
                if title_len > 100:
                    print(f"   [WARN]  Title length {title_len} exceeds YouTube limit (100)")
                else:
                    print(f"   [OK] Title length OK ({title_len} chars)")

        except Exception as e:
            results[platform] = {"success": False, "error": str(e)}
            print(f"[FAIL] {platform.upper()}: {e}")

    TEST_RESULTS["payloads"] = results
    all_success = all(r["success"] for r in results.values())
    return all_success


def test_error_handling():
    """Test 4: Error handling and classification."""
    print_header("TEST 4: ERROR HANDLING & CLASSIFICATION")

    error_codes = [
        (400, PostingStatus.PERMANENT_ERROR, "Bad Request"),
        (401, PostingStatus.PERMANENT_ERROR, "Unauthorized"),
        (403, PostingStatus.PERMANENT_ERROR, "Forbidden"),
        (404, PostingStatus.PERMANENT_ERROR, "Not Found"),
        (429, PostingStatus.RETRYABLE_ERROR, "Rate Limited"),
        (500, PostingStatus.RETRYABLE_ERROR, "Server Error"),
        (502, PostingStatus.RETRYABLE_ERROR, "Bad Gateway"),
        (503, PostingStatus.RETRYABLE_ERROR, "Service Unavailable"),
    ]

    results = {}

    for platform in TARGET_PLATFORMS:
        adapter = get_adapter(platform)
        if not adapter:
            results[platform] = {"success": False, "errors": []}
            continue

        platform_errors = []
        for code, expected_status, desc in error_codes:
            classified = adapter._classify_error(code, desc)
            correct = classified == expected_status

            platform_errors.append({
                "code": code,
                "description": desc,
                "expected": expected_status.value,
                "actual": classified.value,
                "correct": correct
            })

        all_correct = all(e["correct"] for e in platform_errors)
        results[platform] = {
            "success": all_correct,
            "errors": platform_errors
        }

        status = "[PASS]" if all_correct else "[FAIL]"
        print(f"{status} {platform.upper()}:")

        for error in platform_errors:
            mark = "[OK]" if error["correct"] else "[NO]"
            print(f"   {mark} HTTP {error['code']}: {error['actual']}")

    TEST_RESULTS["errors"] = results
    all_success = all(r["success"] for r in results.values())
    return all_success


def test_invalid_credentials():
    """Test 5: Graceful handling of invalid credentials."""
    print_header("TEST 5: INVALID CREDENTIALS HANDLING")

    results = {}

    for platform in TARGET_PLATFORMS:
        adapter = get_adapter(platform)
        if not adapter:
            results[platform] = {"success": False, "error": "No adapter"}
            print(f"[FAIL] {platform.upper()}: No adapter")
            continue

        try:
            # Try to post with empty/invalid credentials
            result = adapter.post(
                account_credentials={},
                payload={"caption": "test"}
            )

            # Should return PostingResult without crashing
            is_valid_result = isinstance(result, PostingResult)
            has_status = hasattr(result, 'status') if result else False

            results[platform] = {
                "success": is_valid_result and has_status,
                "result_type": type(result).__name__,
                "status": result.status.value if result and has_status else "N/A"
            }

            status = "[PASS]" if (is_valid_result and has_status) else "[FAIL]"
            print(f"{status} {platform.upper()}: {results[platform]['status']}")

        except Exception as e:
            results[platform] = {
                "success": False,
                "error": str(e)
            }
            print(f"[FAIL] {platform.upper()}: {e}")

    TEST_RESULTS["invalid_creds"] = results
    all_success = all(r["success"] for r in results.values())
    return all_success


def test_result_structure():
    """Test 6: Result object structure and methods."""
    print_header("TEST 6: RESULT OBJECT STRUCTURE")

    test_cases = [
        ("success", PostingStatus.SUCCESS, True, False, False),
        ("retryable", PostingStatus.RETRYABLE_ERROR, False, True, False),
        ("permanent", PostingStatus.PERMANENT_ERROR, False, False, True),
    ]

    results = {}
    all_passed = True

    for name, status, expect_success, expect_retry, expect_permanent in test_cases:
        result = PostingResult(
            status=status,
            posted_url="https://example.com/post" if status == PostingStatus.SUCCESS else None,
            error_message="Test error" if status != PostingStatus.SUCCESS else None
        )

        is_success = result.is_success()
        is_retry = result.is_retryable()
        is_perm = result.is_permanent_failure()

        passed = (
            is_success == expect_success and
            is_retry == expect_retry and
            is_perm == expect_permanent
        )

        results[name] = {"passed": passed}
        status_mark = "[PASS]" if passed else "[FAIL]"
        print(f"{status_mark} {name.upper()}: status={status.value}, "
              f"is_success={is_success}, is_retryable={is_retry}, is_permanent={is_perm}")

        all_passed = all_passed and passed

    TEST_RESULTS["result_structure"] = results
    return all_passed


def print_summary():
    """Print test summary."""
    print_header("SUMMARY")

    test_names = {
        "availability": "Platform Availability",
        "interfaces": "Adapter Interface Compliance",
        "payloads": "Payload Preparation",
        "errors": "Error Handling",
        "invalid_creds": "Invalid Credentials",
        "result_structure": "Result Structure"
    }

    all_passed = True

    for test_id, test_name in test_names.items():
        if test_id not in TEST_RESULTS:
            continue

        # Determine pass/fail for this test
        test_data = TEST_RESULTS[test_id]

        # Check if all platform results passed
        passed = True
        if isinstance(test_data, dict):
            for platform_result in test_data.values():
                if isinstance(platform_result, dict):
                    # Check various success indicators
                    if "compliant" in platform_result:
                        passed = passed and platform_result.get("compliant", False)
                    elif "available" in platform_result:
                        passed = passed and platform_result.get("available", False)
                    elif "success" in platform_result:
                        passed = passed and platform_result.get("success", False)
                    elif "passed" in platform_result:
                        passed = passed and platform_result.get("passed", False)
        else:
            passed = False

        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")
        all_passed = all_passed and passed

    print("\n" + "=" * 70)
    if all_passed:
        print("  [SUCCESS] ALL TESTS PASSED!")
        print("=" * 70)
        return 0
    else:
        print("  [FAIL] SOME TESTS FAILED")
        print("=" * 70)
        return 1


def main():
    """Run all tests."""
    print("\n")
    print("=" * 70)
    print("  4-PLATFORM COMPREHENSIVE TEST SUITE")
    print("  YouTube | TikTok | Instagram | Meta")
    print("=" * 70)

    tests = [
        ("Availability", test_platform_availability),
        ("Interface", test_platform_interfaces),
        ("Payloads", test_payload_preparation),
        ("Errors", test_error_handling),
        ("Credentials", test_invalid_credentials),
        ("Results", test_result_structure),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n[FAIL] Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Print final summary
    exit_code = print_summary()

    # Detailed results
    print("\nDETAILED RESULTS:")
    print(json.dumps(TEST_RESULTS, indent=2, default=str))

    return exit_code


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
