"""
Background webhook event processor.
Framework-neutral module (no Flask/FastAPI imports).
Called by RQ worker to process webhook events.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


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
