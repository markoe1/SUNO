"""
RevenueEngine: Estimate revenue and compute ROI.
Phase 8: Conservative formula-based estimation.
"""

import logging

logger = logging.getLogger(__name__)

NICHE_MULTIPLIERS = {
    "finance": 3.5,
    "fitness": 2.0,
    "entertainment": 1.5,
    "education": 2.5,
    "lifestyle": 1.2,
    "tech": 2.8,
    "gaming": 1.8,
    "music": 2.0,
    "sports": 2.2,
}

BASE_CPM_USD = 2.50  # USD per 1000 views
BASE_VIEWS = 5_000


class RevenueEngine:
    """Estimate revenue and compute ROI."""

    def estimate(self, clip, campaign, creator_profile) -> dict:
        """
        Estimate clip revenue based on niche, scores, and engagement potential.
        Returns: {"predicted_views": int, "estimated_value": float}
        """
        niche = creator_profile.niche if creator_profile else None
        niche_mult = NICHE_MULTIPLIERS.get(niche.lower(), 1.0) if niche else 1.0

        overall_score = clip.overall_score or 0.5
        monetization_score = clip.monetization_score or 0.5

        # Conservative view estimate
        predicted_views = int(BASE_VIEWS * (1.0 + overall_score) * niche_mult)

        # CPM-based revenue
        estimated_value = round(
            (predicted_views / 1000) * BASE_CPM_USD * monetization_score, 2
        )

        logger.info(
            f"[REVENUE_ESTIMATED] clip_id={clip.id}, predicted_views={predicted_views}, "
            f"estimated_value=${estimated_value}"
        )

        return {"predicted_views": predicted_views, "estimated_value": estimated_value}

    def compute_roi(self, estimated_value: float, ai_cost_usd: float) -> float | None:
        """
        Compute ROI as estimated_value / ai_cost_usd.
        Returns: float (ROI ratio) or None if cost is zero.
        """
        if ai_cost_usd <= 0:
            return None

        roi = estimated_value / ai_cost_usd
        return round(roi, 1)
