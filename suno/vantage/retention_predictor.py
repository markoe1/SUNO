"""
RetentionPredictor: Predict watch time and completion rate using Claude.
Phase 8: Haiku-powered retention analysis.
"""

import logging
import json
import anthropic

logger = logging.getLogger(__name__)

PREDICTOR_MODEL = "claude-haiku-4-5-20251001"

HAIKU_INPUT_COST = 0.80 / 1_000_000
HAIKU_OUTPUT_COST = 4.00 / 1_000_000


class RetentionPredictor:
    """Predict clip retention metrics using Claude."""

    def __init__(self, api_key: str, model: str = PREDICTOR_MODEL):
        self.api_key = api_key
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None

    def predict(self, clip, campaign, creator_profile) -> dict:
        """
        Predict retention metrics.
        Returns: {
            "predicted_watch_time": float (seconds),
            "predicted_completion_rate": float (0.0-1.0),
            "predicted_dropoff_ms": int,
            "cost_usd": float
        }
        """
        if not self.client:
            logger.warning("[RETENTION_SKIPPED] No API key provided")
            return {
                "predicted_watch_time": 30.0,
                "predicted_completion_rate": 0.5,
                "predicted_dropoff_ms": 5000,
                "cost_usd": 0.0,
            }

        niche = creator_profile.niche if creator_profile else None
        platform_focus = (
            creator_profile.platform_focus if creator_profile else []
        )
        duration_target = campaign.ideal_duration_seconds or 30

        prompt = f"""Predict retention metrics for this clip.

Title: {clip.title}
Niche: {niche or 'general'}
Duration Target: {duration_target}s
Platforms: {', '.join(platform_focus) if platform_focus else 'TikTok, Reels'}
Overall Score: {clip.overall_score or 0.5}

Return JSON with exactly these fields:
{{"predicted_watch_time": 30.0, "predicted_completion_rate": 0.72, "predicted_dropoff_ms": 8500}}

Rules:
- predicted_watch_time: seconds, between 3 and duration_target
- predicted_completion_rate: between 0.0 and 1.0
- predicted_dropoff_ms: milliseconds where 50% drop off

Return ONLY JSON, no explanation."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = input_tokens * HAIKU_INPUT_COST + output_tokens * HAIKU_OUTPUT_COST

            text = response.content[0].text.strip()
            data = json.loads(text)

            # Validate
            watch_time = float(data.get("predicted_watch_time", 30.0))
            completion_rate = float(data.get("predicted_completion_rate", 0.5))
            dropoff_ms = int(data.get("predicted_dropoff_ms", 5000))

            # Ensure in bounds
            watch_time = max(3.0, min(float(duration_target), watch_time))
            completion_rate = max(0.0, min(1.0, completion_rate))
            dropoff_ms = max(0, dropoff_ms)

            logger.info(
                f"[RETENTION_PREDICTED] clip_id={clip.id}, "
                f"watch_time={watch_time:.1f}s, completion_rate={completion_rate:.2f}, "
                f"cost_usd={cost_usd:.6f}"
            )

            return {
                "predicted_watch_time": watch_time,
                "predicted_completion_rate": completion_rate,
                "predicted_dropoff_ms": dropoff_ms,
                "cost_usd": cost_usd,
            }

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"[RETENTION_PARSE_ERROR] clip_id={clip.id}: {e}")
            return {
                "predicted_watch_time": 30.0,
                "predicted_completion_rate": 0.5,
                "predicted_dropoff_ms": 5000,
                "cost_usd": 0.0,
            }
        except Exception as e:
            logger.error(f"[RETENTION_FAILED] clip_id={clip.id}: {e}")
            return {
                "predicted_watch_time": 30.0,
                "predicted_completion_rate": 0.5,
                "predicted_dropoff_ms": 5000,
                "cost_usd": 0.0,
            }
