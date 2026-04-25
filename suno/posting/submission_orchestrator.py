"""
Submission Orchestrator
Manages submission lifecycle with retry logic and dead-letter queue.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from suno.posting.adapters import get_adapter

logger = logging.getLogger(__name__)


class SubmissionOrchestrator:
    """Orchestrates submission lifecycle with full retry logic."""

    MAX_RETRIES = 2
    RETRY_BACKOFF_MINUTES = 10

    def __init__(self, db: Session):
        """Initialize submission orchestrator."""
        self.db = db

    def execute_submission_job(
        self,
        submission_job_id: int,
        account_id: int,
        platform: str,
        account_credentials: Dict[str, str],
        posted_url: str,
        source_clip_url: str,
    ) -> Dict[str, Any]:
        """
        Execute a submission job with full retry logic.

        Args:
            submission_job_id: ID of submission job
            account_id: Account ID
            platform: Source platform name
            account_credentials: Platform credentials
            posted_url: URL of posted content
            source_clip_url: Original clip URL

        Returns:
            Result dict with status and details
        """
        from suno.common.models import SubmissionJob, DeadLetterJob
        from suno.common.enums import JobLifecycle

        try:
            # Get submission job
            submission_job = self.db.query(SubmissionJob).filter(
                SubmissionJob.id == submission_job_id
            ).first()

            if not submission_job:
                logger.error(f"Submission job {submission_job_id} not found")
                return {"success": False, "error": "Submission job not found"}

            # Get platform adapter
            adapter = get_adapter(platform)
            if not adapter:
                logger.error(f"No adapter for platform {platform}")
                submission_job.status = JobLifecycle.FAILED
                submission_job.error_message = f"No adapter for {platform}"
                self.db.commit()
                return {"success": False, "error": f"No adapter for {platform}"}

            # Execute submission
            result = adapter.submit_result(
                account_credentials=account_credentials,
                posted_url=posted_url,
                source_clip_url=source_clip_url,
            )

            if result:
                # Success
                submission_job.status = JobLifecycle.SUCCEEDED
                submission_job.submission_url = posted_url
                self.db.commit()

                logger.info(f"Submission job {submission_job_id} succeeded")
                return {
                    "success": True,
                    "submission_url": posted_url,
                }

            else:
                # Failure (retryable)
                submission_job.retry_count += 1

                if submission_job.retry_count >= self.MAX_RETRIES:
                    # Max retries reached: move to dead-letter
                    submission_job.status = JobLifecycle.FAILED
                    self.db.commit()

                    # Create dead-letter record
                    dead_letter = DeadLetterJob(
                        original_job_type="submission",
                        original_job_id=submission_job_id,
                        payload={
                            "submission_job_id": submission_job_id,
                            "platform": platform,
                            "posted_url": posted_url,
                        },
                        error_message=f"Max retries ({self.MAX_RETRIES}) reached",
                        retry_count=submission_job.retry_count,
                    )
                    self.db.add(dead_letter)
                    self.db.commit()

                    logger.error(f"Submission job {submission_job_id} dead-lettered")
                    return {
                        "success": False,
                        "error": "Max retries exceeded",
                        "dead_letter_job_id": dead_letter.id,
                    }
                else:
                    # Schedule retry
                    submission_job.status = JobLifecycle.PENDING
                    self.db.commit()

                    logger.warning(
                        f"Submission job {submission_job_id} retryable error "
                        f"(attempt {submission_job.retry_count}/{self.MAX_RETRIES})"
                    )
                    return {
                        "success": False,
                        "error": "Retryable error",
                        "retry_count": submission_job.retry_count,
                    }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error executing submission job {submission_job_id}: {e}")

            return {
                "success": False,
                "error": str(e),
                "unexpected": True,
            }

    def get_dead_letter_jobs(self, limit: int = 20) -> list:
        """Get dead-letter submission jobs requiring operator intervention."""
        from suno.common.models import DeadLetterJob

        return self.db.query(DeadLetterJob).filter(
            DeadLetterJob.original_job_type == "submission"
        ).order_by(
            DeadLetterJob.created_at.desc()
        ).limit(limit).all()
