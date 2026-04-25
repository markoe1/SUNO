"""
Submission Flow
Post results are submitted back to sources and tracked.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from enum import Enum

logger = logging.getLogger(__name__)


class SubmissionStatus(str, Enum):
    """Submission status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


class SubmissionFlow:
    """Manages submitting posted URLs back to source platforms."""

    def __init__(self, db: Session):
        """
        Initialize submission flow.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def submit_post(
        self,
        post_job_id: int,
        clip_id: int,
        posted_url: str,
        source_platform: str,
        source_clip_url: str,
    ) -> Dict[str, Any]:
        """
        Submit posted URL back to source platform.

        Args:
            post_job_id: ID of post job
            clip_id: ID of clip
            posted_url: URL where clip was posted
            source_platform: Original source platform
            source_clip_url: URL of original clip

        Returns:
            Result dict with submission status
        """
        from suno.common.models import SubmissionJob, PostJob
        from suno.common.enums import JobLifecycle

        try:
            # Get post job for context
            post_job = self.db.query(PostJob).filter(
                PostJob.id == post_job_id
            ).first()

            if not post_job:
                logger.warning(f"Post job {post_job_id} not found")
                return {"success": False, "error": "Post job not found"}

            # Create submission job record
            submission_job = SubmissionJob(
                post_job_id=post_job_id,
                clip_id=clip_id,
                source_platform=source_platform,
                status=JobLifecycle.PENDING,
                submission_url=posted_url,
            )
            self.db.add(submission_job)
            self.db.commit()

            logger.info(f"Created submission job {submission_job.id} for {source_platform}")

            # In real implementation, would call source platform API to submit result
            # For now, mark as submitted
            submission_job.status = JobLifecycle.SUCCEEDED
            submission_job.submission_id = f"sub_{posted_url.split('/')[-1]}"
            self.db.commit()

            return {
                "success": True,
                "submission_job_id": submission_job.id,
                "status": "submitted",
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Submission failed: {e}")
            return {"success": False, "error": str(e)}

    def track_submission(
        self,
        submission_job_id: int,
        accepted: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Track submission acceptance/rejection from source.

        Args:
            submission_job_id: ID of submission job
            accepted: Whether submission was accepted
            details: Platform-specific response details

        Returns:
            Success boolean
        """
        from suno.common.models import SubmissionJob

        try:
            submission = self.db.query(SubmissionJob).filter(
                SubmissionJob.id == submission_job_id
            ).first()

            if not submission:
                logger.warning(f"Submission {submission_job_id} not found")
                return False

            if accepted:
                submission.submission_id = details.get("submission_id") if details else None
                logger.info(f"Submission {submission_job_id} accepted")
            else:
                submission.error_message = details.get("reason") if details else "Rejected"
                logger.warning(f"Submission {submission_job_id} rejected: {submission.error_message}")

            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to track submission: {e}")
            return False

    def get_pending_submissions(self, limit: int = 20) -> list:
        """
        Get pending submissions to track.

        Args:
            limit: Max submissions to return

        Returns:
            List of submission job records
        """
        from suno.common.models import SubmissionJob
        from suno.common.enums import JobLifecycle

        return self.db.query(SubmissionJob).filter(
            SubmissionJob.status == JobLifecycle.PENDING
        ).order_by(
            SubmissionJob.created_at.asc()
        ).limit(limit).all()

    def retry_failed_submission(self, submission_job_id: int) -> bool:
        """
        Retry a failed submission.

        Args:
            submission_job_id: ID of submission job

        Returns:
            Success boolean
        """
        from suno.common.models import SubmissionJob
        from suno.common.enums import JobLifecycle

        try:
            submission = self.db.query(SubmissionJob).filter(
                SubmissionJob.id == submission_job_id
            ).first()

            if not submission:
                return False

            submission.status = JobLifecycle.PENDING
            submission.retry_count += 1
            submission.error_message = None
            self.db.commit()

            logger.info(f"Retrying submission {submission_job_id} (attempt {submission.retry_count})")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to retry submission: {e}")
            return False
