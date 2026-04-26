#!/usr/bin/env python
"""
Production webhook validation test for membership.went_valid
Verifies membership status activation and account provisioning.
"""

import requests
import hmac
import hashlib
import json
import os
import time
from datetime import datetime
import uuid

# Configuration
RENDER_WEBHOOK_URL = "https://suno-api-production.onrender.com/webhooks/whop"
RENDER_API_URL = "https://suno-api-production.onrender.com"
WHOP_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "test-secret-key")

def send_membership_webhook_test():
    """Send membership.went_valid webhook and verify status activation."""

    # Generate unique test data
    test_id = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    test_email = f"webhook-test-{timestamp}-{test_id}@example.com"
    event_id = f"evt-{timestamp}-{test_id}"
    membership_id = f"mem-{timestamp}-{test_id}"
    customer_id = f"cust-{timestamp}-{test_id}"

    print(f"\n{'='*70}")
    print(f"PHASE 6 MEMBERSHIP VALIDATION TEST")
    print(f"{'='*70}")
    print(f"Test Email:     {test_email}")
    print(f"Event ID:       {event_id}")
    print(f"Membership ID:  {membership_id}")
    print(f"Customer ID:    {customer_id}")
    print(f"{'='*70}\n")

    # Step 1: Send webhook event
    print("[STEP 1] Sending membership.went_valid webhook...")
    print(f"{'='*70}")

    payload = {
        "id": event_id,
        "action": "membership.went_valid",
        "data": {
            "customer_id": customer_id,
            "customer_email": test_email,
            "membership_id": membership_id,
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

        print(f"\nOK: Webhook accepted by server")

    except Exception as e:
        print(f"\nERROR: Failed to send webhook: {e}")
        return False

    # Step 2: Wait for worker processing
    print(f"\n{'='*70}")
    print(f"[STEP 2] Waiting for worker processing (3 seconds)...")
    print(f"{'='*70}\n")
    time.sleep(3)

    # Step 3: Check membership via API
    print(f"[STEP 3] Verifying membership status via API...")
    print(f"{'='*70}")
    print(f"GET /api/me/membership")
    print(f"Header: X-User-Email: {test_email}\n")

    try:
        api_response = requests.get(
            f"{RENDER_API_URL}/api/me/membership",
            headers={
                "X-User-Email": test_email,
                "Content-Type": "application/json"
            },
            timeout=10
        )

        print(f"HTTP Status: {api_response.status_code}\n")

        if api_response.status_code == 200:
            membership_data = api_response.json()
            print(f"Response:\n{json.dumps(membership_data, indent=2)}\n")

            # Validate response fields
            status_ok = membership_data.get("status") == "active"
            activated_ok = membership_data.get("activated_at") is not None

            print(f"{'='*70}")
            print(f"VALIDATION RESULTS:")
            print(f"{'='*70}")
            print(f"✓ Status is 'active': {status_ok}")
            print(f"✓ activated_at is NOT null: {activated_ok}")
            print(f"  Tier: {membership_data.get('tier')}")
            print(f"  Membership ID: {membership_data.get('membership_id')}")
            print(f"  Activated At: {membership_data.get('activated_at')}")

            if status_ok and activated_ok:
                print(f"\n✅ MEMBERSHIP STATUS FIX VERIFIED")
                print(f"\nTest Summary:")
                print(f"  - Email: {test_email}")
                print(f"  - Status: {membership_data.get('status')}")
                print(f"  - Tier: {membership_data.get('tier')}")
                return True
            else:
                print(f"\n❌ MEMBERSHIP VALIDATION FAILED")
                if not status_ok:
                    print(f"  ERROR: status is '{membership_data.get('status')}', expected 'active'")
                if not activated_ok:
                    print(f"  ERROR: activated_at is null, expected non-null value")
                return False

        elif api_response.status_code == 401:
            print(f"ERROR 401: User not found or not authenticated")
            print(f"Response: {api_response.json()}")
            return False
        elif api_response.status_code == 403:
            print(f"ERROR 403: User has no active membership")
            print(f"Response: {api_response.json()}")
            return False
        else:
            print(f"ERROR {api_response.status_code}: {api_response.text}")
            return False

    except Exception as e:
        print(f"ERROR: Failed to call membership API: {e}")
        return False

if __name__ == "__main__":
    success = send_membership_webhook_test()
    exit(0 if success else 1)
