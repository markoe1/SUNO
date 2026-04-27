"""Background job workers powered by RQ

Worker is launched via: python -m suno.workers.job_worker
which uses __main__.py for entry point.

Do NOT import job_worker here — causes RuntimeWarning with sys.modules
when running as a module.
"""

__all__ = []
