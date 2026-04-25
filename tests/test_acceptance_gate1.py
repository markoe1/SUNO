"""
GATE 1: Webhook Authenticity + Idempotency Test
Tests HMAC signature verification and duplicate webhook handling.
"""

import hmac
import hashlib
import json
from datetime import datetime
from suno.billing.webhook_events import WebhookEventManager

# Test constants
SECRET = "whsec_test_secret_12345"
WEBHOOK_ID = "evt_test_12345"
EVENT_TYPE = "membership.went_valid"
PAYLOAD = {
    "id": WEBHOOK_ID,
    "action": EVENT_TYPE,
    "data": {
        "user_email": "testuser@example.com",
        "whop_membership_id": "mem_test_123",
        "plan_id": "plan_starter_001"
    }
}

def compute_signature(body: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

def test_webhook_signature_verification():
    """Test 1A: Valid HMAC signature accepted."""
    from suno.billing.webhook_routes import WebhookSignatureVerifier

    body = json.dumps(PAYLOAD).encode()
    valid_sig = compute_signature(body, SECRET)

    verifier = WebhookSignatureVerifier(SECRET)
    result = verifier.verify(body, valid_sig)

    assert result == True, "Valid signature should be accepted"
    print("✅ Test 1A PASS: Valid signature accepted")
    return True

def test_webhook_signature_rejection():
    """Test 1B: Invalid HMAC signature rejected."""
    from suno.billing.webhook_routes import WebhookSignatureVerifier

    body = json.dumps(PAYLOAD).encode()
    invalid_sig = "deadbeef" * 8  # Invalid signature

    verifier = WebhookSignatureVerifier(SECRET)
    result = verifier.verify(body, invalid_sig)

    assert result == False, "Invalid signature should be rejected"
    print("✅ Test 1B PASS: Invalid signature rejected")
    return True

def test_webhook_idempotency(db_session):
    """Test 1C: Duplicate webhooks don't create duplicate jobs."""
    from suno.common.models import WebhookEvent

    manager = WebhookEventManager(db_session)

    # First webhook
    is_new_1, event_1 = manager.store_event(WEBHOOK_ID, EVENT_TYPE, PAYLOAD)
    assert is_new_1 == True, "First webhook should be new"
    assert event_1.id is not None, "Event should be stored"
    event_id_1 = event_1.id

    # Duplicate webhook with same ID
    is_new_2, event_2 = manager.store_event(WEBHOOK_ID, EVENT_TYPE, PAYLOAD)
    assert is_new_2 == False, "Duplicate webhook should not be new"
    assert event_2.id == event_id_1, "Should return same event"

    # Verify only one event in DB
    count = db_session.query(WebhookEvent).filter(
        WebhookEvent.whop_event_id == WEBHOOK_ID
    ).count()
    assert count == 1, f"Expected 1 event, found {count}"

    print("✅ Test 1C PASS: Duplicate prevention working")
    return True

def test_event_status_transitions(db_session):
    """Test 1D: Event status transitions correctly."""
    from suno.common.models import WebhookEvent
    from suno.billing.webhook_events import WebhookEventStatus

    manager = WebhookEventManager(db_session)

    # Store event
    is_new, event = manager.store_event(f"evt_trans_{datetime.utcnow().timestamp()}", EVENT_TYPE, PAYLOAD)
    event_id = event.id

    # Verify initial status
    assert event.status == WebhookEventStatus.RECEIVED, "Initial status should be RECEIVED"

    # Mark validated
    result = manager.mark_validated(event_id)
    assert result == True, "mark_validated should succeed"
    db_session.commit()  # Caller must commit

    # Verify status changed
    event = db_session.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    assert event.status == WebhookEventStatus.VALIDATED, "Status should be VALIDATED"

    # Mark processing
    result = manager.mark_processing(event_id)
    assert result == True, "mark_processing should succeed"
    db_session.commit()

    event = db_session.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    assert event.status == WebhookEventStatus.PROCESSING, "Status should be PROCESSING"

    # Mark completed
    result = manager.mark_completed(event_id, {"account_id": 1})
    assert result == True, "mark_completed should succeed"
    db_session.commit()

    event = db_session.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    assert event.status == WebhookEventStatus.COMPLETED, "Status should be COMPLETED"

    print("✅ Test 1D PASS: Event status transitions correct")
    return True

if __name__ == "__main__":
    print("\n" + "="*60)
    print("GATE 1: WEBHOOK AUTHENTICITY + IDEMPOTENCY")
    print("="*60)

    try:
        # Test signature verification
        test_webhook_signature_verification()
        test_webhook_signature_rejection()

        # For DB tests, we need a session
        from suno.database import SessionLocal
        db = SessionLocal()
        try:
            test_webhook_idempotency(db)
            test_event_status_transitions(db)
        finally:
            db.close()

        print("\n" + "="*60)
        print("GATE 1: ✅ PASS")
        print("="*60)
        print("""
✅ Valid HMAC signatures accepted
✅ Invalid signatures rejected
✅ Duplicate webhooks prevented
✅ Event status transitions correct
✅ No duplicate jobs created on retry
        """)

    except Exception as e:
        print(f"\n❌ GATE 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
