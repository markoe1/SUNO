"""
PHASE 3, PART 3: Caption Generation and Scheduling
Generates captions using Claude AI and applies platform-specific formatting.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
import anthropic

logger = logging.getLogger(__name__)


class CaptionGenerationError(Exception):
    """Raised when caption generation fails"""
    pass


class CaptionGenerator:
    """Generates captions for clips using Claude AI."""

    def __init__(self, db: Session, anthropic_api_key: str):
        """
        Initialize caption generator.

        Args:
            db: SQLAlchemy session
            anthropic_api_key: API key for Anthropic Claude
        """
        self.db = db
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)

    def generate_caption(
        self,
        clip_id: int,
        assignment_id: int,
        target_platform: str,
        campaign_brief: Optional[str] = None,
        tone: Optional[str] = None,
        style: Optional[str] = None,
    ) -> Dict:
        """
        Generate caption for clip using Claude AI.

        Args:
            clip_id: ID of clip
            assignment_id: ID of clip assignment
            target_platform: Target platform name
            campaign_brief: Campaign brief for context
            tone: Desired tone of caption
            style: Desired style of caption

        Returns:
            Dict with caption, hashtags, and metadata
        """
        from suno.common.models import Clip, Campaign

        try:
            # Get clip and campaign context
            clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
            if not clip:
                raise CaptionGenerationError(f"Clip {clip_id} not found")

            campaign = self.db.query(Campaign).filter(Campaign.id == clip.campaign_id).first()
            if not campaign:
                raise CaptionGenerationError(f"Campaign not found for clip {clip_id}")

            # Build prompt context
            brief = campaign_brief or (f"CTA: {campaign.cta}" if campaign.cta else f"Audience: {campaign.audience}" if campaign.audience else "")
            tone = tone or "engaging"
            style = style or "native"

            prompt = self._build_caption_prompt(
                clip.title,
                clip.description,
                clip.creator,
                clip.source_platform,
                target_platform,
                brief,
                tone,
                style,
                clip.hashtags,
            )

            # Call Claude API
            message = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            response_text = message.content[0].text

            # Parse response
            caption_data = self._parse_caption_response(response_text, target_platform)

            logger.info(f"Generated caption for clip {clip_id} on {target_platform}")
            return {
                "success": True,
                "caption": caption_data["caption"],
                "hashtags": caption_data["hashtags"],
                "character_count": len(caption_data["caption"]),
                "platform": target_platform,
            }

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error for clip {clip_id}: {e}")
            raise CaptionGenerationError(f"Claude API error: {e}")
        except Exception as e:
            logger.error(f"Error generating caption for clip {clip_id}: {e}")
            raise CaptionGenerationError(f"Caption generation failed: {e}")

    def _build_caption_prompt(
        self,
        title: str,
        description: str,
        creator: str,
        source_platform: str,
        target_platform: str,
        brief: str,
        tone: str,
        style: str,
        existing_hashtags: List[str],
    ) -> str:
        """
        Build the prompt for Claude to generate caption.

        Args:
            title: Clip title
            description: Clip description
            creator: Original creator name
            source_platform: Where clip came from
            target_platform: Where clip will be posted
            brief: Campaign brief
            tone: Desired tone
            style: Desired style
            existing_hashtags: Hashtags from source

        Returns:
            Formatted prompt string
        """
        platform_guidelines = self._get_platform_guidelines(target_platform)
        char_limit = self._get_platform_char_limit(target_platform)

        prompt = f"""You are an expert social media content strategist. Generate an engaging caption for a video clip.

SOURCE CLIP INFO:
- Title: {title}
- Description: {description}
- Creator: {creator}
- Original Platform: {source_platform}
- Original Hashtags: {', '.join(existing_hashtags) if existing_hashtags else 'None'}

TARGET PLATFORM: {target_platform}
PLATFORM GUIDELINES: {platform_guidelines}
CHARACTER LIMIT: {char_limit}

CAMPAIGN CONTEXT:
- Brief: {brief if brief else 'No specific brief'}
- Tone: {tone}
- Style: {style}

INSTRUCTIONS:
1. Create a compelling caption that resonates with {target_platform} audiences
2. Keep tone {tone}
3. Stay under {char_limit} characters
4. Generate 3-5 relevant hashtags that are popular on {target_platform}
5. Avoid generic hashtags
6. Make it native to the platform (don't mention other platforms)

RESPONSE FORMAT:
CAPTION:
[Your caption here]

HASHTAGS:
#hashtag1 #hashtag2 #hashtag3 #hashtag4

Focus on authenticity and engagement. Make it feel natural for {target_platform}."""

        return prompt

    def _parse_caption_response(self, response: str, target_platform: str) -> Dict:
        """
        Parse Claude's response into caption and hashtags.

        Args:
            response: Raw response from Claude
            target_platform: Target platform for validation

        Returns:
            Dict with caption and hashtags
        """
        try:
            parts = response.split("HASHTAGS:")
            caption_part = parts[0].replace("CAPTION:", "").strip()
            hashtags_part = parts[1].strip() if len(parts) > 1 else ""

            # Extract hashtags
            hashtags = []
            for token in hashtags_part.split():
                if token.startswith("#"):
                    hashtags.append(token)

            # Enforce platform-specific limits
            char_limit = self._get_platform_char_limit(target_platform)
            if len(caption_part) > char_limit:
                caption_part = caption_part[:char_limit].rsplit(" ", 1)[0] + "..."

            return {
                "caption": caption_part,
                "hashtags": hashtags,
            }
        except Exception as e:
            logger.warning(f"Failed to parse caption response, returning raw: {e}")
            return {
                "caption": response[:300],
                "hashtags": [],
            }

    @staticmethod
    def _get_platform_guidelines(platform: str) -> str:
        """Get platform-specific posting guidelines."""
        guidelines = {
            "tiktok": "Trendy, fast-paced, uses trending sounds and effects. Emoji-friendly. Casual tone.",
            "instagram": "Aesthetic, high-quality visuals. Mix of captions and hashtags. Professional but relatable.",
            "youtube": "Detailed descriptions. SEO-focused. Links and timestamps appreciated.",
            "twitter": "Concise, witty. Conversation-focused. Retweets and quote-tweets common.",
            "threads": "Conversational, long-form allowed. Hashtags less critical.",
            "bluesky": "Authentic, community-focused. Similar to early Twitter. Hashtagging useful.",
            "linkedin": "Professional, thoughtful. Value-focused. Industry insights appreciated.",
        }
        return guidelines.get(platform.lower(), "Engaging and native to the platform.")

    @staticmethod
    def _get_platform_char_limit(platform: str) -> int:
        """Get character limit for platform."""
        limits = {
            "twitter": 280,
            "threads": 500,
            "bluesky": 300,
            "tiktok": 150,
            "instagram": 2200,
            "youtube": 5000,
            "linkedin": 3000,
        }
        return limits.get(platform.lower(), 300)


class SchedulingManager:
    """Manages post scheduling based on tier features and optimization."""

    def __init__(self, db: Session):
        """
        Initialize scheduling manager.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def schedule_post(
        self,
        assignment_id: int,
        optimal_time: Optional[datetime] = None,
        use_tier_scheduling: bool = True,
    ) -> Optional[datetime]:
        """
        Schedule a post for an assignment.

        Args:
            assignment_id: ID of clip assignment
            optimal_time: Optional specific time to schedule
            use_tier_scheduling: Whether to use tier-based optimization

        Returns:
            Scheduled datetime or None if immediate posting

        Raises:
            Exception if assignment not found
        """
        from suno.common.models import ClipAssignment, PostJob, Account
        from suno.common.enums import JobLifecycle

        assignment = self.db.query(ClipAssignment).filter(
            ClipAssignment.id == assignment_id
        ).first()

        if not assignment:
            raise Exception(f"Assignment {assignment_id} not found")

        account = self.db.query(Account).filter(Account.id == assignment.account_id).first()
        if not account or not account.membership:
            raise Exception("Account or membership not found")

        tier = account.membership.tier

        # Determine scheduled time
        if optimal_time:
            scheduled_time = optimal_time
        elif tier and tier.scheduling:
            # Tier supports scheduling - use optimal time
            scheduled_time = self._calculate_optimal_posting_time(
                assignment.target_platform,
                account.membership.user.created_at
            )
        else:
            # No scheduling support - post immediately
            scheduled_time = None

        # Create post job
        try:
            post_job = PostJob(
                clip_id=assignment.clip_id,
                account_id=assignment.account_id,
                target_platform=assignment.target_platform,
                status=JobLifecycle.PENDING,
                scheduled_for=scheduled_time,
            )
            self.db.add(post_job)
            self.db.commit()

            logger.info(f"Scheduled post for assignment {assignment_id} at {scheduled_time}")
            return scheduled_time

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error scheduling post: {e}")
            raise

    @staticmethod
    def _calculate_optimal_posting_time(platform: str, user_created_at: datetime) -> datetime:
        """
        Calculate optimal posting time for platform.

        Uses simplified heuristics:
        - TikTok: Evenings (6-9 PM)
        - Instagram: Lunch time (12-1 PM)
        - YouTube: Evening (7-8 PM)
        - Twitter: Business hours (9 AM - 5 PM)
        - LinkedIn: Business hours (9 AM - 5 PM)

        Args:
            platform: Target platform
            user_created_at: User creation time (for timezone inference)

        Returns:
            Optimal posting datetime
        """
        now = datetime.utcnow()
        platform_times = {
            "tiktok": (18, 21),      # 6-9 PM
            "instagram": (12, 13),   # 12-1 PM
            "youtube": (19, 20),     # 7-8 PM
            "twitter": (10, 17),     # 10 AM - 5 PM
            "threads": (14, 16),     # 2-4 PM
            "bluesky": (14, 16),     # 2-4 PM
            "linkedin": (9, 12),     # 9 AM - 12 PM
        }

        start_hour, end_hour = platform_times.get(platform.lower(), (12, 13))

        # Schedule for tomorrow at mid-range time
        tomorrow = now + timedelta(days=1)
        scheduled = tomorrow.replace(hour=start_hour + (end_hour - start_hour) // 2, minute=0, second=0)

        return scheduled
