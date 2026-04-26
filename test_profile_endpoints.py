"""
Test script for profile endpoints.
Tests: /me, /me/membership, /me/workspace, /me/limits, /dashboard/data
"""

import requests
import json
from datetime import datetime

# Test configuration
API_URL = "https://suno-api-production.onrender.com/api"
TEST_USER_EMAIL = "final-0ce0fd6c@example.com"

headers = {
    "X-User-Email": TEST_USER_EMAIL,
    "Content-Type": "application/json",
}

print("=" * 70)
print("SUNO PRODUCT LAYER - ENDPOINT TESTS")
print("=" * 70)
print(f"\nTest User: {TEST_USER_EMAIL}")
print(f"API URL: {API_URL}")
print(f"Timestamp: {datetime.now().isoformat()}")
print()

# Test endpoints
endpoints = [
    ("GET /me", f"{API_URL}/me"),
    ("GET /me/membership", f"{API_URL}/me/membership"),
    ("GET /me/workspace", f"{API_URL}/me/workspace"),
    ("GET /me/limits", f"{API_URL}/me/limits"),
    ("GET /dashboard/data", f"{API_URL}/dashboard/data"),
]

results = []

for name, url in endpoints:
    print(f"\n{'=' * 70}")
    print(f"Test: {name}")
    print(f"URL: {url}")
    print("-" * 70)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        status = response.status_code

        print(f"Status: {status}")

        if status == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            results.append((name, "✅ PASS"))
        else:
            print(f"Error: {response.text}")
            results.append((name, f"❌ FAIL ({status})"))

    except Exception as e:
        print(f"Exception: {e}")
        results.append((name, "❌ ERROR"))

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
for name, result in results:
    print(f"{name:<30} {result}")

passed = sum(1 for _, r in results if "✅" in r)
total = len(results)
print(f"\nResult: {passed}/{total} tests passed")

if passed == total:
    print("\n🎉 ALL TESTS PASSED - PRODUCT LAYER READY")
else:
    print(f"\n❌ {total - passed} test(s) failed - review above")
