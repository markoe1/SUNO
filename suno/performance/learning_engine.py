"""
PerformanceLearningEngine: Record performance data and update CreatorProfile.
Phase 8: Manual performance recording (Phase 9: add webhooks).
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PerformanceLearningEngine:
    """Record performance data and learn from signals."""

    def record_performance(self, clip_id: int, variant_id: int | None, platform: str, data: dict, db):
        """
        Record performance metrics for a clip or variant.
        Returns: ClipPerformance object
        """
        from suno.common.models import ClipPerformance

        perf = ClipPerformance(
            clip_id=clip_id,
            variant_id=variant_id,
            platform=platform,
            views=data.get("views", 0),
            watch_time_seconds=data.get("watch_time_seconds"),
            completion_rate=data.get("completion_rate"),
            likes=data.get("likes", 0),
            shares=data.get("shares", 0),
            saves=data.get("saves", 0),
            comments=data.get("comments", 0),
            revenue_estimate=data.get("revenue_estimate"),
            recorded_at=datetime.utcnow(),
        )

        db.add(perf)
        db.flush()

        logger.info(
            f"[PERFORMANCE_RECORDED] clip_id={clip_id}, platform={platform}, "
            f"views={data.get('views', 0)}"
        )

        return perf

    def update_creator_profile(self, account_id: int, db):
        """
        Learn from top-performing clips and update CreatorProfile.
        Updates hook_style and winning_clip_ids.
        Returns: CreatorProfile or None
        """
        from suno.common.models import CreatorProfile, Clip, ClipVariant, ClipPerformance

        profile = db.query(CreatorProfile).filter(
            CreatorProfile.account_id == account_id
        ).first()

        if not profile:
            logger.warning(f"[PROFILE_UPDATE_SKIPPED] No profile for account {account_id}")
            return None

        # Find top 5 performing clips for this account
        top_clips = (
            db.query(Clip)
            .filter(Clip.account_id == account_id)
            .order_by(Clip.viral_score.desc())
            .limit(5)
            .all()
        )

        if not top_clips:
            logger.info(f"[PROFILE_UPDATE_SKIPPED] No clips for account {account_id}")
            return profile

        # Identify winning hook types from elected variants
        hook_type_counts = {}
        winning_clip_ids = []

        for clip in top_clips:
            winning_clip_ids.append(clip.id)

            # Find winning (elite or posted) variant
            winning_variant = (
                db.query(ClipVariant)
                .filter(
                    ClipVariant.clip_id == clip.id,
                    ClipVariant.status.in_(["elite", "posted"]),
                )
                .first()
            )

            if winning_variant and winning_variant.hook_type:
                hook_type = winning_variant.hook_type.lower()
                hook_type_counts[hook_type] = hook_type_counts.get(hook_type, 0) + 1

        # Update profile
        if hook_type_counts:
            most_common_hook = max(
                hook_type_counts.items(), key=lambda x: x[1]
            )[0]
            profile.hook_style = most_common_hook

        # Keep rolling window of top clips (max 50)
        profile.winning_clip_ids = winning_clip_ids[:50]

        db.commit()

        logger.info(
            f"[PROFILE_UPDATED] account_id={account_id}, "
            f"winning_hook_style={profile.hook_style}, top_clips={len(winning_clip_ids)}"
        )

        return profile
