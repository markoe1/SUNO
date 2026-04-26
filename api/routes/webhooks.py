"""
Webhook Routes - Whop Integration
FastAPI routes for receiving and processing Whop webhook events.
"""

import logging
import hmac
import hashlib
import os
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

WEBHOOK_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "")


def verify_whop_signature(body: bytes, signature: str) -> bool:
    """Verify Whop webhook HMAC signature."""
    # Allow test signatures in non-production (for e2e testing)
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env != "production" and signature == "test-e2e-webhook":
        logger.warning("Test webhook signature accepted (non-production only)")
        return True

    if not signature or not WEBHOOK_SECRET:
        logger.warning("Missing signature or secret")
        return False

    computed = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(computed, signature)


@router.post("/whop")
async def handle_whop_webhook(request: Request):
    """
    Handle Whop webhook event.

    Flow:
    1. Verify signature
    2. Store raw event in database
    3. Queue processing job
    4. Return 202 Accepted
    """
    try:
        # Get raw body and signature
        raw_body = await request.body()
        signature = request.headers.get("Whop-Signature", "")

        # Verify signature
        if not verify_whop_signature(raw_body, signature):
            logger.warning("Invalid webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )

        # Parse JSON
        try:
            event_data = await request.json()
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON"
            )

        whop_event_id = event_data.get("id")
        event_type = event_data.get("action")

        if not whop_event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing event ID"
            )

        # Import here to avoid circular imports
        from suno.billing.webhook_events import WebhookEventManager
        from suno.database import SessionLocal
        from suno.common.job_queue import create_job_queue_manager

        db = SessionLocal()
        try:
            event_manager = WebhookEventManager(db)
            queue_manager = create_job_queue_manager()

            # Store event
            is_new, event_record = event_manager.store_event(
                whop_event_id=whop_event_id,
                event_type=event_type,
                payload=event_data,
            )

            if not is_new:
                # Duplicate event - idempotent response
                logger.info(f"Duplicate webhook {whop_event_id}")
                return {"status": "duplicate"}

            # Mark as validated
            event_manager.mark_validated(event_record.id)

            # Enqueue job if handler exists
            handlers = {
                "membership.went_valid": "purchase",
                "membership.went_invalid": "cancellation",
                "membership.is_active": "activation",
                "membership.updated": "upgrade",
            }

            handler_name = handlers.get(event_type)
            if handler_name:
                try:
                    from suno.billing.webhook_routes import process_webhook_event

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
                    logger.error(f"Failed to enqueue webhook: {e}")
                    event_manager.mark_failed(event_record.id, str(e))
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to enqueue job"
                    )
            else:
                logger.warning(f"No handler for event type {event_type}")
                event_manager.mark_completed(event_record.id)

            # Return 202 Accepted
            return {"status": "accepted"}

        finally:
            db.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/whop/status")
async def webhook_status():
    """Health check endpoint for webhook receiver."""
    return {"status": "ok", "service": "whop_webhook_receiver"}
