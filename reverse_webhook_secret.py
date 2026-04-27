#!/usr/bin/env python3
"""
Reverse-engineer the correct WHOP_WEBHOOK_SECRET from a successful webhook.

Usage:
  If you have a webhook that returned 200 OK with body_sha256 and received_sig,
  this script can test candidate secrets to find which one validates.

Example from logs:
  [WEBHOOK_DIAG] body_sha256=abc123def456...
  [WEBHOOK_DIAG] received_sig=789xyz...
  [WEBHOOK_DIAG] secret_fingerprint=20f2e1d00e7d

Then test secrets like:
  python reverse_webhook_secret.py "secret_candidate_1" "received_sig_value" "raw_body_bytes"
"""

import hmac
import hashlib
import sys
import json
from typing import Optional

def verify_secret(secret: str, body: bytes, signature: str) -> bool:
    """Test if a secret produces the given signature for the body."""
    computed = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)

def get_secret_fingerprint(secret: str) -> str:
    """Get the diagnostic fingerprint (first 12 chars of SHA256)."""
    return hashlib.sha256(secret.encode()).hexdigest()[:12]

def main():
    print("=" * 70)
    print("WEBHOOK SECRET REVERSE-ENGINEERING TOOL")
    print("=" * 70)
    print()
    print("This script helps identify the correct WHOP_WEBHOOK_SECRET")
    print()
    print("STEP 1: Find a successful webhook in your logs (one that returned 200)")
    print("  Look for lines like:")
    print("    [WEBHOOK_DIAG] body_sha256=...")
    print("    [WEBHOOK_DIAG] received_sig=...")
    print("    [WEBHOOK_DIAG] secret_fingerprint=...")
    print()
    print("STEP 2: Extract from the log:")
    print("  - The raw webhook body (from request body)")
    print("  - The received signature from the header")
    print()
    print("STEP 3: Test candidate secrets:")
    print("  python reverse_webhook_secret.py")
    print("    --secret 'candidate-secret-string'")
    print("    --body '{json body}'")
    print("    --sig 'signature-from-header'")
    print()
    print("=" * 70)
    print()
    print("QUICK DIAGNOSIS:")
    print()
    print("If webhook validation is failing with fingerprint mismatch:")
    print("  1. Run: python debug_webhook_secret.py (on Render)")
    print("  2. Compare fingerprint to successful webhook logs")
    print("  3. Update .env WHOP_WEBHOOK_SECRET if different")
    print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        main()
    else:
        # Simple test mode
        if "--secret" in sys.argv:
            secret_idx = sys.argv.index("--secret")
            secret = sys.argv[secret_idx + 1]
            fp = get_secret_fingerprint(secret)
            print(f"Secret: {secret}")
            print(f"Fingerprint: {fp}")
