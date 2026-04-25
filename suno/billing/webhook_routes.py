"""
Webhook Routes and Handler
Flask routes for receiving and processing Whop webhook events.
Implements proper queueing and event lifecycle tracking.
"""

import logging
import hmac
import hashlib
import os
from typing import Dict, Any, Tuple
from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

webhook_bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")


class WebhookSignatureVerifier:
    """Verifies Whop webhook HMAC signatures."""

    def __init__(self, secret: str):
        """
        Initialize verifier.

        Args:
            secret: Webhook secret from Whop dashboard
        """
        self.secret = secret

    def verify(self, body: bytes, signature: str) -> bool:
        """
        Verify webhook signature using HMAC-SHA256.

        Args:
            body: Raw request body
            signature: Signature header value

        Returns:
            True if signature is valid
        """
        if not signature:
            logger.warning("Missing webhook signature")
            return False

        computed = hmac.new(
            self.secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(computed, signature)


def create_webhook_handler(db: Session, queue_manager, signature_secret: str):
    """
    Factory to create webhook handler function.

    Args:
        db: SQLAlchemy session
        queue_manager: JobQueueManager instance
        signature_secret: Webhook signature secret

    Returns:
        Webhook handler function
    """
    from suno.billing.webhook_events import WebhookEventManager
    from suno.billing.membership_lifecycle import MembershipLifecycleHandler

    verifier = WebhookSignatureVerifier(signature_secret)
    event_manager = WebhookEventManager(db)
    lifecycle_handler = MembershipLifecycleHandler(db, queue_manager)

    @webhook_bp.post("/whop")
    def handle_whop_webhook():
        """
        Handle Whop webhook event.

        Flow:
        1. Verify signature
        2. Store raw event
        3. Validate and enqueue
        4. Return 202 Accepted immediately
        5. Process async
        """
        raw_body = request.get_data()
        signature = request.headers.get("Whop-Signature", "")

        # 1. Verify signature
        if not verifier.verify(raw_body, signature):
            logger.warning("Invalid webhook signature, rejecting")
            return jsonify({"error": "Invalid signature"}), 401

        # 2. Parse event
        event_data = request.get_json(force=True)
        whop_event_id = event_data.get("id")
        event_type = event_data.get("action")

        if not whop_event_id:
            logger.warning("Missing event ID in webhook")
            return jsonify({"error": "Missing event ID"}), 400

        # 3. Store raw event
        is_new, event_record = event_manager.store_event(
            whop_event_id=whop_event_id,
            event_type=event_type,
            payload=event_data,
        )

        if not is_new:
            # Duplicate event - return success (idempotency)
            logger.info(f"Duplicate webhook {whop_event_id}, returning 202")
            return jsonify({"status": "duplicate"}), 202

        # 4. Validate signature on stored event
        event_manager.mark_validated(event_record.id)

        # 5. Determine handler and enqueue job
        handler_name = _get_handler_for_event(event_type)
        if handler_name:
            try:
                job_id = queue_manager.enqueue(
                    "critical",
                    process_webhook_event,
                    kwargs={
                        "event_id": event_record.id,
                        "event_type": event_type,
                        "event_data": event_data,
                    },
                )
                event_manager.mark_enqueued(event_record.id, job_id)
                logger.info(f"Enqueued webhook {whop_event_id} as job {job_id}")
            except Exception as e:
                logger.error(f"Failed to enqueue webhook {whop_event_id}: {e}")
                event_manager.mark_failed(event_record.id, str(e))
                return jsonify({"error": "Failed to enqueue"}), 500
        else:
            logger.warning(f"No handler for event type {event_type}")
            event_manager.mark_completed(event_record.id)

        # 6. Return 202 immediately (Whop times out after 30s)
        return jsonify({"status": "accepted"}), 202

    @webhook_bp.get("/whop/status")
    def webhook_status():
        """Health check endpoint for webhook receiver."""
        return jsonify({
            "status": "ok",
            "service": "whop_webhook_receiver",
        }), 200

    return webhook_bp, event_manager, lifecycle_handler


def _get_handler_for_event(event_type: str) -> str:
    """Get handler function name for event type."""
    handlers = {
        "membership.went_valid": "handle_purchase",
        "membership.went_invalid": "handle_cancellation",
        "membership.is_active": "handle_activation",
        "membership.updated": "handle_upgrade",
    }
    return handlers.get(event_type)


# Background job function (called by RQ worker)


def process_webhook_event(event_id: int, event_type: str, event_data: Dict[str, Any]):
    """
    Process webhook event in background.

    Args:
        event_id: Database event record ID
        event_type: Type of event
        event_data: Full event payload
    """
    from suno.database import SessionLocal
    from suno.billing.webhook_events import WebhookEventManager
    from suno.billing.membership_lifecycle import MembershipLifecycleHandler
    from suno.common.job_queue import create_job_queue_manager

    db = SessionLocal()
    try:
        event_manager = WebhookEventManager(db)
        queue_manager = create_job_queue_manager()
        lifecycle_handler = MembershipLifecycleHandler(db, queue_manager)

        # Mark as processing
        event_manager.mark_processing(event_id)

        # Route to handler
        result = None
        if event_type == "membership.went_valid":
            result = lifecycle_handler.handle_purchase(event_data.get("data", {}))
        elif event_type == "membership.went_invalid":
            result = lifecycle_handler.handle_cancellation(event_data.get("data", {}))
        elif event_type == "membership.is_active":
            result = lifecycle_handler.handle_activation(event_data.get("data", {}))
        elif event_type == "membership.updated":
            result = lifecycle_handler.handle_upgrade(event_data.get("data", {}))
        else:
            logger.warning(f"Unknown event type: {event_type}")
            event_manager.mark_completed(event_id)
            return

        # Mark as completed
        if result and result.get("success"):
            event_manager.mark_completed(event_id, result)
            logger.info(f"Event {event_id} processed successfully")
        else:
            error_msg = result.get("error", "Unknown error") if result else "No result"
            event_manager.mark_failed(event_id, error_msg)
            logger.error(f"Event {event_id} processing failed: {error_msg}")

    except Exception as e:
        logger.error(f"Unexpected error processing event {event_id}: {e}")
        try:
            event_manager.mark_failed(event_id, str(e))
        except:
            pass
    finally:
        db.close()
