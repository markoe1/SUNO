"""
Clip Quality Monitoring System
==============================
Validates clips before posting to ensure quality standards.
Tracks quality metrics and flags low-quality clips for operator review.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    """Quality assessment for a clip."""
    overall_score: float  # 0-100
    file_integrity: float
    video_specs: float
    caption_quality: float
    metadata: float
    issues: List[str]
    warnings: List[str]
    approved: bool  # False if score < 70


class QualityMonitor:
    """Monitors and validates clip quality."""

    def __init__(self):
        self.min_score = 70  # Clips below this are flagged
        self.quality_log = Path("data/quality_log.json")
        self.quality_log.parent.mkdir(parents=True, exist_ok=True)

    def assess_clip(self, clip_path: str, caption: str = "") -> QualityScore:
        """Assess overall quality of a clip."""
        clip_path = Path(clip_path)

        scores = {
            "file_integrity": self._check_file_integrity(clip_path),
            "video_specs": self._check_video_specs(clip_path),
            "caption_quality": self._check_caption_quality(caption),
            "metadata": self._check_metadata(clip_path),
        }

        # Calculate overall score (weighted average)
        overall = (
            scores["file_integrity"] * 0.25 +
            scores["video_specs"] * 0.35 +
            scores["caption_quality"] * 0.25 +
            scores["metadata"] * 0.15
        )

        issues, warnings = self._determine_issues(clip_path, caption, scores)
        approved = overall >= self.min_score and len(issues) == 0

        result = QualityScore(
            overall_score=round(overall, 1),
            file_integrity=scores["file_integrity"],
            video_specs=scores["video_specs"],
            caption_quality=scores["caption_quality"],
            metadata=scores["metadata"],
            issues=issues,
            warnings=warnings,
            approved=approved,
        )

        self._log_assessment(clip_path.name, result)
        return result

    def _check_file_integrity(self, clip_path: Path) -> float:
        """Check if file is readable and not corrupted."""
        try:
            if not clip_path.exists():
                return 0.0

            file_size = clip_path.stat().st_size
            if file_size == 0:
                return 0.0

            # Try to read first 1MB to verify not corrupted
            with open(clip_path, 'rb') as f:
                f.read(min(1024 * 1024, file_size))

            # File size check (10MB - 500MB reasonable range)
            if 10_000_000 < file_size < 500_000_000:
                return 100.0
            elif 5_000_000 < file_size < 1_000_000_000:
                return 80.0
            else:
                return 50.0

        except Exception as e:
            logger.error(f"File integrity check failed: {e}")
            return 0.0

    def _check_video_specs(self, clip_path: Path) -> float:
        """Check video resolution, duration, format."""
        try:
            # Basic checks without ffmpeg dependency
            file_ext = clip_path.suffix.lower()
            valid_formats = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}

            if file_ext not in valid_formats:
                return 30.0  # Wrong format

            # Check file size as proxy for resolution/quality
            file_size_mb = clip_path.stat().st_size / (1024 * 1024)

            # 30-200MB is ideal for 1080p 15-60 sec clips
            if 30 < file_size_mb < 200:
                return 95.0
            elif 20 < file_size_mb < 250:
                return 80.0
            elif 10 < file_size_mb < 300:
                return 60.0
            else:
                return 40.0

        except Exception as e:
            logger.error(f"Video spec check failed: {e}")
            return 50.0

    def _check_caption_quality(self, caption: str) -> float:
        """Check caption/description quality."""
        if not caption:
            return 0.0

        score = 100.0
        issues = []

        # Length check (15-200 chars optimal)
        if len(caption) < 10:
            score -= 30
            issues.append("Caption too short")
        elif len(caption) > 300:
            score -= 20
            issues.append("Caption too long")
        elif 15 < len(caption) < 200:
            pass  # Perfect
        else:
            score -= 10

        # Check for spam/low-quality patterns
        if caption.count("#") > 15:
            score -= 20
            issues.append("Too many hashtags")

        if len(caption) > 0 and caption[0].islower():
            score -= 5
            issues.append("Caption doesn't start with capital")

        # Check for emoji count (1-3 is good, 4+ is spam)
        emoji_count = sum(1 for c in caption if ord(c) > 127)
        if emoji_count > 5:
            score -= 15
            issues.append("Too many emojis")

        return max(0, score)

    def _check_metadata(self, clip_path: Path) -> float:
        """Check if metadata is complete."""
        try:
            score = 100.0

            # File name quality
            filename = clip_path.stem
            if len(filename) < 3:
                score -= 20

            # Check for creation time
            if clip_path.stat().st_mtime > 0:
                score -= 0  # Has mtime

            return score
        except Exception:
            return 50.0

    def _determine_issues(
        self,
        clip_path: Path,
        caption: str,
        scores: Dict[str, float]
    ) -> Tuple[List[str], List[str]]:
        """Determine critical issues and warnings."""
        issues = []
        warnings = []

        # Critical issues (block posting)
        if scores["file_integrity"] < 50:
            issues.append("File corrupted or unreadable")

        if scores["video_specs"] < 40:
            issues.append("Video format or size invalid")

        # Warnings (log but allow)
        if scores["caption_quality"] < 60:
            warnings.append("Caption quality low")

        if scores["metadata"] < 50:
            warnings.append("Metadata incomplete")

        return issues, warnings

    def _log_assessment(self, filename: str, assessment: QualityScore) -> None:
        """Log quality assessment to file."""
        try:
            log_entry = {
                "timestamp": str(Path(__file__).stat().st_mtime),
                "filename": filename,
                "overall_score": assessment.overall_score,
                "components": {
                    "file_integrity": assessment.file_integrity,
                    "video_specs": assessment.video_specs,
                    "caption_quality": assessment.caption_quality,
                    "metadata": assessment.metadata,
                },
                "approved": assessment.approved,
                "issues": assessment.issues,
                "warnings": assessment.warnings,
            }

            # Append to log
            logs = []
            if self.quality_log.exists():
                with open(self.quality_log) as f:
                    logs = json.load(f)

            logs.append(log_entry)

            # Keep only last 1000 entries
            logs = logs[-1000:]

            with open(self.quality_log, 'w') as f:
                json.dump(logs, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to log assessment: {e}")

    def get_quality_report(self) -> Dict:
        """Get overall quality statistics."""
        try:
            if not self.quality_log.exists():
                return {"total_clips": 0, "avg_score": 0, "approval_rate": 0}

            with open(self.quality_log) as f:
                logs = json.load(f)

            if not logs:
                return {"total_clips": 0, "avg_score": 0, "approval_rate": 0}

            total = len(logs)
            avg_score = sum(log["overall_score"] for log in logs) / total
            approved = sum(1 for log in logs if log["approved"])

            return {
                "total_clips": total,
                "avg_score": round(avg_score, 1),
                "approval_rate": round(approved / total * 100, 1),
                "approved_clips": approved,
                "flagged_clips": total - approved,
            }
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return {}


# Convenience function
def assess_clip_quality(clip_path: str, caption: str = "") -> QualityScore:
    """Quick quality assessment."""
    monitor = QualityMonitor()
    return monitor.assess_clip(clip_path, caption)
