"""
HookEngine: Generate hook variants using Claude + token cost tracking.
Phase 8: Haiku for bulk (10 hooks), Sonnet for polish (elite winner).
"""

import logging
import json
from typing import Optional
import anthropic

logger = logging.getLogger(__name__)

DRAFT_MODEL = "claude-haiku-4-5-20251001"
ELITE_MODEL = "claude-sonnet-4-6"

HAIKU_INPUT_COST = 0.80 / 1_000_000  # USD per token
HAIKU_OUTPUT_COST = 4.00 / 1_000_000
SONNET_INPUT_COST = 3.00 / 1_000_000
SONNET_OUTPUT_COST = 15.00 / 1_000_000


class HookEngine:
    """Generate hook variants and polish winners with token cost tracking."""

    def __init__(
        self,
        api_key: str,
        draft_model: str = DRAFT_MODEL,
        elite_model: str = ELITE_MODEL,
    ):
        self.api_key = api_key
        self.draft_model = draft_model
        self.elite_model = elite_model
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None

    def generate_hooks(self, clip, campaign, creator_profile) -> dict:
        """
        Generate 10 hook variants via Haiku.
        Returns: {"hooks": List[{"hook_type": str, "content": str}], "cost_usd": float}
        """
        if not self.client:
            logger.warning("[HOOK_GENERATION_SKIPPED] No API key provided")
            return {
                "hooks": [
                    {"hook_type": "curiosity", "content": "Wait until the end..."},
                    {"hook_type": "emotional", "content": "This will change everything..."},
                ],
                "cost_usd": 0.0,
            }

        # Build context
        niche = creator_profile.niche if creator_profile else None
        tone = creator_profile.tone if creator_profile else None
        platform_focus = (
            creator_profile.platform_focus if creator_profile else []
        )
        do_not_use = creator_profile.do_not_use if creator_profile else []

        campaign_brief = f"CTA: {campaign.cta}" if campaign.cta else f"Audience: {campaign.audience}" if campaign.audience else campaign.name
        do_not_use_str = ", ".join(do_not_use) if do_not_use else "none"
        platform_str = ", ".join(platform_focus) if platform_focus else "TikTok, Instagram"

        prompt = f"""Generate exactly 10 viral hook variants for this clip.

Clip: {clip.title}
Campaign: {campaign_brief}
Niche: {niche or 'general'}
Tone: {tone or 'engaging'}
Platforms: {platform_str}
Do NOT use: {do_not_use_str}

Return a JSON array with exactly 10 objects. Each object must have:
- "hook_type": one of ["curiosity", "controversial", "emotional", "authority"]
- "content": the hook text (2-10 words, punchy)

Aim for 2-3 hooks per type. Ensure variety and scroll-stopping power.

Return ONLY the JSON array, no markdown, no explanation."""

        try:
            response = self.client.messages.create(
                model=self.draft_model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = (
                input_tokens * HAIKU_INPUT_COST + output_tokens * HAIKU_OUTPUT_COST
            )

            # Parse hooks
            text = response.content[0].text.strip()
            hooks = json.loads(text)

            # Validate
            if not isinstance(hooks, list) or len(hooks) == 0:
                raise ValueError("Expected non-empty array")

            logger.info(
                f"[HOOK_GENERATED] clip_id={clip.id}, count={len(hooks)}, "
                f"model={self.draft_model}, cost_usd={cost_usd:.6f}"
            )

            return {"hooks": hooks, "cost_usd": cost_usd}

        except json.JSONDecodeError:
            logger.error(f"[HOOK_PARSE_ERROR] clip_id={clip.id}, invalid JSON")
            return {
                "hooks": [
                    {"hook_type": "curiosity", "content": "You won't believe this..."},
                    {"hook_type": "emotional", "content": "This moment changed everything..."},
                ],
                "cost_usd": 0.0,
            }
        except Exception as e:
            logger.error(f"[HOOK_FAILED] clip_id={clip.id}: {e}")
            return {
                "hooks": [
                    {"hook_type": "curiosity", "content": "Wait until the end..."},
                    {"hook_type": "emotional", "content": "Watch to the end..."},
                ],
                "cost_usd": 0.0,
            }

    def polish_winner(self, hook_text: str, hook_type: str, context: dict) -> dict:
        """
        Polish the elected hook variant via Sonnet.
        Returns: {"content": str, "cost_usd": float}
        """
        if not self.client:
            logger.warning("[HOOK_POLISH_SKIPPED] No API key provided")
            return {"content": hook_text, "cost_usd": 0.0}

        niche = context.get("niche")
        brief = context.get("brief", "")

        prompt = f"""Refine this hook for maximum first-3-seconds scroll-stopping impact.

Hook: {hook_text}
Type: {hook_type}
Niche: {niche or 'general'}
Context: {brief}

Rules:
- Keep it 2-10 words maximum
- Make it visceral and immediate
- Zero fluff, pure impact
- Match platform norms (TikTok/Reels speed)

Return ONLY the polished hook text, nothing else."""

        try:
            response = self.client.messages.create(
                model=self.elite_model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = (
                input_tokens * SONNET_INPUT_COST + output_tokens * SONNET_OUTPUT_COST
            )

            polished = response.content[0].text.strip()

            logger.info(
                f"[HOOK_POLISHED] model={self.elite_model}, "
                f"cost_usd={cost_usd:.6f}"
            )

            return {"content": polished, "cost_usd": cost_usd}

        except Exception as e:
            logger.error(f"[HOOK_POLISH_FAILED]: {e}")
            return {"content": hook_text, "cost_usd": 0.0}
