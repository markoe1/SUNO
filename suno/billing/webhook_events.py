"""
Webhook Event Lifecycle Management
Tracks webhook events from receipt through processing with full audit trail.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class WebhookEventStatus(str, Enum):
    """Webhook event processing status."""
    RECEIVED = "received"          # Event received and stored
    VALIDATED = "validated"        # Signature validated
    ENQUEUED = "enqueued"          # Job enqueued for processing
    PROCESSING = "processing"      # Currently being processed
    COMPLETED = "completed"        # Successfully processed
    FAILED = "failed"              # Processing failed
    DEAD_LETTER = "dead_letter"    # Permanently failed, needs operator intervention


class WebhookEventManager:
    """Manages webhook event lifecycle with full audit trail."""

    def __init__(self, db: Session):
        """
        Initialize webhook event manager.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def store_event(
        self,
        whop_event_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> tuple[bool, Any]:
        """
        Store received webhook event.

        Args:
            whop_event_id: Unique event ID from Whop
            event_type: Event type (membership.went_valid, etc)
            payload: Full event payload

        Returns:
            (is_new, event_record): Tuple of success and event record
        """
        from suno.common.models import WebhookEvent

        try:
            # Check if already stored
            existing = self.db.query(WebhookEvent).filter(
                WebhookEvent.whop_event_id == whop_event_id
            ).first()

            if existing:
                logger.info(f"Webhook event {whop_event_id} already stored")
                return False, existing

            # Create new event record
            event = WebhookEvent(
                whop_event_id=whop_event_id,
                event_type=event_type,
                payload=payload,
                status=WebhookEventStatus.RECEIVED,
                received_at=datetime.utcnow(),
            )
            self.db.add(event)
            self.db.commit()

            logger.info(f"Stored webhook event {whop_event_id} ({event_type})")
            return True, event

        except IntegrityError:
            self.db.rollback()
            # Race condition: event stored by another process
            existing = self.db.query(WebhookEvent).filter(
                WebhookEvent.whop_event_id == whop_event_id
            ).first()
            logger.info(f"Webhook event {whop_event_id} was stored by concurrent process")
            return False, existing
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to store webhook event: {e}")
            raise

    def mark_validated(self, event_id: int) -> bool:
        """
        Mark event as signature-validated.

        Args:
            event_id: Database event ID

        Returns:
            Success boolean
        """
        from suno.common.models import WebhookEvent

        try:
            event = self.db.query(WebhookEvent).filter(
                WebhookEvent.id == event_id
            ).first()

            if not event:
                logger.warning(f"Event {event_id} not found")
                return False

            event.status = WebhookEventStatus.VALIDATED
            event.validated_at = datetime.utcnow()
            # Don't commit - let caller control transaction

            logger.info(f"Marked event {event_id} as validated")
            return True

        except Exception as e:
            logger.error(f"Failed to mark event as validated: {e}")
            return False

    def mark_enqueued(self, event_id: int, job_id: str) -> bool:
        """
        Mark event as enqueued with job reference.

        Args:
            event_id: Database event ID
            job_id: RQ job ID

        Returns:
            Success boolean
        """
        from suno.common.models import WebhookEvent

        try:
            event = self.db.query(WebhookEvent).filter(
                WebhookEvent.id == event_id
            ).first()

            if not event:
                logger.warning(f"Event {event_id} not found")
                return False

            event.status = WebhookEventStatus.ENQUEUED
            event.job_id = job_id
            event.enqueued_at = datetime.utcnow()

            logger.info(f"Marked event {event_id} as enqueued (job {job_id})")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark event as enqueued: {e}")
            return False

    def mark_processing(self, event_id: int) -> bool:
        """Mark event as currently processing."""
        from suno.common.models import WebhookEvent

        try:
            event = self.db.query(WebhookEvent).filter(
                WebhookEvent.id == event_id
            ).first()

            if not event:
                return False

            event.status = WebhookEventStatus.PROCESSING
            event.processing_started_at = datetime.utcnow()
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark event as processing: {e}")
            return False

    def mark_completed(self, event_id: int, result: Optional[Dict] = None) -> bool:
        """
        Mark event as successfully processed.

        Args:
            event_id: Database event ID
            result: Processing result metadata

        Returns:
            Success boolean
        """
        from suno.common.models import WebhookEvent

        try:
            event = self.db.query(WebhookEvent).filter(
                WebhookEvent.id == event_id
            ).first()

            if not event:
                return False

            event.status = WebhookEventStatus.COMPLETED
            event.completed_at = datetime.utcnow()
            event.processing_result = result or {}

            logger.info(f"Marked event {event_id} as completed")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark event as completed: {e}")
            return False

    def mark_failed(self, event_id: int, error: str, retry_count: int = 0) -> bool:
        """
        Mark event as failed with error details.

        Args:
            event_id: Database event ID
            error: Error message
            retry_count: Number of retries attempted

        Returns:
            Success boolean
        """
        from suno.common.models import WebhookEvent

        try:
            event = self.db.query(WebhookEvent).filter(
                WebhookEvent.id == event_id
            ).first()

            if not event:
                return False

            event.status = WebhookEventStatus.FAILED
            event.failed_at = datetime.utcnow()
            event.error_message = error
            event.retry_count = retry_count

            logger.warning(f"Marked event {event_id} as failed: {error}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark event as failed: {e}")
            return False

    def mark_dead_letter(self, event_id: int, reason: str) -> bool:
        """
        Move event to dead letter (permanent failure).

        Args:
            event_id: Database event ID
            reason: Reason for dead lettering

        Returns:
            Success boolean
        """
        from suno.common.models import WebhookEvent

        try:
            event = self.db.query(WebhookEvent).filter(
                WebhookEvent.id == event_id
            ).first()

            if not event:
                return False

            event.status = WebhookEventStatus.DEAD_LETTER
            event.dead_lettered_at = datetime.utcnow()
            event.error_message = reason

            logger.error(f"Dead-lettered event {event_id}: {reason}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to dead-letter event: {e}")
            return False

    def get_event_by_whop_id(self, whop_event_id: str):
        """Get event by Whop event ID."""
        from suno.common.models import WebhookEvent

        return self.db.query(WebhookEvent).filter(
            WebhookEvent.whop_event_id == whop_event_id
        ).first()

    def get_failed_events(self, limit: int = 20):
        """Get failed events that may be retried."""
        from suno.common.models import WebhookEvent

        return self.db.query(WebhookEvent).filter(
            WebhookEvent.status == WebhookEventStatus.FAILED,
            WebhookEvent.retry_count < 3,
        ).order_by(WebhookEvent.failed_at.desc()).limit(limit).all()

    def get_dead_letter_events(self, limit: int = 20):
        """Get dead-lettered events requiring operator intervention."""
        from suno.common.models import WebhookEvent

        return self.db.query(WebhookEvent).filter(
            WebhookEvent.status == WebhookEventStatus.DEAD_LETTER,
        ).order_by(WebhookEvent.dead_lettered_at.desc()).limit(limit).all()
