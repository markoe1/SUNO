"""
Job Queue Management using RQ + Redis
Central queueing system for all background jobs.
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
import json

try:
    from redis import Redis
    from rq import Queue, Worker, job
except ImportError:
    raise ImportError("Install redis and rq: pip install redis rq")

logger = logging.getLogger(__name__)


class JobQueueType(str, Enum):
    """Queue types by priority"""
    CRITICAL = "critical"      # Provisioning, revocation
    HIGH = "high"              # Caption generation
    NORMAL = "normal"          # Posting, scheduling
    LOW = "low"                # Analytics, cleanup


class JobQueueManager:
    """Manages all background job queueing."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        Initialize job queue manager.

        Args:
            redis_url: Redis connection URL
        """
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.queues = {
            JobQueueType.CRITICAL: Queue(JobQueueType.CRITICAL, connection=self.redis),
            JobQueueType.HIGH: Queue(JobQueueType.HIGH, connection=self.redis),
            JobQueueType.NORMAL: Queue(JobQueueType.NORMAL, connection=self.redis),
            JobQueueType.LOW: Queue(JobQueueType.LOW, connection=self.redis),
        }
        logger.info("Job queue manager initialized")

    def enqueue(
        self,
        queue_type,
        func,
        args: tuple = (),
        kwargs: Dict[str, Any] = None,
        job_timeout: int = 300,
        result_ttl: int = 500,
    ) -> str:
        """
        Enqueue a background job.

        Args:
            queue_type: Priority queue (str or JobQueueType enum)
            func: Callable to execute
            args: Positional arguments
            kwargs: Keyword arguments
            job_timeout: Max execution time in seconds
            result_ttl: Result time-to-live in seconds

        Returns:
            Job ID
        """
        # Handle both string and enum
        if isinstance(queue_type, str):
            try:
                queue_type = JobQueueType[queue_type.upper()]
            except KeyError:
                raise ValueError(f"Invalid queue type: {queue_type}")

        kwargs = kwargs or {}
        queue = self.queues[queue_type]

        try:
            rq_job = queue.enqueue(
                func,
                args=args,
                kwargs=kwargs,
                job_timeout=job_timeout,
                result_ttl=result_ttl,
            )
            logger.info(f"Enqueued job {rq_job.id} to {queue_type.value} queue")
            return rq_job.id
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            raise

    def get_job(self, job_id: str):
        """Get job object by ID."""
        return job.Job.fetch(job_id, connection=self.redis)

    def get_job_status(self, job_id: str) -> Optional[str]:
        """
        Get job status.

        Returns: queued, started, finished, failed, deferred
        """
        try:
            rq_job = self.get_job(job_id)
            return rq_job.get_status()
        except Exception as e:
            logger.warning(f"Failed to get job status {job_id}: {e}")
            return None

    def get_queue_status(self) -> Dict[str, int]:
        """Get status of all queues."""
        return {
            queue_type.value: len(queue)
            for queue_type, queue in self.queues.items()
        }

    def clear_queue(self, queue_type: JobQueueType):
        """Clear all jobs from queue (WARNING: use carefully)."""
        self.queues[queue_type].empty()
        logger.warning(f"Cleared {queue_type} queue")


def create_job_queue_manager(redis_url: str = None) -> JobQueueManager:
    """Factory to create job queue manager."""
    import os

    url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return JobQueueManager(url)
