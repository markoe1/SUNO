"""
Entry point for running the worker as a module.
Allows: python -m suno.workers
"""

from .job_worker import run_worker
import os

if __name__ == "__main__":
    run_worker(
        redis_url=os.getenv("REDIS_URL"),
        worker_name=os.getenv("WORKER_NAME", "suno-worker"),
    )
