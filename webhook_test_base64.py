#!/usr/bin/env python
"""Test webhook with base64-encoded signature."""

import requests
import hmac
import hashlib
import json
import os
import base64
from datetime import datetime
import uuid

RENDER_WEBHOOK_URL = "https://suno-api-production.onrender.com/webhooks/whop"
WHOP_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "")

def test_webhook_base64():
    """Test with base64-encoded signature."""

    if not WHOP_SECRET:
        print("ERROR: WHOP_WEBHOOK_SECRET not set")
        return False

    test_id = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    event_id = f"evt-{timestamp}-{test_id}"

    payload = {
        "id": event_id,
        "action": "membership.went_valid",
        "data": {
            "customer_id": f"cust-{test_id}",
            "membership_id": f"mem-{test_id}",
            "status": "active"
        }
    }

    body = json.dumps(payload).encode('utf-8')

    # Try base64-encoded signature
    sig_hex = hmac.new(
        WHOP_SECRET.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    sig_b64 = base64.b64encode(bytes.fromhex(sig_hex)).decode('utf-8')

    print(f"Event ID: {event_id}")
    print(f"Signature (hex): {sig_hex[:16]}...")
    print(f"Signature (b64): {sig_b64[:20]}...")
    print(f"\nSending webhook with base64-encoded signature...\n")

    try:
        response = requests.post(
            RENDER_WEBHOOK_URL,
            data=body,
            headers={
                "Whop-Signature": sig_b64,
                "Content-Type": "application/json"
            },
            timeout=10
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {response.json() if response.text else 'empty'}")
        return response.status_code == 200 or response.status_code == 202

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_webhook_base64()
