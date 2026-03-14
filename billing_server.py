"""
Whop Billing Server (stub)
==========================
SUNO Clips uses Whop as the merchant of record for operator subscriptions.

Env vars (set when implementing):
  WHOP_API_KEY            — Whop API key from dashboard.whop.com
  WHOP_WEBHOOK_SECRET     — Webhook secret for signature verification
  WHOP_PRODUCT_ID         — Product ID (prod_xxx) for operator subscriptions
  SUCCESS_URL             — Redirect after successful checkout
  CANCEL_URL              — Redirect if user cancels

Whop checkout flow:
  1. Redirect user to https://whop.com/checkout/<product_id>/?d2c=true
  2. Whop handles payment + subscription lifecycle
  3. Whop sends webhook events to /webhook
  4. On membership.went_valid  — activate operator account
  5. On membership.went_invalid — deactivate / restrict access

Whop webhook docs: https://dev.whop.com/api-reference/webhooks
"""

import hashlib
import hmac
import json
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request

load_dotenv()

app = Flask(__name__)

WHOP_API_KEY = os.getenv("WHOP_API_KEY", "")
WHOP_WEBHOOK_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "")
WHOP_PRODUCT_ID = os.getenv("WHOP_PRODUCT_ID", "")
SUCCESS_URL = os.getenv("SUCCESS_URL", "http://localhost:8000/dashboard")
CANCEL_URL = os.getenv("CANCEL_URL", "http://localhost:8000/")


@app.get("/")
def root():
    return "SUNO Clips — Whop Billing (stub — not yet active)", 200


@app.get("/checkout")
def create_checkout():
    """Redirect user to Whop checkout for operator subscription."""
    if not WHOP_PRODUCT_ID:
        return jsonify({"error": "WHOP_PRODUCT_ID not configured"}), 400

    customer_email = request.args.get("email", "")
    checkout_url = f"https://whop.com/checkout/{WHOP_PRODUCT_ID}/?d2c=true"
    if customer_email:
        checkout_url += f"&email={customer_email}"

    return redirect(checkout_url, code=303)


@app.post("/webhook")
def whop_webhook():
    """Verify and handle Whop webhook events."""
    if not WHOP_WEBHOOK_SECRET:
        return jsonify({"error": "Webhook secret not configured"}), 500

    raw_body = request.get_data()
    signature = request.headers.get("Whop-Signature", "")

    if not _verify_whop_signature(raw_body, signature):
        return jsonify({"error": "Invalid signature"}), 401

    event = request.get_json(force=True)
    event_type = event.get("action", "")

    if event_type == "membership.went_valid":
        # User paid — activate their operator account
        data = event.get("data", {})
        membership_id = data.get("id")
        user_email = data.get("user", {}).get("email")
        # TODO: look up user by email, set tier = "operator", store membership_id as whop_transaction_id
        app.logger.info(f"Membership activated: {membership_id} for {user_email}")

    elif event_type == "membership.went_invalid":
        # Subscription lapsed — restrict access
        data = event.get("data", {})
        membership_id = data.get("id")
        # TODO: look up user by membership_id, downgrade tier
        app.logger.info(f"Membership deactivated: {membership_id}")

    elif event_type == "payment.succeeded":
        data = event.get("data", {})
        app.logger.info(f"Payment succeeded: {data.get('id')}")

    return jsonify({"ok": True}), 200


def _verify_whop_signature(raw_body: bytes, signature: str) -> bool:
    """
    Verify Whop webhook HMAC-SHA256 signature.
    Whop sends: Whop-Signature: <hex_digest>
    """
    if not WHOP_WEBHOOK_SECRET or not signature:
        return False
    try:
        expected = hmac.new(
            WHOP_WEBHOOK_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


@app.get("/success")
def success():
    return redirect(SUCCESS_URL, code=303)


@app.get("/cancel")
def cancel():
    return redirect(CANCEL_URL, code=303)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
