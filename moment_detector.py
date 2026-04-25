"""
Moment Detection
================
Detects viral/interesting moments in videos using heuristic methods.
No ML needed - uses scene change detection and audio analysis.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Moment:
    """A detected moment in a video."""
    start_sec: float
    end_sec: float
    duration: float
    reason: str  # "scene_change", "audio_peak", "cut_heavy"
    score: float  # 0-100, higher = more interesting


class MomentDetector:
    """Detects interesting moments in videos."""

    def __init__(self):
        self.min_moment_duration = 3  # Don't detect moments < 3 seconds apart
        self.max_moment_duration = 60  # Don't look for moments > 60 seconds

    def detect_moments(
        self,
        video_path: str,
        config: Optional[Dict] = None
    ) -> List[Moment]:
        """
        Detect interesting moments in a video.

        Args:
            video_path: Path to .mp4 file
            config: Detection config (optional)
                - scene_change_threshold: 0.0-1.0 (0.3 default)
                - audio_threshold: dB above baseline (8.0 default)
                - min_duration: minimum moment duration (3 default)
                - max_duration: maximum moment duration (60 default)

        Returns:
            List of Moment objects, sorted by start time
        """
        config = config or {}
        scene_threshold = config.get("scene_change_threshold", 0.3)
        audio_threshold = config.get("audio_threshold", 8.0)
        self.min_moment_duration = config.get("min_duration", 3)
        self.max_moment_duration = config.get("max_duration", 60)

        logger.info(f"Detecting moments in: {video_path}")

        try:
            import cv2
        except ImportError:
            logger.error("opencv-python not installed. Install with: pip install opencv-python")
            return []

        video_path = Path(video_path)
        if not video_path.exists():
            logger.error(f"Video not found: {video_path}")
            return []

        moments = []

        try:
            # Open video
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                logger.error(f"Could not open video: {video_path}")
                return []

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            total_duration = total_frames / fps if fps > 0 else 0

            logger.info(f"Video: {total_frames} frames @ {fps} FPS = {total_duration:.1f}s")

            # Detect scene changes
            logger.info("Detecting scene changes...")
            scene_moments = self._detect_scene_changes(
                cap, fps, total_frames, scene_threshold
            )
            logger.info(f"  Found {len(scene_moments)} scene changes")
            moments.extend(scene_moments)

            # Detect audio peaks (requires librosa)
            try:
                logger.info("Detecting audio peaks...")
                audio_moments = self._detect_audio_peaks(
                    str(video_path), fps, audio_threshold
                )
                logger.info(f"  Found {len(audio_moments)} audio peaks")
                moments.extend(audio_moments)
            except ImportError:
                logger.warning("  librosa not installed, skipping audio detection")

            # Sort by start time
            moments.sort(key=lambda m: m.start_sec)

            # Merge overlapping moments
            moments = self._merge_overlapping(moments)

            logger.info(f"Total moments detected: {len(moments)}")
            return moments

        except Exception as e:
            logger.error(f"Moment detection failed: {e}")
            return []
        finally:
            cap.release()

    def _detect_scene_changes(
        self,
        cap,
        fps: float,
        total_frames: int,
        threshold: float = 0.3
    ) -> List[Moment]:
        """
        Detect scene changes using frame histogram differences.

        Args:
            cap: cv2.VideoCapture object
            fps: Frames per second
            total_frames: Total number of frames
            threshold: Histogram difference threshold (0.0-1.0)

        Returns:
            List of Moment objects for detected scene changes
        """
        try:
            import cv2
        except ImportError:
            return []

        moments = []
        frame_skip = max(1, int(fps / 2))  # Process every 2nd frame (0.5s intervals)
        prev_hist = None
        prev_frame_num = 0

        frame_num = 0
        while frame_num < total_frames:
            ret, frame = cap.read()
            if not ret:
                break

            # Resize for faster processing
            frame = cv2.resize(frame, (160, 90))

            # Calculate histogram
            hist = cv2.calcHist(
                [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)],
                [0],
                None,
                [256],
                [0, 256]
            )
            hist = cv2.normalize(hist, hist).flatten()

            # Compare to previous histogram
            if prev_hist is not None:
                diff = cv2.compareHist(
                    prev_hist,
                    hist,
                    cv2.HISTCMP_BHATTACHARYYA
                )

                if diff > threshold:
                    # Scene change detected
                    moment_sec = frame_num / fps
                    moment = Moment(
                        start_sec=max(0, moment_sec - 1),
                        end_sec=min(moment_sec + 3, total_frames / fps),
                        duration=4,
                        reason="scene_change",
                        score=min(100, diff * 100),
                    )
                    moments.append(moment)
                    logger.debug(f"  Scene change at {moment_sec:.1f}s (diff={diff:.3f})")

            prev_hist = hist.copy()
            frame_num += frame_skip

        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to beginning
        return moments

    def _detect_audio_peaks(
        self,
        video_path: str,
        fps: float,
        threshold_db: float = 8.0
    ) -> List[Moment]:
        """
        Detect loud audio segments.

        Args:
            video_path: Path to video file
            fps: Frames per second
            threshold_db: Decibels above baseline

        Returns:
            List of Moment objects for audio peaks
        """
        try:
            import librosa
        except ImportError:
            logger.warning("librosa not installed, skipping audio detection")
            return []

        moments = []

        try:
            # Load audio from video
            logger.debug(f"Loading audio from {video_path}...")
            y, sr = librosa.load(video_path, sr=22050)

            # Calculate RMS energy in 0.5-second windows
            frame_length = int(sr * 0.5)  # 0.5 second window
            hop_length = int(sr * 0.25)  # 0.25 second hop (overlap)

            # Calculate energy
            S = librosa.feature.melspectrogram(y=y, sr=sr)
            energy = librosa.power_to_db(np.mean(S, axis=0))

            # Find peaks
            baseline = np.percentile(energy, 25)  # 25th percentile = baseline
            threshold = baseline + threshold_db

            logger.debug(f"Audio baseline: {baseline:.1f} dB, threshold: {threshold:.1f} dB")

            # Find segments above threshold
            peak_frames = np.where(energy > threshold)[0]

            if len(peak_frames) > 0:
                # Group consecutive peaks
                peak_times = []
                start_frame = peak_frames[0]

                for i in range(1, len(peak_frames)):
                    if peak_frames[i] - peak_frames[i - 1] > 4:  # Gap of >1s
                        end_frame = peak_frames[i - 1]
                        start_sec = (start_frame * hop_length) / sr
                        end_sec = (end_frame * hop_length) / sr

                        if end_sec - start_sec >= self.min_moment_duration:
                            moment = Moment(
                                start_sec=max(0, start_sec - 0.5),
                                end_sec=min(end_sec + 0.5, len(y) / sr),
                                duration=end_sec - start_sec,
                                reason="audio_peak",
                                score=min(
                                    100,
                                    (np.mean(energy[start_frame:end_frame]) - baseline) * 5
                                ),
                            )
                            moments.append(moment)
                            logger.debug(
                                f"  Audio peak at {start_sec:.1f}-{end_sec:.1f}s "
                                f"(score={moment.score:.0f})"
                            )

                        start_frame = peak_frames[i]

            return moments

        except Exception as e:
            logger.warning(f"Audio detection failed: {e}")
            return []

    def _merge_overlapping(self, moments: List[Moment]) -> List[Moment]:
        """
        Merge moments that overlap significantly.

        Args:
            moments: List of Moment objects

        Returns:
            List of merged moments
        """
        if not moments:
            return []

        merged = []
        current = moments[0]

        for moment in moments[1:]:
            # Check for overlap
            if moment.start_sec < current.end_sec:
                # Overlapping - merge
                current = Moment(
                    start_sec=current.start_sec,
                    end_sec=max(current.end_sec, moment.end_sec),
                    duration=max(current.end_sec, moment.end_sec) - current.start_sec,
                    reason=f"{current.reason}+{moment.reason}",
                    score=max(current.score, moment.score),
                )
            else:
                # No overlap - save current and start new
                merged.append(current)
                current = moment

        merged.append(current)
        return merged


def main():
    """Test moment detection."""
    logging.basicConfig(level=logging.INFO)

    # Example: detect moments in a video
    test_video = "data/youtube_sources/sample.mp4"

    if not Path(test_video).exists():
        logger.info(f"Test video not found: {test_video}")
        logger.info("To test, download a video first:")
        logger.info("  from youtube_discovery import YouTubeDiscovery")
        logger.info("  discovery = YouTubeDiscovery()")
        logger.info("  videos = discovery.search_query('funny videos', max_videos=1)")
        logger.info("  discovery.download_videos(videos)")
        return

    detector = MomentDetector()
    moments = detector.detect_moments(test_video)

    logger.info(f"\nDetected {len(moments)} moments:")
    for m in moments:
        logger.info(f"  {m.start_sec:.1f}-{m.end_sec:.1f}s: {m.reason} (score={m.score:.0f})")


if __name__ == "__main__":
    main()
