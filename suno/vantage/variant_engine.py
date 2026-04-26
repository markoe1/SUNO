"""
VariantEngine: Create, schedule, and adapt clip variants with dynamic signal intelligence.
Phase 8: Sibling suppression, cooldown staggering, early signal evaluation.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

FIRST_SIGNAL_WINDOW_MINUTES = 30  # How soon after posting to evaluate early perf
STRONG_SIGNAL_VIEWS_THRESHOLD = 500  # Views in first window = strong signal
STRONG_SIGNAL_ENGAGEMENT_THRESHOLD = 0.05  # Engagement rate = strong


class VariantEngine:
    """Create and manage clip variants with dynamic signal suppression."""

    def create_variants(self, clip_id: int, hooks: list, db, cooldown_minutes: int = 120) -> list:
        """
        Create variant records for each hook.
        Returns: list of ClipVariant objects
        """
        from suno.common.models import ClipVariant
        from suno.common.enums import VariantStatus

        # Assign shared group ID to all variants
        variant_group_id = uuid.uuid4().hex

        variants = []
        for hook in hooks:
            variant = ClipVariant(
                clip_id=clip_id,
                variant_group_id=variant_group_id,
                variant_type="hook",
                content=hook["content"],
                hook_type=hook.get("hook_type", "unknown"),
                status=VariantStatus.DRAFT,
                signal_status="pending",
            )

            # Assign predicted engagement by hook type
            hook_type = hook.get("hook_type", "unknown").lower()
            if hook_type == "authority":
                variant.predicted_engagement = 0.80
            elif hook_type == "emotional":
                variant.predicted_engagement = 0.75
            elif hook_type == "curiosity":
                variant.predicted_engagement = 0.70
            elif hook_type == "controversial":
                variant.predicted_engagement = 0.65
            else:
                variant.predicted_engagement = 0.50

            variants.append(variant)
            db.add(variant)

        db.flush()  # Assign IDs without committing

        logger.info(
            f"[VARIANT_CREATED] clip_id={clip_id}, count={len(variants)}, "
            f"group_id={variant_group_id}"
        )

        return variants

    def select_winner(self, variants: list):
        """Select variant with highest predicted_engagement."""
        if not variants:
            return None
        return max(variants, key=lambda v: v.predicted_engagement or 0.0)

    def assign_posting_schedule(
        self, variants: list, winner, db=None, cooldown_minutes: int = 120
    ) -> list:
        """
        Assign posting schedule to variants.
        Winner: immediate posting
        Siblings: staggered at cooldown intervals, suppressed if strong signal detected
        """
        from suno.common.enums import VariantStatus

        now = datetime.utcnow()

        # Winner posts immediately
        winner.status = VariantStatus.ELITE
        winner.scheduled_for = now
        winner.first_signal_at = now + timedelta(minutes=FIRST_SIGNAL_WINDOW_MINUTES)
        winner.signal_status = "pending"

        # Siblings post on staggered schedule
        sibling_index = 0
        for variant in variants:
            if variant.id == winner.id:
                continue

            sibling_index += 1
            variant.status = VariantStatus.ELECTED
            variant.scheduled_for = now + sibling_index * timedelta(
                minutes=cooldown_minutes
            )
            variant.first_signal_at = variant.scheduled_for + timedelta(
                minutes=FIRST_SIGNAL_WINDOW_MINUTES
            )
            variant.signal_status = "pending"

        logger.info(
            f"[SCHEDULE_ASSIGNED] winner_id={winner.id}, "
            f"siblings={len(variants) - 1}, cooldown_min={cooldown_minutes}"
        )

        return variants

    def evaluate_signal_and_adapt(self, posted_variant_id: int, db):
        """
        Evaluate early performance of a posted variant.
        If strong signal: suppress siblings. If weak: allow next sibling to proceed.
        Returns: {"signal_status": str, "suppressed_count": int, "next_variant_id": int|None}
        """
        from suno.common.models import ClipVariant, ClipPerformance

        variant = db.query(ClipVariant).filter(ClipVariant.id == posted_variant_id).first()
        if not variant:
            logger.error(f"[SIGNAL_EVAL_FAILED] Variant not found: {posted_variant_id}")
            return {"signal_status": "error", "suppressed_count": 0, "next_variant_id": None}

        # Fetch performance data for this variant since posting
        performances = (
            db.query(ClipPerformance)
            .filter(
                ClipPerformance.variant_id == posted_variant_id,
                ClipPerformance.recorded_at >= (variant.posted_at or datetime.utcnow()),
            )
            .all()
        )

        total_views = sum(p.views for p in performances)
        total_engagement = (
            sum(p.likes + p.shares + p.saves + p.comments for p in performances)
        )
        engagement_rate = (
            (total_engagement / total_views) if total_views > 0 else 0.0
        )

        # Determine signal strength
        is_strong = (
            total_views >= STRONG_SIGNAL_VIEWS_THRESHOLD
            or engagement_rate >= STRONG_SIGNAL_ENGAGEMENT_THRESHOLD
        )

        if is_strong:
            # Strong signal: suppress all siblings
            variant.signal_status = "strong"

            siblings = (
                db.query(ClipVariant)
                .filter(
                    ClipVariant.variant_group_id == variant.variant_group_id,
                    ClipVariant.id != posted_variant_id,
                    ClipVariant.status.in_(["elected", "draft"]),
                )
                .all()
            )

            for sibling in siblings:
                sibling.signal_status = "paused"
                sibling.scheduled_for = None

            db.commit()

            logger.info(
                f"[VARIANT_SUPPRESSED] group_id={variant.variant_group_id}, "
                f"suppressed_count={len(siblings)}, reason=strong_signal, "
                f"views={total_views}, engagement_rate={engagement_rate:.4f}"
            )

            return {
                "signal_status": "strong",
                "suppressed_count": len(siblings),
                "next_variant_id": None,
            }
        else:
            # Weak signal: allow next sibling to proceed
            variant.signal_status = "weak"

            next_sibling = (
                db.query(ClipVariant)
                .filter(
                    ClipVariant.variant_group_id == variant.variant_group_id,
                    ClipVariant.id != posted_variant_id,
                    ClipVariant.status == "elected",
                    ClipVariant.signal_status == "pending",
                )
                .order_by(ClipVariant.scheduled_for)
                .first()
            )

            db.commit()

            next_id = next_sibling.id if next_sibling else None

            logger.info(
                f"[VARIANT_WEAK_SIGNAL] group_id={variant.variant_group_id}, "
                f"next_variant_id={next_id}, views={total_views}"
            )

            return {
                "signal_status": "weak",
                "suppressed_count": 0,
                "next_variant_id": next_id,
            }
