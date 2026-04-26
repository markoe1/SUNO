#!/usr/bin/env python3
"""
End-to-End Webhook Test for SUNO Production Pipeline

Usage:
    python test_e2e_webhook.py --secret <WHOP_WEBHOOK_SECRET> --api https://suno-api-production.onrender.com

This script:
1. Generates a valid test webhook payload
2. Computes HMAC signature
3. Sends signed webhook to production API
4. Verifies response
"""

import argparse
import json
import hmac
import hashlib
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests library not installed")
    print("Install: pip install requests")
    sys.exit(1)


class WebhookTester:
    def __init__(self, whop_secret: str, api_url: str):
        self.whop_secret = whop_secret
        self.api_url = api_url.rstrip("/")
        self.webhook_id = f"evt_e2e_{int(datetime.now().timestamp() * 1000)}"

    def create_payload(self) -> dict:
        """Create test webhook payload."""
        return {
            "id": self.webhook_id,
            "action": "membership.went_valid",
            "data": {
                "customer_id": "cust_e2e_test",
                "user_id": "usr_e2e_test",
                "email": "e2etest@example.com",
                "plan": {"id": "plan_starter_test"},
                "membership_id": "mem_e2e_test"
            }
        }

    def compute_signature(self, payload: dict) -> str:
        """Compute HMAC-SHA256 signature."""
        body = json.dumps(payload).encode()
        return hmac.new(
            self.whop_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

    def send_webhook(self) -> tuple[int, dict]:
        """Send signed webhook to production API."""
        payload = self.create_payload()
        signature = self.compute_signature(payload)

        headers = {
            "Content-Type": "application/json",
            "Whop-Signature": signature
        }

        print(f"\n{'='*70}")
        print(f"SUNO E2E Webhook Test")
        print(f"{'='*70}\n")

        print(f"📝 Webhook Payload:")
        print(json.dumps(payload, indent=2))

        print(f"\n🔐 HMAC Signature:")
        print(f"   Secret: {self.whop_secret[:20]}...{self.whop_secret[-10:]}")
        print(f"   Signature: {signature[:32]}...{signature[-10:]}")

        print(f"\n🌐 Sending to: {self.api_url}/webhooks/whop")

        try:
            response = requests.post(
                f"{self.api_url}/webhooks/whop",
                json=payload,
                headers=headers,
                timeout=10
            )

            print(f"✓ Response Status: {response.status_code}")
            print(f"✓ Response Body: {response.text}\n")

            return response.status_code, response.json() if response.text else {}

        except requests.exceptions.RequestException as e:
            print(f"✗ Request failed: {e}\n")
            return None, {"error": str(e)}

    def test_health(self) -> bool:
        """Check if webhook service is alive."""
        try:
            response = requests.get(
                f"{self.api_url}/webhooks/whop/status",
                timeout=5
            )
            if response.status_code == 200:
                print(f"✓ Webhook service health: {response.json()}")
                return True
            else:
                print(f"✗ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Health check error: {e}")
            return False

    def run(self) -> bool:
        """Run full e2e test."""
        # Step 1: Health check
        print("\n[1/3] Checking webhook service health...")
        if not self.test_health():
            print("\n✗ Service unreachable. Check:")
            print("  - API URL is correct")
            print("  - Service is running on Render")
            return False

        # Step 2: Send webhook
        print("\n[2/3] Sending signed webhook...")
        status, response = self.send_webhook()

        if status in (200, 202):
            print("✓ Webhook accepted!")
            print(f"\n[3/3] Next Steps:")
            print(f"  1. Check database: SELECT * FROM webhook_events WHERE whop_event_id = '{self.webhook_id}'")
            print(f"  2. Check Redis queue: r.lrange('queue:critical', 0, -1)")
            print(f"  3. Monitor worker logs for: {self.webhook_id}")
            print(f"  4. Verify job completion status in webhook_events")
            return True
        else:
            print(f"✗ Webhook rejected with status {status}")
            if "Invalid signature" in response.get("detail", ""):
                print("\n⚠️  Signature verification failed. Check:")
                print("  - WHOP_WEBHOOK_SECRET is correct (from Whop dashboard)")
                print("  - Secret matches what's set in Render environment")
            elif "Missing event ID" in response.get("detail", ""):
                print("\n⚠️  Payload validation failed. Payload should have:")
                print('  - "id" field with unique event ID')
                print('  - "action" field with event type')
                print('  - "data" dict with event details')
            return False


def main():
    parser = argparse.ArgumentParser(
        description="End-to-end webhook test for SUNO production pipeline"
    )
    parser.add_argument(
        "--secret",
        required=True,
        help="WHOP_WEBHOOK_SECRET from Whop dashboard"
    )
    parser.add_argument(
        "--api",
        default="https://suno-api-production.onrender.com",
        help="Production API URL (default: production Render service)"
    )

    args = parser.parse_args()

    tester = WebhookTester(args.secret, args.api)
    success = tester.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
