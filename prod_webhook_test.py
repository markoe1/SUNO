#!/usr/bin/env python
"""Production webhook test - sends a test event to Render SUNO webhook handler."""

import requests
import hmac
import hashlib
import json
import os
from datetime import datetime

# Configuration
RENDER_WEBHOOK_URL = "https://suno-api-production.onrender.com/webhooks/whop"
WHOP_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "test-secret-key")

def send_webhook_test(event_action="membership.went_valid"):
    """Send a test webhook event."""

    # Generate unique event ID with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")[:20]
    event_id = f"prod-test-{timestamp}"

    # Build payload
    payload = {
        "id": event_id,
        "action": event_action,
        "data": {
            "customer_id": f"cust-{event_id}",
            "membership_id": f"mem-{event_id}",
            "status": "active"
        }
    }

    # Convert to JSON bytes
    body = json.dumps(payload).encode('utf-8')

    # Compute HMAC-SHA256 signature
    signature = hmac.new(
        WHOP_SECRET.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    # Send request
    print(f"\n{'='*70}")
    print(f"SENDING WEBHOOK TEST")
    print(f"{'='*70}")
    print(f"Event ID:    {event_id}")
    print(f"Action:      {event_action}")
    print(f"URL:         {RENDER_WEBHOOK_URL}")
    print(f"Signature:   {signature[:16]}...")
    print(f"Payload:     {json.dumps(payload, indent=2)}")
    print(f"{'='*70}\n")

    try:
        response = requests.post(
            RENDER_WEBHOOK_URL,
            data=body,  # Use raw bytes, not json=payload (which re-encodes)
            headers={
                "Whop-Signature": signature,
                "Content-Type": "application/json"
            },
            timeout=10
        )

        print(f"HTTP Status: {response.status_code}")
        print(f"Response:    {response.json() if response.text else 'empty'}\n")

        if response.status_code == 200:
            print(f"✅ Webhook sent successfully!")
            print(f"\n📋 NEXT STEPS:")
            print(f"1. Check Render SUNO-WORKER logs for event {event_id}")
            print(f"2. Look for these markers:")
            print(f"   [JOB_START] Processing webhook event...")
            print(f"   [JOB_SUCCESS] Event {event_id} processed successfully")
            print(f"3. If no markers appear within 30s, worker may have crashed")
            print(f"\nEvent ID to track: {event_id}")
            return True
        else:
            print(f"❌ Webhook failed with status {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error sending webhook: {e}")
        return False

if __name__ == "__main__":
    send_webhook_test()
