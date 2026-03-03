"""RQ queue setup."""

import os

from redis import Redis
from rq import Queue

redis_conn = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
q = Queue("suno-clips", connection=redis_conn, default_timeout=300)
