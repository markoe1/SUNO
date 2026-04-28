"""
Background Job Worker
RQ Worker that processes queued jobs in priority order.
Handles provisioning, revocation, caption generation, and posting.
"""

import logging
import os
import signal
import sys
import socket
from typing import Optional

try:
    from redis import Redis
    from rq import Worker, Queue
except ImportError:
    raise ImportError("Install redis and rq: pip install redis rq")

logger = logging.getLogger(__name__)


class SUNOWorker:
    """
    SUNO background job worker.

    Processes jobs in this priority order:
    1. CRITICAL: provisioning, revocation
    2. HIGH: caption generation
    3. NORMAL: posting, scheduling
    4. LOW: analytics, cleanup
    """

    def __init__(self, redis_url: str = None, worker_name: str = "suno-worker"):
        """
        Initialize worker.

        Args:
            redis_url: Redis connection URL
            worker_name: Name for this worker instance
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.worker_name = worker_name

        # DEBUG: Log what Redis URL we're actually using
        redis_url_masked = self.redis_url.replace(self.redis_url.split('@')[0].split('://')[1], "***") if '@' in self.redis_url else self.redis_url
        logger.info(f"Redis URL being used: {redis_url_masked}")

        self.redis = Redis.from_url(self.redis_url, decode_responses=False)
        self.worker: Optional[Worker] = None

        logger.info(f"Initialized SUNO worker: {worker_name}")

    def run(self, interval: int = 30, job_monitoring_interval: int = 10):
        """
        Run the worker (blocks until interrupted).

        Args:
            interval: Check queue every N seconds
            job_monitoring_interval: Monitor job progress every N seconds
        """
        try:
            # Pre-import webhook processor so RQ can resolve the function path
            import suno.billing.webhook_processor
            logger.info("Pre-loaded suno.billing.webhook_processor for job execution")

            # Create queues and log their current lengths
            queues = [
                Queue("critical", connection=self.redis),
                Queue("high", connection=self.redis),
                Queue("normal", connection=self.redis),
                Queue("low", connection=self.redis),
            ]

            critical_queue_length = len(queues[0])
            logger.info(f"Queue lengths - critical: {critical_queue_length}, high: {len(queues[1])}, normal: {len(queues[2])}, low: {len(queues[3])}")

            # Create worker with priority queue order
            self.worker = Worker(
                queues=queues,
                connection=self.redis,
                name=self.worker_name,
                default_result_ttl=500,
                job_monitoring_interval=job_monitoring_interval,
            )

            logger.info(f"Starting worker {self.worker_name}")
            logger.info("Processing jobs from queues: critical > high > normal > low")
            logger.info(f"Connected to Redis: {self.redis_url}")

            # Register signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self._handle_shutdown)
            signal.signal(signal.SIGTERM, self._handle_shutdown)

            # Run worker with job monitoring
            logger.info(f"Worker {self.worker_name} ready to process jobs")
            self.worker.work(with_scheduler=False, logging_level=logging.INFO)

        except Exception as e:
            logger.error(f"Worker error: {e}")
            sys.exit(1)

    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")

        if self.worker:
            # Stop accepting new jobs
            self.worker.request_stop()

            # Wait for current job to complete
            logger.info("Waiting for current job to complete...")

        sys.exit(0)

    def get_status(self) -> dict:
        """Get worker status."""
        if not self.worker:
            return {"status": "not_running"}

        return {
            "name": self.worker.name,
            "status": self.worker.get_status(),
            "successful_jobs": self.worker.successful_job_count,
            "failed_jobs": self.worker.failed_job_count,
            "total_jobs": self.worker.successful_job_count + self.worker.failed_job_count,
        }


def run_worker(
    redis_url: str = None,
    worker_name: str = None,
    queue_check_interval: int = 30,
):
    """
    Start a background job worker.

    Args:
        redis_url: Redis URL
        worker_name: Worker name (auto-generated if not provided)
        queue_check_interval: How often to check queue in seconds
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Generate unique worker name if not provided
    if not worker_name:
        hostname = socket.gethostname()
        pid = os.getpid()
        worker_name = f"suno-worker-{hostname}-{pid}"

    worker = SUNOWorker(redis_url, worker_name)
    worker.run(interval=queue_check_interval)


if __name__ == "__main__":
    # Run worker if executed directly
    import argparse

    parser = argparse.ArgumentParser(description="SUNO Background Job Worker")
    parser.add_argument(
        "--redis-url",
        default=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        help="Redis connection URL",
    )
    parser.add_argument(
        "--worker-name",
        default=None,
        help="Worker name (auto-generated if not provided)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Queue check interval in seconds",
    )

    args = parser.parse_args()

    run_worker(
        redis_url=args.redis_url,
        worker_name=args.worker_name,
        queue_check_interval=args.interval,
    )
