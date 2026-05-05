"""
Clip Assignment and Scheduling
Creates clip assignments and schedules them for caption generation and posting.
Uses real job queueing for all operations.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AssignmentScheduler:
    """
    Manages clip assignment creation and scheduling.

    Workflow:
    1. Find eligible clips from campaigns
    2. Check account capacity (daily limits, platform availability)
    3. Create assignments
    4. Schedule caption generation jobs
    """

    def __init__(self, db: Session, queue_manager):
        """
        Initialize assignment scheduler.

        Args:
            db: SQLAlchemy session
            queue_manager: JobQueueManager instance
        """
        self.db = db
        self.queue_manager = queue_manager

    def assign_clips_for_account(
        self,
        account_id: int,
        limit: int = 10,
    ) -> Dict[str, int]:
        """
        Assign available clips to an account.

        Args:
            account_id: Account ID
            limit: Max clips to assign

        Returns:
            Stats dict with assigned, skipped, error counts
        """
        from suno.common.models import (
            Account, Clip, Campaign, ClipAssignment,
            Membership
        )

        stats = {"assigned": 0, "skipped": 0, "errors": 0}

        try:
            # Get account and verify it's active
            account = self.db.query(Account).filter(Account.id == account_id).first()
            if not account or not account.automation_enabled:
                logger.warning(f"Account {account_id} not active")
                return stats

            membership = account.membership
            if not membership or membership.status != "active":
                logger.warning(f"Membership for account {account_id} not active")
                return stats

            # Get tier limits
            tier = membership.tier
            max_daily = tier.max_daily_clips
            platforms = tier.platforms

            # Check daily quota
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            from sqlalchemy import func
            today_count = self.db.query(func.count(ClipAssignment.id)).filter(
                ClipAssignment.account_id == account_id,
                ClipAssignment.created_at >= today_start,
            ).scalar() or 0

            remaining = max_daily - today_count
            if remaining <= 0:
                logger.info(f"Account {account_id} reached daily limit ({max_daily})")
                return stats

            # Find available clips without assignments
            available_clips = self.db.query(Clip).filter(
                Clip.available == True,
                Clip.platform_eligible == True,
                ~Clip.assignments.any(ClipAssignment.account_id == account_id),
            ).order_by(Clip.engagement_score.desc()).limit(min(limit, remaining)).all()

            logger.info(f"Found {len(available_clips)} available clips for account {account_id}")

            # Create assignments for each clip and platform
            for clip in available_clips:
                try:
                    for platform in platforms:
                        # Check platform quota for today
                        platform_count = self.db.query(func.count(ClipAssignment.id)).filter(
                            ClipAssignment.account_id == account_id,
                            ClipAssignment.target_platform == platform,
                            ClipAssignment.created_at >= today_start,
                        ).scalar() or 0

                        platform_limit = self._get_platform_limit(platform)
                        if platform_count >= platform_limit:
                            logger.debug(f"Platform {platform} quota reached for account {account_id}")
                            continue

                        # Create assignment
                        assignment = ClipAssignment(
                            clip_id=clip.id,
                            account_id=account_id,
                            target_platform=platform,
                            status="queued",
                            priority=self._calculate_priority(clip),
                        )
                        self.db.add(assignment)
                        self.db.flush()

                        # Enqueue caption generation job
                        try:
                            job_id = self.queue_manager.enqueue(
                                "high",
                                generate_caption_job,
                                kwargs={
                                    "assignment_id": assignment.id,
                                    "clip_id": clip.id,
                                    "target_platform": platform,
                                },
                            )
                            logger.info(f"Enqueued caption job {job_id} for assignment {assignment.id}")
                            stats["assigned"] += 1
                        except Exception as e:
                            logger.error(f"Failed to enqueue caption job: {e}")
                            stats["errors"] += 1
                            self.db.rollback()

                except Exception as e:
                    logger.error(f"Error assigning clip {clip.id}: {e}")
                    stats["errors"] += 1

            self.db.commit()
            logger.info(f"Assignment complete for account {account_id}: {stats}")
            return stats

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error in assign_clips_for_account: {e}")
            return stats

    def schedule_post_jobs(
        self,
        account_id: int,
        limit: int = 10,
    ) -> Dict[str, int]:
        """
        Schedule post jobs for captioned clips.

        Checks for completed captions and creates post jobs with optimal scheduling.

        Args:
            account_id: Account ID
            limit: Max jobs to create

        Returns:
            Stats dict with scheduled, skipped, error counts
        """
        from suno.common.models import (
            ClipAssignment, PostJob, CaptionJob,
        )
        from suno.common.enums import JobLifecycle, ClipLifecycle

        stats = {"scheduled": 0, "skipped": 0, "errors": 0}

        try:
            # Find assignments with completed captions
            completed_captions = self.db.query(CaptionJob).filter(
                CaptionJob.status == JobLifecycle.SUCCEEDED,
            ).limit(limit).all()

            logger.info(f"Found {len(completed_captions)} completed captions to schedule")

            for caption_job in completed_captions:
                try:
                    assignment = caption_job.assignment
                    if not assignment or assignment.account_id != account_id:
                        stats["skipped"] += 1
                        continue

                    # Check if post job already exists
                    existing = self.db.query(PostJob).filter(
                        PostJob.clip_id == assignment.clip_id,
                        PostJob.account_id == assignment.account_id,
                        PostJob.target_platform == assignment.target_platform,
                    ).first()

                    if existing:
                        logger.debug(f"Post job already exists for assignment {assignment.id}")
                        stats["skipped"] += 1
                        continue

                    # Calculate optimal posting time
                    scheduled_time = self._calculate_posting_time(
                        assignment.target_platform,
                        assignment.account.membership.tier
                    )

                    # Create post job
                    post_job = PostJob(
                        clip_id=assignment.clip_id,
                        account_id=assignment.account_id,
                        target_platform=assignment.target_platform,
                        status=JobLifecycle.PENDING,
                        scheduled_for=scheduled_time,
                    )
                    self.db.add(post_job)
                    self.db.flush()

                    # Enqueue posting job
                    job_id = self.queue_manager.enqueue(
                        "normal",
                        execute_post_job,
                        kwargs={
                            "post_job_id": post_job.id,
                        },
                    )

                    logger.info(f"Scheduled post job {post_job.id} for {assignment.target_platform} at {scheduled_time}")
                    stats["scheduled"] += 1

                except Exception as e:
                    logger.error(f"Error scheduling post job: {e}")
                    stats["errors"] += 1
                    self.db.rollback()

            self.db.commit()
            return stats

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error in schedule_post_jobs: {e}")
            return stats

    @staticmethod
    def _get_platform_limit(platform: str) -> int:
        """Get daily posting limit for platform."""
        limits = {
            "tiktok": 5,
            "instagram": 3,
            "youtube": 2,
            "twitter": 10,
            "threads": 5,
            "bluesky": 5,
            "linkedin": 2,
        }
        return limits.get(platform.lower(), 3)

    @staticmethod
    def _calculate_priority(clip) -> int:
        """Calculate assignment priority (0-100, higher = process first)."""
        priority = 0

        # Engagement score (0-50)
        priority += int(min(50, clip.engagement_score * 50))

        # Freshness (0-30): newer clips get higher priority
        age_hours = (datetime.utcnow() - clip.created_at).total_seconds() / 3600
        freshness = max(0, 30 - min(30, age_hours / 4))
        priority += int(freshness)

        # Trending (0-20): trending clips higher priority
        if clip.trending_category:
            priority += 20

        return min(100, priority)

    @staticmethod
    def _calculate_posting_time(platform: str, tier) -> datetime:
        """
        Calculate optimal posting time.

        Args:
            platform: Target platform
            tier: User tier

        Returns:
            Datetime to post
        """
        if not tier.scheduling:
            # Tier doesn't support scheduling, post ASAP
            return datetime.utcnow()

        # Platform-optimized times
        platform_hours = {
            "tiktok": (18, 21),      # 6-9 PM
            "instagram": (12, 13),   # 12-1 PM
            "youtube": (19, 20),     # 7-8 PM
            "twitter": (10, 17),     # 10 AM - 5 PM
            "threads": (14, 16),     # 2-4 PM
            "bluesky": (14, 16),     # 2-4 PM
            "linkedin": (9, 12),     # 9 AM - 12 PM
        }

        start_hour, end_hour = platform_hours.get(platform.lower(), (12, 13))
        optimal_hour = start_hour + (end_hour - start_hour) // 2

        # Schedule for tomorrow at optimal hour
        tomorrow = datetime.utcnow() + timedelta(days=1)
        return tomorrow.replace(hour=optimal_hour, minute=0, second=0, microsecond=0)


# Background job functions


def generate_caption_job(assignment_id: int, clip_id: int, target_platform: str):
    """Generate caption for clip in background."""
    from suno.database import SessionLocal
    from suno.campaigns.caption_generator import CaptionGenerator

    db = SessionLocal()
    try:
        import os
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        generator = CaptionGenerator(db, anthropic_key)
        result = generator.generate_caption(
            clip_id=clip_id,
            assignment_id=assignment_id,
            target_platform=target_platform,
        )
        logger.info(f"Caption generated for assignment {assignment_id}: {result['character_count']} chars")
        return result
    except Exception as e:
        logger.error(f"Caption generation failed: {e}")
        raise
    finally:
        db.close()


def execute_post_job(post_job_id: int):
    """Execute posting job in background."""
    from suno.database import SessionLocal
    from suno.campaigns.job_executor import PostingJobExecutor

    db = SessionLocal()
    try:
        executor = PostingJobExecutor(db)
        result = executor.execute_job(post_job_id)
        logger.info(f"Post job {post_job_id} executed: {result}")
        return result
    except Exception as e:
        logger.error(f"Post job execution failed: {e}")
        raise
    finally:
        db.close()
