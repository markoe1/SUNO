"""
Paddle Billing Server
=====================
Handles Paddle checkout link generation and webhook events.
Paddle is the merchant of record — no Stripe dependency.

Env vars required:
  PADDLE_API_KEY          — Paddle API key (sandbox or live)
  PADDLE_WEBHOOK_SECRET   — Webhook secret from Paddle dashboard
  PADDLE_PRICE_ID         — Default price ID (pri_xxx)
  SUCCESS_URL             — Redirect after successful checkout
  CANCEL_URL              — Redirect if user cancels
"""

import hashlib
import hmac
import json
import os

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request

load_dotenv()

app = Flask(__name__)

PADDLE_API_KEY = os.getenv("PADDLE_API_KEY", "")
PADDLE_WEBHOOK_SECRET = os.getenv("PADDLE_WEBHOOK_SECRET", "")
PADDLE_PRICE_ID = os.getenv("PADDLE_PRICE_ID", "")
SUCCESS_URL = os.getenv("SUCCESS_URL", "http://localhost:5001/success")
CANCEL_URL = os.getenv("CANCEL_URL", "http://localhost:5001/cancel")

# Use sandbox endpoint unless PADDLE_ENV=production
PADDLE_BASE = (
    "https://api.paddle.com"
    if os.getenv("PADDLE_ENV") == "production"
    else "https://sandbox-api.paddle.com"
)


def _paddle_headers():
    return {
        "Authorization": f"Bearer {PADDLE_API_KEY}",
        "Content-Type": "application/json",
    }


@app.get("/")
def root():
    return "SUNO Clips — Paddle Billing OK", 200


@app.get("/checkout")
def create_checkout():
    """Generate a Paddle checkout URL and redirect the user to it."""
    price_id = request.args.get("price_id", PADDLE_PRICE_ID)
    customer_email = request.args.get("email", "")

    if not PADDLE_API_KEY or not price_id:
        return jsonify({"error": "PADDLE_API_KEY or price_id not configured"}), 400

    payload = {
        "items": [{"price_id": price_id, "quantity": 1}],
        "checkout": {"url": SUCCESS_URL},
    }
    if customer_email:
        payload["customer"] = {"email": customer_email}

    try:
        resp = requests.post(
            f"{PADDLE_BASE}/transactions",
            headers=_paddle_headers(),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        checkout_url = data["data"]["checkout"]["url"]
        return redirect(checkout_url, code=303)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post("/webhook")
def paddle_webhook():
    """Verify and handle Paddle webhook events."""
    if not PADDLE_WEBHOOK_SECRET:
        return jsonify({"error": "Webhook secret not configured"}), 500

    # Verify Paddle-Signature header
    signature_header = request.headers.get("Paddle-Signature", "")
    raw_body = request.get_data()

    if not _verify_paddle_signature(raw_body, signature_header):
        return jsonify({"error": "Invalid signature"}), 401

    event = request.get_json(force=True)
    event_type = event.get("event_type", "")

    if event_type == "transaction.completed":
        txn = event.get("data", {})
        txn_id = txn.get("id")
        customer_id = txn.get("customer_id")
        # TODO: activate subscription for customer, store txn_id as paddle_transaction_id
        app.logger.info(f"Payment completed: txn={txn_id} customer={customer_id}")

    elif event_type == "subscription.activated":
        sub = event.get("data", {})
        app.logger.info(f"Subscription activated: {sub.get('id')}")

    elif event_type == "subscription.canceled":
        sub = event.get("data", {})
        app.logger.info(f"Subscription canceled: {sub.get('id')}")

    return jsonify({"ok": True}), 200


def _verify_paddle_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Verify Paddle webhook signature.
    Header format: ts=1234567890;h1=abc123...
    """
    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(";"))
        ts = parts.get("ts", "")
        h1 = parts.get("h1", "")
        signed_payload = f"{ts}:{raw_body.decode('utf-8')}"
        expected = hmac.new(
            PADDLE_WEBHOOK_SECRET.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, h1)
    except Exception:
        return False


@app.get("/success")
def success():
    return "Payment successful. You can close this tab.", 200


@app.get("/cancel")
def cancel():
    return "Payment canceled. You can close this tab.", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
