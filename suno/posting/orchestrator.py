"""
Posting Orchestrator
Manages posting lifecycle from scheduled job to posted + submitted.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from suno.posting.adapters import get_adapter, is_platform_supported
from suno.posting.submission import SubmissionFlow

logger = logging.getLogger(__name__)


class PostingOrchestrator:
    """
    Orchestrates the complete posting lifecycle:
    1. Execute post job (call platform adapter)
    2. Store posted URL
    3. Enqueue submission (if needed)
    4. Handle retries on failure
    5. Move failed jobs to dead-letter queue
    """

    MAX_RETRIES = 2
    RETRY_BACKOFF_MINUTES = 10
    SUBMISSION_TIMEOUT_HOURS = 24

    def __init__(self, db: Session):
        """
        Initialize posting orchestrator.

        Args:
            db: SQLAlchemy session
        """
        self.db = db
        self.submission = SubmissionFlow(db)

    def execute_post_job(
        self,
        post_job_id: int,
        platform: str,
        account_credentials: Dict[str, str],
        clip_url: str,
        caption: str,
        hashtags: list,
    ) -> Dict[str, Any]:
        """
        Execute a posting job with full retry logic.

        Args:
            post_job_id: ID of post job
            platform: Target platform
            account_credentials: Platform-specific credentials
            clip_url: URL of clip to post
            caption: Post caption
            hashtags: List of hashtags

        Returns:
            Result dict with status and details
        """
        from suno.common.models import PostJob, DeadLetterJob
        from suno.common.enums import JobLifecycle

        try:
            # Get post job
            post_job = self.db.query(PostJob).filter(
                PostJob.id == post_job_id
            ).first()

            if not post_job:
                logger.error(f"Post job {post_job_id} not found")
                return {"success": False, "error": "Post job not found"}

            # Check platform support
            if not is_platform_supported(platform):
                logger.error(f"Platform {platform} not supported")
                post_job.status = JobLifecycle.FAILED
                post_job.error_message = f"Platform {platform} not supported"
                self.db.commit()

                return {
                    "success": False,
                    "error": f"Platform {platform} not supported",
                }

            # Get adapter
            adapter = get_adapter(platform)
            if not adapter:
                return {"success": False, "error": f"No adapter for {platform}"}

            # Validate account
            if not adapter.validate_account(account_credentials):
                logger.warning(f"Account validation failed for {platform}")
                return {"success": False, "error": "Account validation failed"}

            # Prepare payload
            payload = adapter.prepare_payload(
                clip_url=clip_url,
                caption=caption,
                hashtags=hashtags,
                metadata={"job_id": post_job_id},
            )

            # Execute post
            result = adapter.post(account_credentials, payload)

            if result.is_success():
                # Success: store posted URL
                post_job.status = JobLifecycle.SUCCEEDED
                post_job.posted_at = datetime.utcnow()
                post_job.posted_url = result.posted_url
                self.db.commit()

                logger.info(f"Post job {post_job_id} succeeded: {result.posted_url}")

                # Enqueue submission job
                self.submission.submit_post(
                    post_job_id=post_job_id,
                    clip_id=post_job.clip_id,
                    posted_url=result.posted_url,
                    source_platform=platform,
                    source_clip_url=clip_url,
                )

                return {
                    "success": True,
                    "posted_url": result.posted_url,
                    "post_id": result.post_id,
                }

            elif result.is_retryable():
                # Retryable error: increment retry count or dead-letter
                post_job.retry_count += 1
                post_job.error_message = result.error_message

                if post_job.retry_count >= self.MAX_RETRIES:
                    # Max retries reached: move to dead-letter
                    post_job.status = JobLifecycle.FAILED
                    self.db.commit()

                    # Create dead-letter record
                    dead_letter = DeadLetterJob(
                        original_job_type="post",
                        original_job_id=post_job_id,
                        payload={
                            "post_job_id": post_job_id,
                            "platform": platform,
                            "clip_url": clip_url,
                        },
                        error_message=f"Max retries ({self.MAX_RETRIES}) reached: {result.error_message}",
                        retry_count=post_job.retry_count,
                    )
                    self.db.add(dead_letter)
                    self.db.commit()

                    logger.error(f"Post job {post_job_id} dead-lettered after {self.MAX_RETRIES} retries")
                    return {
                        "success": False,
                        "error": "Max retries exceeded",
                        "dead_letter_job_id": dead_letter.id,
                    }
                else:
                    # Schedule retry
                    post_job.status = JobLifecycle.PENDING
                    self.db.commit()

                    logger.warning(
                        f"Post job {post_job_id} retryable error "
                        f"(attempt {post_job.retry_count}/{self.MAX_RETRIES}): {result.error_message}"
                    )

                    return {
                        "success": False,
                        "error": result.error_message,
                        "retryable": True,
                        "retry_count": post_job.retry_count,
                    }

            else:
                # Permanent error: fail immediately
                post_job.status = JobLifecycle.FAILED
                post_job.error_message = result.error_message
                self.db.commit()

                # Create dead-letter record
                dead_letter = DeadLetterJob(
                    original_job_type="post",
                    original_job_id=post_job_id,
                    payload={
                        "post_job_id": post_job_id,
                        "platform": platform,
                        "clip_url": clip_url,
                    },
                    error_message=f"Permanent error: {result.error_message}",
                    retry_count=post_job.retry_count,
                )
                self.db.add(dead_letter)
                self.db.commit()

                logger.error(f"Post job {post_job_id} permanent error: {result.error_message}")

                return {
                    "success": False,
                    "error": result.error_message,
                    "permanent": True,
                    "dead_letter_job_id": dead_letter.id,
                }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error executing post job {post_job_id}: {e}")

            return {
                "success": False,
                "error": str(e),
                "unexpected": True,
            }

    def get_dead_letter_jobs(self, limit: int = 20) -> list:
        """
        Get dead-letter jobs requiring operator intervention.

        Args:
            limit: Max jobs to return

        Returns:
            List of dead-letter job records
        """
        from suno.common.models import DeadLetterJob

        return self.db.query(DeadLetterJob).filter(
            DeadLetterJob.original_job_type == "post"
        ).order_by(
            DeadLetterJob.created_at.desc()
        ).limit(limit).all()

    def retry_dead_letter_job(self, dead_letter_job_id: int) -> bool:
        """
        Move dead-letter job back to pending for retry.

        Args:
            dead_letter_job_id: ID of dead-letter job

        Returns:
            Success boolean
        """
        from suno.common.models import DeadLetterJob, PostJob

        try:
            dead_letter = self.db.query(DeadLetterJob).filter(
                DeadLetterJob.id == dead_letter_job_id
            ).first()

            if not dead_letter:
                return False

            # Get original post job
            post_job = self.db.query(PostJob).filter(
                PostJob.id == dead_letter.original_job_id
            ).first()

            if not post_job:
                logger.warning(f"Original post job not found for dead-letter {dead_letter_job_id}")
                return False

            # Reset for retry (allow full cycle again)
            post_job.status = JobLifecycle.PENDING
            post_job.retry_count = 0
            post_job.error_message = None
            self.db.commit()

            logger.info(f"Moved dead-letter job {dead_letter_job_id} back to pending")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to retry dead-letter job: {e}")
            return False

    def get_posting_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get posting metrics for past N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            Metrics dict
        """
        from suno.common.models import PostJob, DeadLetterJob
        from suno.common.enums import JobLifecycle

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        succeeded = self.db.query(func.count(PostJob.id)).filter(
            PostJob.status == JobLifecycle.SUCCEEDED,
            PostJob.updated_at >= cutoff,
        ).scalar() or 0

        failed = self.db.query(func.count(PostJob.id)).filter(
            PostJob.status == JobLifecycle.FAILED,
            PostJob.updated_at >= cutoff,
        ).scalar() or 0

        dead_letter = self.db.query(func.count(DeadLetterJob.id)).filter(
            DeadLetterJob.original_job_type == "post",
            DeadLetterJob.created_at >= cutoff,
        ).scalar() or 0

        total = succeeded + failed
        success_rate = (succeeded / total * 100) if total > 0 else 0

        return {
            "time_window_hours": hours,
            "succeeded": succeeded,
            "failed": failed,
            "dead_letter": dead_letter,
            "total": total,
            "success_rate": f"{success_rate:.1f}%",
        }
