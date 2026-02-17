import os
from flask import Flask, jsonify, request, redirect
import stripe
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
PRICE_ID = os.getenv("STRIPE_PRICE_ID_SUNO", "")
SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:5001/success")
CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "http://localhost:5001/cancel")

@app.get("/")
def root():
    return "SUNO Billing Server OK", 200

@app.get("/checkout")
def create_checkout():
    price = request.args.get("price_id", PRICE_ID)
    if not stripe.api_key or not price:
        return jsonify({"error": "Missing STRIPE_SECRET_KEY or price_id"}), 400
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": price, "quantity": 1}],
            success_url=SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=CANCEL_URL,
            payment_method_types=["card"],
            automatic_tax={"enabled": True},
        )
        return redirect(session.url, code=303)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.get("/success")
def success():
    return "Payment successful. You can close this tab.", 200

@app.get("/cancel")
def cancel():
    return "Payment canceled. You can close this tab.", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)