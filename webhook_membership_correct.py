#!/usr/bin/env python
"""
Corrected webhook test with proper field names for membership.went_valid
"""

import requests
import hmac
import hashlib
import json
import os
import time
from datetime import datetime
import uuid

RENDER_WEBHOOK_URL = "https://suno-api-production.onrender.com/webhooks/whop"
RENDER_API_URL = "https://suno-api-production.onrender.com"
WHOP_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "")

def send_webhook_test():
    """Send properly formatted membership.went_valid webhook."""

    if not WHOP_SECRET:
        print("ERROR: WHOP_WEBHOOK_SECRET not set")
        return False

    # Generate unique test data
    test_id = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    test_email = f"webhook-test-{timestamp}-{test_id}@example.com"
    event_id = f"evt-{timestamp}-{test_id}"
    whop_membership_id = f"mem-{timestamp}-{test_id}"

    print(f"\n{'='*70}")
    print(f"PHASE 6 MEMBERSHIP VALIDATION TEST")
    print(f"{'='*70}")
    print(f"Test Email:          {test_email}")
    print(f"Event ID:            {event_id}")
    print(f"Whop Membership ID:  {whop_membership_id}")
    print(f"Plan ID:             plan_starter")
    print(f"{'='*70}\n")

    # CORRECT payload format (matching membership_lifecycle.handle_purchase expectations)
    payload = {
        "id": event_id,
        "action": "membership.went_valid",
        "data": {
            "user_email": test_email,  # Not customer_email!
            "whop_membership_id": whop_membership_id,  # Not membership_id!
            "plan_id": "plan_starter",
            "status": "active"
        }
    }

    body = json.dumps(payload).encode('utf-8')
    signature = hmac.new(
        WHOP_SECRET.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    print(f"[STEP 1] Sending membership.went_valid webhook...")
    print(f"{'='*70}")
    print(f"Payload:\n{json.dumps(payload, indent=2)}\n")

    try:
        response = requests.post(
            RENDER_WEBHOOK_URL,
            data=body,
            headers={
                "Whop-Signature": signature,
                "Content-Type": "application/json"
            },
            timeout=10
        )

        print(f"HTTP Status: {response.status_code}")
        print(f"Response:    {response.json() if response.text else 'empty'}")

        if response.status_code != 200:
            print(f"\nERROR: Webhook failed with {response.status_code}")
            return False

        print(f"\nOK: Webhook accepted")

    except Exception as e:
        print(f"\nERROR: Failed to send webhook: {e}")
        return False

    # Step 2: Wait for worker
    print(f"\n{'='*70}")
    print(f"[STEP 2] Waiting for worker to process (max 15 seconds)...")
    print(f"{'='*70}\n")

    for attempt in range(1, 9):
        print(f"[Attempt {attempt}/8] Checking in 2 seconds...")
        time.sleep(2)

        try:
            api_response = requests.get(
                f"{RENDER_API_URL}/api/me/membership",
                headers={"X-User-Email": test_email},
                timeout=10
            )

            if api_response.status_code == 200:
                print(f"\n[STEP 3] Membership Status Verification")
                print(f"{'='*70}")

                membership_data = api_response.json()
                print(f"Response:\n{json.dumps(membership_data, indent=2)}\n")

                # Validate
                status_ok = membership_data.get("status") == "active"
                activated_ok = membership_data.get("activated_at") is not None

                print(f"Validation:")
                print(f"  Status = 'active': {status_ok}")
                print(f"  activated_at NOT null: {activated_ok}")
                print(f"  Tier: {membership_data.get('tier')}")
                print(f"  Membership ID: {membership_data.get('membership_id')}")

                if status_ok and activated_ok:
                    print(f"\n{'='*70}")
                    print(f"SUCCESS: MEMBERSHIP STATUS FIX VERIFIED")
                    print(f"{'='*70}")
                    print(f"\nTest Summary:")
                    print(f"  Email: {test_email}")
                    print(f"  Status: {membership_data.get('status')}")
                    print(f"  Tier: {membership_data.get('tier')}")
                    print(f"  Activated At: {membership_data.get('activated_at')}")
                    return True
                else:
                    print(f"\nERROR: Validation failed")
                    if not status_ok:
                        print(f"  status is '{membership_data.get('status')}', expected 'active'")
                    if not activated_ok:
                        print(f"  activated_at is null, expected non-null")
                    return False

            elif api_response.status_code == 401:
                status_detail = api_response.json().get('detail', 'unknown')
                if "User not found" in status_detail:
                    print(f"  Still waiting... User not created yet")
                else:
                    print(f"  Error: {status_detail}")

        except Exception as e:
            print(f"  Error: {e}")

    print(f"\nERROR: User not created after 16 seconds - worker may have failed")
    return False

if __name__ == "__main__":
    success = send_webhook_test()
    exit(0 if success else 1)
