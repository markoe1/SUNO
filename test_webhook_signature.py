#!/usr/bin/env python3
"""
Test webhook signature verification with CORRECT lowercase secret
"""

import hmac
import hashlib
import json

# CORRECT: lowercase 's' - matches Render server
WEBHOOK_SECRET_CORRECT = "ws_9100a54d91874bf240b1b20438f23683d66306dab0e25d5f7eb7c13cbbed5b12"

# WRONG: uppercase 'S' - what was being used before
WEBHOOK_SECRET_WRONG = "wS_9100a54d91874bf240b1b20438f23683d66306dab0e25d5f7eb7c13cbbed5b12"

# Example webhook body (226 bytes based on your logs)
test_body = json.dumps({
    "id": "evt-test-20260427",
    "action": "membership.went_valid",
    "data": {"account_id": 123}
}).encode()

def compute_signature(secret: str, body: bytes) -> str:
    """Compute HMAC-SHA256 signature."""
    return hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

def get_fingerprint(secret: str) -> str:
    """Get diagnostic fingerprint."""
    return hashlib.sha256(secret.encode()).hexdigest()[:12]

print("=" * 70)
print("WEBHOOK SIGNATURE TEST")
print("=" * 70)
print()

# Test with CORRECT secret
print("[OK] CORRECT (lowercase 's'):")
correct_sig = compute_signature(WEBHOOK_SECRET_CORRECT, test_body)
correct_fp = get_fingerprint(WEBHOOK_SECRET_CORRECT)
print(f"  Secret fingerprint: {correct_fp}")
print(f"  Signature: {correct_sig[:32]}...")
print()

# Test with WRONG secret
print("[NO] WRONG (uppercase 'S'):")
wrong_sig = compute_signature(WEBHOOK_SECRET_WRONG, test_body)
wrong_fp = get_fingerprint(WEBHOOK_SECRET_WRONG)
print(f"  Secret fingerprint: {wrong_fp}")
print(f"  Signature: {wrong_sig[:32]}...")
print()

# Compare
print("=" * 70)
print("COMPARISON")
print("=" * 70)
print(f"Fingerprints match expected Render (20f2e1d00e7d)?")
if correct_fp == "20f2e1d00e7d":
    print(f"  Correct (ws_...): {correct_fp} [MATCH]")
else:
    print(f"  Correct (ws_...): {correct_fp} [NO]")
if wrong_fp == "20f2e1d00e7d":
    print(f"  Wrong (wS_...):   {wrong_fp} [MATCH]")
else:
    print(f"  Wrong (wS_...):   {wrong_fp} [NO]")
print()

# Test actual comparison
print("Signature comparison:")
print(f"  Correct == Wrong? {correct_sig == wrong_sig} (should be False)")
print()

print("=" * 70)
print("NEXT STEP")
print("=" * 70)
print()
print("1. Use the CORRECT lowercase secret: ws_9100...")
print("2. Update your client test script with lowercase secret")
print("3. Resend webhook - should get 200 OK")
print("4. Only THEN update Render if needed")
print()
