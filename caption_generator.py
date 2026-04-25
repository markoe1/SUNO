"""
Caption Generation
==================
Generates viral captions and hashtags for clips using Claude vision API.
Extracts thumbnail from clip and generates context-aware captions.
"""

import logging
import os
import base64
import subprocess
from pathlib import Path
from typing import Tuple, List, Optional, Dict
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class GeneratedCaption:
    """Generated caption and hashtags for a clip."""
    caption: str  # 1-2 sentences, <100 chars
    hashtags: List[str]  # 3-5 hashtags
    moment_type: str  # "scene_change", "audio_peak", etc.
    confidence: float  # 0-1, how confident in the caption


class CaptionGenerator:
    """Generate viral captions for clips using Claude vision API."""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize caption generator.

        Args:
            model: Claude model to use for vision + generation
        """
        self.model = model
        try:
            from anthropic import Anthropic
            self.client = Anthropic()
        except ImportError:
            logger.error("anthropic not installed. Install with: pip install anthropic")
            self.client = None

    def generate(\
        self,
        clip_path: str,
        source_title: str,
        moment_type: str,
        creator_preferences: Optional[Dict] = None
    ) -> Optional[GeneratedCaption]:
        """
        Generate caption and hashtags for a clip.

        Args:
            clip_path: Path to clip file (.mp4)
            source_title: Original video/content title
            moment_type: Type of moment ("scene_change", "audio_peak", etc.)
            creator_preferences: Creator content rules/style (optional)

        Returns:
            GeneratedCaption object, or None if failed
        """
        if not self.client:
            logger.error("Claude client not initialized")
            return None

        clip_path = Path(clip_path)
        if not clip_path.exists():
            logger.error(f"Clip not found: {clip_path}")
            return None

        logger.info(f"Generating caption for: {clip_path.name}")

        # Extract thumbnail from clip
        thumbnail_b64 = self._extract_thumbnail(str(clip_path))
        if not thumbnail_b64:
            logger.warning("Could not extract thumbnail, generating caption without image")
            # Fall back to text-only generation
            return self._generate_text_only(source_title, moment_type, creator_preferences)

        # Generate caption using vision + context
        caption_data = self._generate_with_vision(
            thumbnail_b64,
            source_title,
            moment_type,
            creator_preferences
        )

        if caption_data:
            return caption_data
        else:
            logger.warning("Vision-based generation failed, falling back to text-only")
            return self._generate_text_only(source_title, moment_type, creator_preferences)

    def _extract_thumbnail(\
        self,
        clip_path: str,
        timestamp: float = 0.5
    ) -> Optional[str]:
        """
        Extract thumbnail from clip at timestamp.

        Args:
            clip_path: Path to clip
            timestamp: Seconds into clip (0.5 = middle 50%)

        Returns:
            Base64-encoded JPEG image, or None if failed
        """
        try:
            # Get clip duration first
            cmd_duration = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1:noval=0",
                clip_path
            ]

            result = subprocess.run(
                cmd_duration,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.warning(f"Could not get clip duration: {result.stderr}")
                duration = None
            else:
                try:
                    duration = float(result.stdout.strip())
                except ValueError:
                    duration = None

            # Use 1/3 into clip or explicit timestamp
            if duration and duration > 0:
                frame_time = min(duration * timestamp, duration - 0.1)
            else:
                frame_time = 0.5

            # Extract frame as JPEG
            output_file = Path(clip_path).parent / "thumbnail.jpg"

            cmd_extract = [
                "ffmpeg",
                "-y",
                "-ss", str(frame_time),
                "-i", clip_path,
                "-vframes", "1",
                "-q:v", "2",  # High quality JPEG
                str(output_file)
            ]

            result = subprocess.run(
                cmd_extract,
                capture_output=True,
                timeout=10
            )

            if result.returncode != 0 or not output_file.exists():
                logger.warning(f"ffmpeg thumbnail extraction failed")
                return None

            # Read and encode to base64
            with open(output_file, "rb") as f:
                thumbnail_data = f.read()

            output_file.unlink()  # Clean up temp file

            b64 = base64.standard_b64encode(thumbnail_data).decode("utf-8")
            logger.debug(f"Extracted thumbnail: {len(thumbnail_data)} bytes")
            return b64

        except subprocess.TimeoutExpired:
            logger.warning("Thumbnail extraction timed out")
            return None
        except Exception as e:
            logger.warning(f"Thumbnail extraction failed: {e}")
            return None

    def _generate_with_vision(\
        self,
        thumbnail_b64: str,
        source_title: str,
        moment_type: str,
        creator_preferences: Optional[Dict] = None
    ) -> Optional[GeneratedCaption]:
        """
        Generate caption using Claude vision + context.

        Args:
            thumbnail_b64: Base64-encoded thumbnail JPEG
            source_title: Original content title
            moment_type: Type of moment
            creator_preferences: Creator rules (optional)

        Returns:
            GeneratedCaption or None
        """
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt(creator_preferences)

            # Build user prompt
            user_text = f"""Analyze this clip thumbnail and generate a viral TikTok/Instagram caption.

Original content: {source_title}
Moment type: {moment_type}

Requirements:
- Caption: 1-2 sentences, max 100 characters
- Start with a viral hook (e.g., "POV:", "Wait for it...", "Tell me I'm wrong...", "The way this...")
- 3-5 relevant hashtags
- Make it engaging and shareable

Format your response as JSON:
{{
    "caption": "Your viral caption here",
    "hashtags": ["#tag1", "#tag2", "#tag3"]
}}"""

            # Call Claude with vision
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": thumbnail_b64
                                }
                            },
                            {
                                "type": "text",
                                "text": user_text
                            }
                        ]
                    }
                ]
            )

            # Parse response
            response_text = response.content[0].text

            try:
                # Try to extract JSON
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    data = json.loads(json_str)
                else:
                    logger.warning("No JSON found in response, using raw text")
                    # Fall back to parsing text
                    return self._parse_caption_text(response_text, moment_type)

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                return self._parse_caption_text(response_text, moment_type)

            caption = data.get("caption", "").strip()
            hashtags = data.get("hashtags", [])

            if not caption or len(caption) > 100:
                logger.warning(f"Invalid caption: length={len(caption) if caption else 0}")
                return self._parse_caption_text(response_text, moment_type)

            logger.info(f"Generated caption: {caption}")
            return GeneratedCaption(
                caption=caption,
                hashtags=hashtags[:5],  # Limit to 5
                moment_type=moment_type,
                confidence=0.9
            )

        except Exception as e:
            logger.error(f"Vision-based generation failed: {e}")
            return None

    def _generate_text_only(\
        self,
        source_title: str,
        moment_type: str,
        creator_preferences: Optional[Dict] = None
    ) -> Optional[GeneratedCaption]:
        """
        Generate caption using text-only (no vision).

        Args:
            source_title: Original content title
            moment_type: Type of moment
            creator_preferences: Creator rules (optional)

        Returns:
            GeneratedCaption or None
        """
        if not self.client:
            return None

        try:
            system_prompt = self._build_system_prompt(creator_preferences)

            user_text = f"""Generate a viral TikTok/Instagram caption for this moment.

Source: {source_title}
Moment type: {moment_type}

Requirements:
- Caption: 1-2 sentences, max 100 characters
- Use a viral hook
- 3-5 hashtags
- No hashtags in caption (separate them)

Format as JSON:
{{
    "caption": "Your caption",
    "hashtags": ["#tag1", "#tag2", "#tag3"]
}}"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_text
                    }
                ]
            )

            response_text = response.content[0].text

            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                return self._parse_caption_text(response_text, moment_type)

            caption = data.get("caption", "").strip()
            hashtags = data.get("hashtags", [])

            if not caption or len(caption) > 100:
                logger.warning(f"Invalid caption length: {len(caption) if caption else 0}")
                return self._parse_caption_text(response_text, moment_type)

            logger.info(f"Generated text-only caption: {caption}")
            return GeneratedCaption(
                caption=caption,
                hashtags=hashtags[:5],
                moment_type=moment_type,
                confidence=0.7  # Lower confidence for text-only
            )

        except Exception as e:
            logger.error(f"Text-only generation failed: {e}")
            return None

    def _parse_caption_text(\
        self,
        text: str,
        moment_type: str
    ) -> Optional[GeneratedCaption]:
        """
        Fallback: parse caption from plain text response.

        Args:
            text: Response text from Claude
            moment_type: Type of moment

        Returns:
            GeneratedCaption or None
        """
        try:
            lines = text.strip().split("\n")

            # Find caption (first non-empty line that's not a hashtag)
            caption = None
            hashtags = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("#"):
                    hashtags.append(line)
                elif caption is None and len(line) < 100:
                    caption = line
                elif caption and line.startswith("#"):
                    hashtags.append(line)

            if caption and len(caption) <= 100:
                logger.info(f"Parsed caption from text: {caption}")
                return GeneratedCaption(
                    caption=caption,
                    hashtags=hashtags[:5],
                    moment_type=moment_type,
                    confidence=0.5
                )

        except Exception as e:
            logger.debug(f"Failed to parse caption text: {e}")

        return None

    def _build_system_prompt(self, creator_preferences: Optional[Dict] = None) -> str:
        """
        Build system prompt based on creator preferences.

        Args:
            creator_preferences: Optional creator rules

        Returns:
            System prompt string
        """
        base_prompt = (
            "You are a viral TikTok/Instagram caption expert. "
            "Generate engaging, concise captions that hook viewers immediately. "
            "Use proven hooks like 'POV:', 'Wait for it...', 'Tell me I'm wrong...', etc. "
            "Be authentic, not clickbaity. "
            "Keep captions under 100 characters. "
            "Always provide hashtags separately."
        )

        if creator_preferences:
            # Add creator-specific rules
            if style := creator_preferences.get("style"):
                base_prompt += f"\nCreator style: {style}"

            if tone := creator_preferences.get("tone"):
                base_prompt += f"\nTone: {tone}"

            if excluded_topics := creator_preferences.get("excluded_topics"):
                base_prompt += f"\nAvoid: {', '.join(excluded_topics)}"

        return base_prompt


def main():
    """Test caption generation."""
    logging.basicConfig(level=logging.INFO)

    # Example: generate caption for test clip
    test_clip = "clips/generated/test_clip.mp4"

    if not Path(test_clip).exists():
        logger.info(f"Test clip not found: {test_clip}")
        logger.info("To test: First extract a clip using auto_clipper.py")
        return

    generator = CaptionGenerator()

    # Test with vision
    logger.info("=== TEST: Generate Caption with Vision ===")
    caption = generator.generate(
        clip_path=test_clip,
        source_title="Crazy viral moment compilation",
        moment_type="scene_change",
        creator_preferences={
            "style": "humorous, relatable",
            "tone": "casual, energetic",
            "excluded_topics": ["politics", "violence"]
        }
    )

    if caption:
        logger.info(f"Caption: {caption.caption}")
        logger.info(f"Hashtags: {' '.join(caption.hashtags)}")
        logger.info(f"Confidence: {caption.confidence:.1%}")
    else:
        logger.warning("Failed to generate caption")


if __name__ == "__main__":
    main()
