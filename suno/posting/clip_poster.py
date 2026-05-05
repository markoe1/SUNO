"""
PostingEngine: Database-only clip posting with variant scheduling and signal evaluation.
Phase 8: Staggered variant posting, no live platform API calls.
Phase 9: Wire platform adapters.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PostingEngine:
    """Schedule and manage clip posting (DB-only in Phase 8)."""

    def schedule_clip_posting(self, clip, variants, db, cooldown_minutes: int = 120) -> dict:
        """
        Mark clip as POSTED and schedule variants for posting.
        Raises ValueError if clip is not APPROVED.
        """        from suno.vantage.variant_engine import VariantEngine

        if clip.status != "approved":
            raise ValueError(
                f"Clip {clip.id} must be APPROVED to post. Current: {clip.status}"
            )

        # Assign posting schedule to variants
        variant_engine = VariantEngine()
        winner = variant_engine.select_winner(variants)
        variant_engine.assign_posting_schedule(variants, winner, db, cooldown_minutes)

        # Mark clip as POSTED (DB-only, no platform calls yet)
        clip.status = "posted"
        db.flush()

        first_post = winner.scheduled_for if winner else None
        last_post = None
        if variants:
            last_post = max(
                (v.scheduled_for for v in variants if v.scheduled_for),
                default=None,
            )

        logger.info(
            f"[CLIP_POSTED] clip_id={clip.id}, variants_scheduled={len(variants)}, "
            f"first_post={first_post}, last_post={last_post}, cooldown_min={cooldown_minutes}"
        )

        return {
            "clip_id": clip.id,
            "variants_scheduled": len(variants),
            "first_post_at": first_post.isoformat() if first_post else None,
            "last_post_at": last_post.isoformat() if last_post else None,
        }

    def run_due_postings(self, db) -> dict:
        """
        Post all variants that are due (scheduled_for <= now) and not suppressed.
        Enqueue signal evaluation job for each posted variant.
        """
        from suno.common.models import ClipVariant
        from suno.common.enums import VariantStatus
        from suno.common.job_queue import JobQueueManager, JobQueueType

        now = datetime.utcnow()

        # Query due variants
        due_variants = (
            db.query(ClipVariant)
            .filter(
                ClipVariant.scheduled_for <= now,
                ClipVariant.status == VariantStatus.ELECTED,
                ClipVariant.signal_status != "paused",
            )
            .all()
        )

        queue = JobQueueManager()
        posted_count = 0

        for variant in due_variants:
            # Gate: verify not suppressed by sibling
            if variant.signal_status == "paused":
                continue

            # Mark as posted
            variant.status = VariantStatus.POSTED
            variant.posted_at = now

            # Enqueue signal evaluation job at first_signal_at
            if variant.first_signal_at:
                delay_seconds = (
                    variant.first_signal_at - now
                ).total_seconds()
                if delay_seconds > 0:
                    queue.enqueue(
                        "evaluate_variant_signal_job",
                        variant.id,
                        queue_type=JobQueueType.LOW,
                        job_timeout="1h",
                        scheduled_at=variant.first_signal_at,
                    )
                    logger.info(
                        f"[SIGNAL_JOB_ENQUEUED] variant_id={variant.id}, "
                        f"scheduled_eval_at={variant.first_signal_at}"
                    )

            posted_count += 1

        db.commit()

        logger.info(f"[POSTINGS_EXECUTED] posted_count={posted_count}")

        return {"posted_count": posted_count}
