"""
PHASE 3 ORCHESTRATOR: Autonomous Clip Processing Pipeline
Coordinates campaign ingestion, clip eligibility checking, caption generation,
scheduling, and posting across the entire system.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Main orchestrator for the autonomous clip processing pipeline.

    Workflow:
    1. Ingest campaigns and clips from source
    2. Check clip eligibility for each account
    3. Create assignments for eligible clips
    4. Queue assignments for caption generation
    5. Generate captions using Claude AI
    6. Schedule posts based on optimal times
    7. Execute posting jobs
    8. Track and monitor all jobs
    """

    def __init__(
        self,
        db: Session,
        anthropic_api_key: str,
    ):
        """
        Initialize orchestrator.

        Args:
            db: SQLAlchemy session
            anthropic_api_key: API key for Claude
        """
        self.db = db
        self.anthropic_api_key = anthropic_api_key

        # Initialize all pipeline components
        from suno.campaigns.ingestion import CampaignIngestionManager
        from suno.campaigns.eligibility import ClipEligibilityChecker, AssignmentQueueManager
        from suno.campaigns.caption_generator import CaptionGenerator, SchedulingManager
        from suno.campaigns.job_executor import CaptionJobExecutor, PostingJobExecutor, JobMonitor

        self.ingestion = CampaignIngestionManager(db)
        self.eligibility = ClipEligibilityChecker(db)
        self.assignment_queue = AssignmentQueueManager(db)
        self.caption_generator = CaptionGenerator(db, anthropic_api_key)
        self.scheduler = SchedulingManager(db)
        self.caption_executor = CaptionJobExecutor(db, anthropic_api_key)
        self.posting_executor = PostingJobExecutor(db)
        self.monitor = JobMonitor(db)

    def process_campaign_end_to_end(
        self,
        raw_campaign: Dict,
        raw_clips: List[Dict],
        account_ids: Optional[List[int]] = None,
    ) -> Dict:
        """
        Process a campaign end-to-end from ingestion to scheduling.

        Args:
            raw_campaign: Raw campaign data from source
            raw_clips: List of raw clip data from source
            account_ids: Optional list of specific accounts to process for

        Returns:
            Result dict with processing stats
        """
        logger.info("Starting end-to-end campaign processing")
        result = {
            "campaign_ingestion": None,
            "clip_ingestions": None,
            "assignments_created": None,
            "jobs_queued": None,
            "total_success": False,
            "errors": [],
        }

        try:
            # STEP 1: Ingest campaign
            logger.info("Step 1: Ingesting campaign")
            is_new, campaign = self.ingestion.ingest_campaign(raw_campaign)
            result["campaign_ingestion"] = {
                "is_new": is_new,
                "campaign_id": campaign.id,
                "title": campaign.title,
            }

            # STEP 2: Ingest clips
            logger.info("Step 2: Ingesting clips")
            clip_stats = self.ingestion.ingest_clips_batch(campaign.id, raw_clips)
            result["clip_ingestions"] = clip_stats

            if clip_stats["new"] == 0 and clip_stats["existing"] == 0:
                logger.warning("No clips ingested")
                return result

            # STEP 3: Get active accounts if not specified
            if account_ids is None:
                from suno.common.models import Account
                from suno.common.enums import MembershipLifecycle

                accounts = self.db.query(Account).join(
                    Account.membership
                ).filter(
                    Account.automation_enabled == True,
                ).all()
                account_ids = [acc.id for acc in accounts]
                logger.info(f"Processing for {len(account_ids)} active accounts")

            # STEP 4: Create assignments for all eligible clips
            logger.info("Step 3: Creating clip assignments")
            from suno.common.models import Clip

            clips = self.db.query(Clip).filter(Clip.campaign_id == campaign.id).all()
            assignment_stats = {
                "total_created": 0,
                "total_skipped": 0,
                "total_errors": 0,
            }

            for clip in clips:
                stats = self.assignment_queue.create_assignments(
                    clip.id,
                    account_ids,
                    campaign.target_platforms,
                )
                assignment_stats["total_created"] += stats["created"]
                assignment_stats["total_skipped"] += stats["skipped"]
                assignment_stats["total_errors"] += stats["errors"]

            result["assignments_created"] = assignment_stats

            # STEP 5: Queue assignments for caption generation
            logger.info("Step 4: Queueing caption generation jobs")
            from suno.common.models import ClipAssignment

            assignments = self.db.query(ClipAssignment.id).filter(
                ClipAssignment.clip_id.in_([c.id for c in clips])
            ).all()

            queue_stats = self.assignment_queue.queue_for_caption_generation(
                [a[0] for a in assignments]
            )
            result["jobs_queued"] = queue_stats

            result["total_success"] = True
            logger.info(f"Campaign processing complete: {result}")

            return result

        except Exception as e:
            logger.error(f"Campaign processing failed: {e}")
            result["errors"].append(str(e))
            return result

    def run_caption_generation_batch(self, limit: int = 20) -> Dict:
        """
        Run caption generation jobs in batch.

        Args:
            limit: Maximum jobs to process

        Returns:
            Stats dict with succeeded/failed counts
        """
        logger.info(f"Running caption generation batch (limit={limit})")
        stats = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "errors": [],
        }

        try:
            # Get pending jobs
            job_ids = self.caption_executor.get_pending_jobs(limit)
            logger.info(f"Found {len(job_ids)} pending caption jobs")

            for job_id in job_ids:
                result = self.caption_executor.execute_job(job_id)
                stats["processed"] += 1

                if result["success"]:
                    stats["succeeded"] += 1
                else:
                    stats["failed"] += 1
                    stats["errors"].append(result.get("error", "Unknown error"))

            logger.info(f"Caption batch complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Caption generation batch failed: {e}")
            stats["errors"].append(str(e))
            return stats

    def run_posting_batch(self, limit: int = 20) -> Dict:
        """
        Run posting jobs in batch.

        Args:
            limit: Maximum jobs to process

        Returns:
            Stats dict with succeeded/failed counts
        """
        logger.info(f"Running posting batch (limit={limit})")
        stats = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "errors": [],
        }

        try:
            # Get pending jobs
            job_ids = self.posting_executor.get_pending_jobs(limit)
            logger.info(f"Found {len(job_ids)} pending posting jobs")

            for job_id in job_ids:
                result = self.posting_executor.execute_job(job_id)
                stats["processed"] += 1

                if result["success"]:
                    stats["succeeded"] += 1
                else:
                    stats["failed"] += 1
                    if "error" in result:
                        stats["errors"].append(result["error"])

            logger.info(f"Posting batch complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Posting batch failed: {e}")
            stats["errors"].append(str(e))
            return stats

    def run_full_pipeline_iteration(self) -> Dict:
        """
        Run one complete pipeline iteration:
        1. Generate captions
        2. Schedule posts
        3. Execute posts
        4. Monitor health

        Returns:
            Comprehensive stats dict
        """
        logger.info("Running full pipeline iteration")
        result = {
            "caption_generation": None,
            "posting": None,
            "metrics": None,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            # Run caption generation
            caption_result = self.run_caption_generation_batch(limit=10)
            result["caption_generation"] = caption_result

            # Run posting
            posting_result = self.run_posting_batch(limit=10)
            result["posting"] = posting_result

            # Get metrics
            metrics = self.monitor.get_execution_metrics(hours=24)
            result["metrics"] = metrics

            logger.info(f"Pipeline iteration complete: {result}")
            return result

        except Exception as e:
            logger.error(f"Pipeline iteration failed: {e}")
            result["error"] = str(e)
            return result

    def get_system_health(self) -> Dict:
        """
        Get overall system health and status.

        Returns:
            Health dict with queue depths, error rates, etc.
        """
        from suno.common.models import (
            CaptionJob, PostJob, Account, Campaign, Clip,
            ClipAssignment, Membership
        )
        from suno.common.enums import JobLifecycle, MembershipLifecycle
        from sqlalchemy import func

        health = {
            "timestamp": datetime.utcnow().isoformat(),
            "queues": {
                "pending_caption_jobs": 0,
                "pending_post_jobs": 0,
                "failed_jobs": 0,
                "dead_letter_jobs": 0,
            },
            "inventory": {
                "total_campaigns": 0,
                "total_clips": 0,
                "pending_assignments": 0,
                "active_accounts": 0,
            },
            "metrics": None,
        }

        try:
            # Queue depths
            health["queues"]["pending_caption_jobs"] = (
                self.db.query(func.count(CaptionJob.id))
                .filter(CaptionJob.status == JobLifecycle.PENDING)
                .scalar() or 0
            )

            health["queues"]["pending_post_jobs"] = (
                self.db.query(func.count(PostJob.id))
                .filter(PostJob.status == JobLifecycle.PENDING)
                .scalar() or 0
            )

            health["queues"]["failed_jobs"] = (
                self.db.query(func.count(CaptionJob.id))
                .filter(CaptionJob.status == JobLifecycle.FAILED)
                .scalar() or 0
            ) + (
                self.db.query(func.count(PostJob.id))
                .filter(PostJob.status == JobLifecycle.FAILED)
                .scalar() or 0
            )

            # Inventory
            health["inventory"]["total_campaigns"] = (
                self.db.query(func.count(Campaign.id)).scalar() or 0
            )

            health["inventory"]["total_clips"] = (
                self.db.query(func.count(Clip.id)).scalar() or 0
            )

            health["inventory"]["pending_assignments"] = (
                self.db.query(func.count(ClipAssignment.id)).scalar() or 0
            )

            health["inventory"]["active_accounts"] = (
                self.db.query(func.count(Account.id))
                .filter(Account.automation_enabled == True)
                .scalar() or 0
            )

            # Metrics
            health["metrics"] = self.monitor.get_execution_metrics(hours=24)

            return health

        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            health["error"] = str(e)
            return health
