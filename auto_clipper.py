"""
Auto-Clipper
============
Extracts short-form clips from long-form videos using moments.
Uses ffmpeg for fast, lossless extraction.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
import random

logger = logging.getLogger(__name__)


@dataclass
class ClipSpec:
    """Specification for a clip to extract."""
    source_path: str
    start_sec: float
    end_sec: float
    moment_reason: str
    output_path: str


class AutoClipper:
    """Extracts clips from videos using ffmpeg."""

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("clips/generated")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_clip(
        self,
        source_path: str,
        start_sec: float,
        end_sec: float,
        output_name: Optional[str] = None
    ) -> Optional[Path]:
        """
        Extract a clip from a video using ffmpeg.

        Args:
            source_path: Path to source video
            start_sec: Start time in seconds
            end_sec: End time in seconds
            output_name: Name for output file (auto-generated if None)

        Returns:
            Path to extracted clip, or None if failed
        """
        source_path = Path(source_path)
        if not source_path.exists():
            logger.error(f"Source video not found: {source_path}")
            return None

        duration = end_sec - start_sec
        if duration <= 0:
            logger.error(f"Invalid clip duration: {duration}s")
            return None

        # Generate output name if not provided
        if not output_name:
            output_name = (
                f"{source_path.stem}_"
                f"{int(start_sec)}-{int(end_sec)}_"
                f"{random.randint(1000, 9999)}.mp4"
            )

        output_path = self.output_dir / output_name

        logger.info(
            f"Extracting clip: {source_path.name} "
            f"[{start_sec:.1f}s - {end_sec:.1f}s] ({duration:.1f}s)"
        )

        try:
            # ffmpeg command: extract segment with minimal re-encoding
            # -c copy = copy without re-encoding (fast)
            # -ss input_time = seek to start (efficient)
            # -to end_time = extract up to end (or -t duration)
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-ss",
                str(start_sec),
                "-i",
                str(source_path),
                "-to",
                str(duration),  # Use duration instead of absolute end time
                "-c",
                "copy",  # Copy without re-encoding
                "-loglevel",
                "warning",  # Reduce log noise
                str(output_path),
            ]

            logger.debug(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                logger.error(f"ffmpeg failed: {result.stderr}")
                return None

            if output_path.exists():
                file_size_mb = output_path.stat().st_size / (1024 * 1024)
                logger.info(f"Clip extracted: {output_path.name} ({file_size_mb:.1f}MB)")
                return output_path
            else:
                logger.error("ffmpeg completed but output file not found")
                return None

        except subprocess.TimeoutExpired:
            logger.error("ffmpeg extraction timed out")
            return None
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return None

    def extract_clips_from_moments(
        self,
        source_path: str,
        moments: List,  # List[Moment] from moment_detector.py
        padding_sec: float = 1.0,
        target_duration_sec: Tuple[int, int] = (15, 60)
    ) -> List[Path]:
        """
        Extract multiple clips from detected moments.

        Args:
            source_path: Path to source video
            moments: List of Moment objects from detector
            padding_sec: Seconds to add before/after moment
            target_duration_sec: Target duration range (min, max)

        Returns:
            List of paths to extracted clips
        """
        logger.info(
            f"Extracting {len(moments)} clips from {Path(source_path).name} "
            f"with {padding_sec}s padding, target {target_duration_sec[0]}-{target_duration_sec[1]}s"
        )

        extracted = []
        min_duration, max_duration = target_duration_sec

        for i, moment in enumerate(moments, 1):
            # Calculate ideal window
            ideal_start = max(0, moment.start_sec - padding_sec)
            ideal_end = moment.end_sec + padding_sec
            ideal_duration = ideal_end - ideal_start

            # Adjust to fit target duration
            if ideal_duration < min_duration:
                # Too short - expand
                center = (ideal_start + ideal_end) / 2
                ideal_start = max(0, center - min_duration / 2)
                ideal_end = ideal_start + min_duration
                logger.debug(
                    f"  Clip {i}: Expanded from {ideal_duration:.1f}s "
                    f"to {ideal_end - ideal_start:.1f}s"
                )

            elif ideal_duration > max_duration:
                # Too long - trim around center of moment
                center = (moment.start_sec + moment.end_sec) / 2
                ideal_start = max(0, center - max_duration / 2)
                ideal_end = ideal_start + max_duration
                logger.debug(
                    f"  Clip {i}: Trimmed from {ideal_duration:.1f}s "
                    f"to {ideal_end - ideal_start:.1f}s"
                )

            # Extract
            output_name = (
                f"clip_{i:02d}_{moment.reason}"
                f"_{int(ideal_start)}-{int(ideal_end)}.mp4"
            )

            clip_path = self.extract_clip(
                source_path,
                ideal_start,
                ideal_end,
                output_name
            )

            if clip_path:
                extracted.append(clip_path)
                logger.info(f"  {i}/{len(moments)}: {clip_path.name}")
            else:
                logger.warning(f"  {i}/{len(moments)}: Failed to extract clip")

        logger.info(f"Successfully extracted {len(extracted)}/{len(moments)} clips")
        return extracted

    def validate_clips(self, clip_paths: List[Path]) -> List[Path]:
        """
        Validate extracted clips are valid MP4 files.

        Args:
            clip_paths: List of clip file paths

        Returns:
            List of valid clips (filters out corrupted files)
        """
        valid = []

        for clip_path in clip_paths:
            try:
                # Use ffmpeg to check file validity
                cmd = [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(clip_path),
                    "-f",
                    "null",
                    "-",
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    file_size = clip_path.stat().st_size
                    logger.debug(f"  ✓ {clip_path.name} ({file_size / 1024 / 1024:.1f}MB)")
                    valid.append(clip_path)
                else:
                    logger.warning(f"  ✗ {clip_path.name} - Invalid file")

            except Exception as e:
                logger.warning(f"  ✗ {clip_path.name} - Validation error: {e}")

        logger.info(f"Validated {len(valid)}/{len(clip_paths)} clips")
        return valid


def main():
    """Test auto-clipping."""
    logging.basicConfig(level=logging.INFO)

    # Example: create a test clip
    test_source = "data/youtube_sources/sample.mp4"

    if not Path(test_source).exists():
        logger.info(f"Test video not found: {test_source}")
        logger.info("To test: Download a video first using youtube_discovery.py")
        return

    clipper = AutoClipper()

    # Test extracting a single clip
    logger.info("=== TEST: Extract Single Clip ===")
    clip_path = clipper.extract_clip(
        test_source,
        start_sec=10,  # Start at 10 seconds
        end_sec=25,    # End at 25 seconds (15s duration)
        output_name="test_clip.mp4"
    )

    if clip_path:
        logger.info(f"Success: {clip_path}")

        # Test validation
        logger.info("\n=== TEST: Validate Clip ===")
        valid = clipper.validate_clips([clip_path])
        logger.info(f"Valid clips: {len(valid)}")


if __name__ == "__main__":
    main()
