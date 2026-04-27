#!/usr/bin/env python3
"""
Webhook Secret Diagnostic Tool
Helps identify what WHOP_WEBHOOK_SECRET is currently configured in environment
"""

import os
import hmac
import hashlib

# Get the secret from environment
WEBHOOK_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "")

if not WEBHOOK_SECRET:
    print("❌ WHOP_WEBHOOK_SECRET is NOT set in environment")
    exit(1)

# Compute fingerprint (last 12 chars of SHA256)
secret_fingerprint = hashlib.sha256(WEBHOOK_SECRET.encode()).hexdigest()[:12]
secret_length = len(WEBHOOK_SECRET)

print("=" * 60)
print("WEBHOOK SECRET DIAGNOSTIC")
print("=" * 60)
print(f"✓ Secret is configured")
print(f"  Length: {secret_length} characters")
print(f"  Fingerprint: {secret_fingerprint}")
print()
print("Use this fingerprint to match against webhook logs.")
print("=" * 60)

# Test HMAC computation with example body
test_body = b"test webhook body"
test_hmac = hmac.new(
    WEBHOOK_SECRET.encode(),
    test_body,
    hashlib.sha256
).hexdigest()

print(f"\nTest HMAC (with body '{test_body.decode()}'):")
print(f"  {test_hmac}")
print()
print("Next steps:")
print("1. Run this on Render: 'python debug_webhook_secret.py'")
print("2. Check the fingerprint against your successful webhook logs")
print("3. Update local .env if different")
