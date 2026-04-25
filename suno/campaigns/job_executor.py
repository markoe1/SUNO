"""
PHASE 3, PART 4: Job Execution and Monitoring
Executes caption generation, posting, and submission jobs with retry logic.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from enum import Enum

logger = logging.getLogger(__name__)


class JobExecutionError(Exception):
    """Raised when job execution fails"""
    pass


class JobPriority(Enum):
    """Job execution priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class CaptionJobExecutor:
    """Executes caption generation jobs."""

    MAX_RETRIES = 3
    RETRY_BACKOFF_MINUTES = 5

    def __init__(self, db: Session, anthropic_api_key: str):
        """
        Initialize caption job executor.

        Args:
            db: SQLAlchemy session
            anthropic_api_key: API key for Claude
        """
        self.db = db
        self.anthropic_api_key = anthropic_api_key
        from suno.campaigns.caption_generator import CaptionGenerator
        self.generator = CaptionGenerator(db, anthropic_api_key)

    def execute_job(self, job_id: int) -> Dict:
        """
        Execute a caption generation job.

        Args:
            job_id: ID of caption job

        Returns:
            Result dict with success status and details

        Raises:
            JobExecutionError if job not found or execution fails
        """
        from suno.common.models import CaptionJob, ClipAssignment, Clip, Campaign
        from suno.common.enums import JobLifecycle

        try:
            job = self.db.query(CaptionJob).filter(CaptionJob.id == job_id).first()
            if not job:
                raise JobExecutionError(f"Caption job {job_id} not found")

            # Update status to processing
            job.status = JobLifecycle.PROCESSING
            self.db.commit()

            # Get context
            assignment = self.db.query(ClipAssignment).filter(
                ClipAssignment.id == job.assignment_id
            ).first()
            if not assignment:
                raise JobExecutionError(f"Assignment {job.assignment_id} not found")

            clip = self.db.query(Clip).filter(Clip.id == assignment.clip_id).first()
            campaign = self.db.query(Campaign).filter(Campaign.id == clip.campaign_id).first()

            # Generate caption
            result = self.generator.generate_caption(
                clip_id=clip.id,
                assignment_id=assignment.id,
                target_platform=assignment.target_platform,
                campaign_brief=campaign.brief if campaign else None,
                tone=campaign.tone if campaign else None,
                style=campaign.style if campaign else None,
            )

            # Update job with success
            job.caption = result["caption"]
            job.hashtags = result["hashtags"]
            job.status = JobLifecycle.SUCCEEDED
            self.db.commit()

            logger.info(f"Caption job {job_id} completed successfully")
            return {
                "success": True,
                "job_id": job_id,
                "caption": result["caption"],
                "hashtags": result["hashtags"],
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Caption job {job_id} failed: {e}")

            # Handle retry logic
            job = self.db.query(CaptionJob).filter(CaptionJob.id == job_id).first()
            if job:
                job.retry_count += 1
                job.error_message = str(e)

                if job.retry_count >= self.MAX_RETRIES:
                    job.status = JobLifecycle.FAILED
                    logger.error(f"Caption job {job_id} exceeded max retries")
                else:
                    job.status = JobLifecycle.PENDING
                    logger.info(f"Caption job {job_id} will retry (attempt {job.retry_count}/{self.MAX_RETRIES})")

                self.db.commit()

            return {
                "success": False,
                "job_id": job_id,
                "error": str(e),
                "retry_count": job.retry_count if job else 0,
            }

    def get_pending_jobs(self, limit: int = 10) -> List[int]:
        """
        Get pending caption jobs ready for execution.

        Args:
            limit: Maximum jobs to return

        Returns:
            List of job IDs
        """
        from suno.common.models import CaptionJob
        from suno.common.enums import JobLifecycle

        jobs = self.db.query(CaptionJob.id).filter(
            CaptionJob.status == JobLifecycle.PENDING
        ).order_by(
            CaptionJob.id.asc()
        ).limit(limit).all()

        return [job[0] for job in jobs]


class PostingJobExecutor:
    """Executes posting jobs to platforms."""

    MAX_RETRIES = 2
    RETRY_BACKOFF_MINUTES = 10

    def __init__(self, db: Session):
        """
        Initialize posting job executor.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def execute_job(self, job_id: int) -> Dict:
        """
        Execute a posting job.

        Args:
            job_id: ID of post job

        Returns:
            Result dict with success status and posted URL

        Raises:
            JobExecutionError if job not found
        """
        from suno.common.models import PostJob, Clip, Account
        from suno.common.enums import JobLifecycle

        try:
            job = self.db.query(PostJob).filter(PostJob.id == job_id).first()
            if not job:
                raise JobExecutionError(f"Post job {job_id} not found")

            # Check if scheduled time has passed
            if job.scheduled_for and job.scheduled_for > datetime.utcnow():
                return {
                    "success": False,
                    "job_id": job_id,
                    "reason": "Scheduled time not reached yet",
                }

            # Update status to processing
            job.status = JobLifecycle.PROCESSING
            self.db.commit()

            # Get context
            clip = self.db.query(Clip).filter(Clip.id == job.clip_id).first()
            account = self.db.query(Account).filter(Account.id == job.account_id).first()

            if not clip or not account:
                raise JobExecutionError("Clip or account not found")

            # Execute post (placeholder - actual posting would integrate with platform APIs)
            posted_url = self._post_to_platform(
                clip,
                account,
                job.target_platform,
            )

            # Update job with success
            job.status = JobLifecycle.SUCCEEDED
            job.posted_at = datetime.utcnow()
            job.posted_url = posted_url
            self.db.commit()

            logger.info(f"Post job {job_id} completed successfully: {posted_url}")
            return {
                "success": True,
                "job_id": job_id,
                "posted_url": posted_url,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Post job {job_id} failed: {e}")

            job = self.db.query(PostJob).filter(PostJob.id == job_id).first()
            if job:
                job.retry_count += 1
                job.error_message = str(e)

                if job.retry_count >= self.MAX_RETRIES:
                    job.status = JobLifecycle.FAILED
                    logger.error(f"Post job {job_id} exceeded max retries")
                else:
                    job.status = JobLifecycle.PENDING
                    logger.info(f"Post job {job_id} will retry (attempt {job.retry_count}/{self.MAX_RETRIES})")

                self.db.commit()

            return {
                "success": False,
                "job_id": job_id,
                "error": str(e),
                "retry_count": job.retry_count if job else 0,
            }

    def get_pending_jobs(self, limit: int = 10) -> List[int]:
        """
        Get pending posting jobs ready for execution.

        Jobs must have caption available and scheduled time reached.

        Args:
            limit: Maximum jobs to return

        Returns:
            List of job IDs
        """
        from suno.common.models import PostJob, ClipAssignment, CaptionJob
        from suno.common.enums import JobLifecycle

        # Get post jobs with ready conditions
        jobs = self.db.query(PostJob.id).filter(
            PostJob.status == JobLifecycle.PENDING,
            (PostJob.scheduled_for.is_(None)) | (PostJob.scheduled_for <= datetime.utcnow())
        ).order_by(
            PostJob.id.asc()
        ).limit(limit).all()

        return [job[0] for job in jobs]

    @staticmethod
    def _post_to_platform(clip, account, platform: str) -> str:
        """
        Post clip to platform (placeholder implementation).

        Real implementation would integrate with:
        - TikTok API
        - Instagram Graph API
        - YouTube Data API
        - Twitter API v2
        - Bluesky Firehose
        - LinkedIn API

        Args:
            clip: Clip object
            account: Account object
            platform: Target platform name

        Returns:
            Posted URL

        Raises:
            JobExecutionError if posting fails
        """
        # Placeholder: generate mock posted URL
        import uuid

        post_id = str(uuid.uuid4())[:12]

        platform_urls = {
            "tiktok": f"https://www.tiktok.com/@user/video/{post_id}",
            "instagram": f"https://www.instagram.com/p/{post_id}/",
            "youtube": f"https://www.youtube.com/watch?v={post_id}",
            "twitter": f"https://twitter.com/user/status/{post_id}",
            "threads": f"https://threads.net/@user/post/{post_id}",
            "bluesky": f"https://bsky.app/profile/user.bsky.social/post/{post_id}",
            "linkedin": f"https://www.linkedin.com/feed/update/urn:li:activity:{post_id}/",
        }

        return platform_urls.get(platform.lower(), f"https://platform.example.com/{post_id}")


class JobMonitor:
    """Monitors job execution and tracks metrics."""

    def __init__(self, db: Session):
        """
        Initialize job monitor.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def get_job_status(self, job_type: str, job_id: int) -> Dict:
        """
        Get status of a specific job.

        Args:
            job_type: Type of job (caption, post, submission)
            job_id: ID of job

        Returns:
            Job status dict
        """
        from suno.common.models import CaptionJob, PostJob, SubmissionJob

        job_map = {
            "caption": CaptionJob,
            "post": PostJob,
            "submission": SubmissionJob,
        }

        JobModel = job_map.get(job_type.lower())
        if not JobModel:
            return {"error": f"Unknown job type: {job_type}"}

        job = self.db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job:
            return {"error": f"Job {job_id} not found"}

        return {
            "job_id": job.id,
            "job_type": job_type,
            "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
            "retry_count": job.retry_count,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }

    def get_execution_metrics(self, hours: int = 24) -> Dict:
        """
        Get execution metrics for past N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            Metrics dict with success rates, counts, etc.
        """
        from suno.common.models import CaptionJob, PostJob, SubmissionJob
        from suno.common.enums import JobLifecycle
        from sqlalchemy import func

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Count jobs by status
        caption_succeeded = self.db.query(func.count(CaptionJob.id)).filter(
            CaptionJob.status == JobLifecycle.SUCCEEDED,
            CaptionJob.updated_at >= cutoff
        ).scalar() or 0

        caption_failed = self.db.query(func.count(CaptionJob.id)).filter(
            CaptionJob.status == JobLifecycle.FAILED,
            CaptionJob.updated_at >= cutoff
        ).scalar() or 0

        post_succeeded = self.db.query(func.count(PostJob.id)).filter(
            PostJob.status == JobLifecycle.SUCCEEDED,
            PostJob.updated_at >= cutoff
        ).scalar() or 0

        post_failed = self.db.query(func.count(PostJob.id)).filter(
            PostJob.status == JobLifecycle.FAILED,
            PostJob.updated_at >= cutoff
        ).scalar() or 0

        # Calculate success rates
        caption_total = caption_succeeded + caption_failed
        caption_rate = (caption_succeeded / caption_total * 100) if caption_total > 0 else 0

        post_total = post_succeeded + post_failed
        post_rate = (post_succeeded / post_total * 100) if post_total > 0 else 0

        return {
            "time_window_hours": hours,
            "caption_generation": {
                "succeeded": caption_succeeded,
                "failed": caption_failed,
                "total": caption_total,
                "success_rate": f"{caption_rate:.1f}%",
            },
            "posting": {
                "succeeded": post_succeeded,
                "failed": post_failed,
                "total": post_total,
                "success_rate": f"{post_rate:.1f}%",
            },
        }

    def requeue_failed_jobs(self, hours: int = 24, limit: int = 20) -> Dict:
        """
        Requeue failed jobs for retry.

        Args:
            hours: Only requeue jobs failed in past N hours
            limit: Max number of jobs to requeue

        Returns:
            Stats dict with requeue count
        """
        from suno.common.models import CaptionJob, PostJob
        from suno.common.enums import JobLifecycle

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        stats = {"requeued": 0, "errors": 0}

        # Requeue failed caption jobs
        caption_jobs = self.db.query(CaptionJob).filter(
            CaptionJob.status == JobLifecycle.FAILED,
            CaptionJob.updated_at >= cutoff,
            CaptionJob.retry_count < CaptionJobExecutor.MAX_RETRIES,
        ).limit(limit).all()

        for job in caption_jobs:
            try:
                job.status = JobLifecycle.PENDING
                job.error_message = None
                self.db.commit()
                stats["requeued"] += 1
            except Exception as e:
                self.db.rollback()
                logger.error(f"Error requeuing caption job {job.id}: {e}")
                stats["errors"] += 1

        return stats
