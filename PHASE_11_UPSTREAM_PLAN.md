# SUNO Clips Upstream Pipeline — Implementation Plan

**Goal:** Autonomous Discovery → Clipping → Caption → Queue → Post → Track

**Current State:**
- ✅ Downstream complete (queue, posting, earnings)
- 🔴 Upstream missing (discovery, moment detection, clipping, captions)

**Do NOT touch:** queue_manager.py, platform_poster.py, daemon.py, quality_monitor.py

**Build in:** clip_pipeline.py (extend), new modules for each phase

---

## Phase 1: YouTube Content Discovery

**Module:** `youtube_discovery.py`

**Input:**
- Channel URL or search query
- Preferences (min duration, content type, etc.)

**Output:**
- List of video URLs + metadata (title, duration, upload_date)

**Implementation:**
```python
class YouTubeDiscovery:
    def search_channels(query: str, max_results: int = 5) -> List[Channel]:
        # Use pytube or yt-dlp to find relevant videos

    def get_videos(channel_url: str, max_videos: int = 10) -> List[Video]:
        # Get recent videos from channel
        # Return: [{"url": "...", "title": "...", "duration": 600, ...}]
```

**Dependencies:** pytube or yt-dlp

---

## Phase 2: Moment Detection

**Module:** `moment_detector.py`

**Input:**
- Video file (local .mp4)
- Thresholds (scene change sensitivity, audio peak threshold, etc.)

**Output:**
- List of (start_sec, end_sec, score, reason) tuples
- Reason: "scene_change", "audio_peak", "text_overlay", "cut_heavy"

**Implementation (Heuristic First):**
```python
class MomentDetector:
    def detect_moments(video_path: str, config: dict) -> List[Moment]:
        # 1. Load video with OpenCV
        # 2. Scene change detection (histogram diff between frames)
        # 3. Audio peak detection (librosa for loud segments)
        # 4. Combine into moments
        # 5. Filter for length + score
```

**Heuristics (No ML needed first):**
- Scene changes: Frame histogram difference > threshold
- Audio peaks: RMS amplitude > baseline + margin
- Cut-heavy: Frames where edge density spikes

**Dependencies:** opencv-python, librosa, numpy

---

## Phase 3: Auto-Clipping

**Module:** `auto_clipper.py`

**Input:**
- Video path
- List of (start, end, reason) moments
- Target duration (15-60s)
- Padding (0.5-2s before/after moment)

**Output:**
- List of .mp4 files extracted to clips/generated/

**Implementation:**
```python
class AutoClipper:
    def extract_clips(
        source_video: str,
        moments: List[Moment],
        target_duration: Tuple[int, int] = (15, 60),
        padding_sec: float = 1.0
    ) -> List[str]:
        # For each moment:
        # 1. Calculate ideal clip window (moment + padding)
        # 2. Adjust to fit target_duration
        # 3. ffmpeg extract segment
        # 4. Return list of clip paths
```

**ffmpeg command:**
```bash
ffmpeg -i input.mp4 -ss {start} -to {end} -c copy output.mp4
```

**Dependencies:** ffmpeg (system), subprocess

---

## Phase 4: Caption Generation

**Module:** `caption_generator.py`

**Input:**
- Clip file (or thumbnail frame)
- Original video title/description
- Moment type (scene_change, audio_peak, text_overlay, etc.)

**Output:**
- Caption string (1-2 sentences, max 100 chars)
- Hashtags (3-5)

**Implementation:**
```python
class CaptionGenerator:
    def generate(
        clip_path: str,
        source_title: str,
        moment_type: str,
        preferences: dict  # creator content rules
    ) -> Tuple[str, List[str]]:
        # 1. Extract thumbnail from clip
        # 2. Describe via Claude vision + context
        # 3. Generate viral hooks (Wait for it..., etc.)
        # 4. Add platform-specific hashtags
```

**Claude Integration:**
```python
client = Anthropic()
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=100,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64_thumbnail
                    }
                },
                {
                    "type": "text",
                    "text": "Create a 1-sentence viral TikTok caption for this moment. Format: Caption | #hashtag1 #hashtag2"
                }
            ]
        }
    ]
)
```

**Dependencies:** anthropic, opencv (for thumbnail extraction)

---

## Phase 5: Integration into clip_pipeline.py

**Extend ClipPipeline class:**

```python
class ClipPipeline:
    # EXISTING
    def discover_clips(self) -> List[Path]
    def ingest_clip(self, clip_path: Path) -> int

    # NEW: Full autonomous flow
    async def discover_and_generate_clips(
        self,
        source_type: str = "youtube",  # "youtube", "tiktok", etc.
        query: str = None,
        channel_url: str = None,
        max_videos: int = 5,
        moments_per_video: int = 3
    ) -> Dict:
        """
        Full pipeline: discover → clip → caption → queue

        Returns: {
            'videos_processed': 5,
            'moments_detected': 15,
            'clips_generated': 15,
            'clips_queued': 15,
            'failed': 0,
            'total_duration_queued': 300  # seconds
        }
        """
        # 1. Discover sources (YouTube)
        # 2. Download videos locally
        # 3. Detect moments
        # 4. Extract clips
        # 5. Generate captions
        # 6. Ingest into queue
```

---

## Phase 6: Testing & Validation

**Test script:** `test_upstream_pipeline.py`

```python
async def test_full_pipeline():
    pipeline = ClipPipeline()

    # Test end-to-end
    result = await pipeline.discover_and_generate_clips(
        source_type="youtube",
        channel_url="https://www.youtube.com/@example",
        max_videos=2,
        moments_per_video=2
    )

    # Verify:
    # 1. Videos downloaded
    # 2. Moments detected
    # 3. Clips extracted (valid .mp4)
    # 4. Captions generated (non-empty)
    # 5. Queue entries created (check DB)
    # 6. Clips pass quality gate
    # 7. Ready for posting
```

---

## Implementation Order

1. **youtube_discovery.py** — Find + download videos (yt-dlp wrapper)
2. **moment_detector.py** — Heuristic scene/audio detection
3. **auto_clipper.py** — ffmpeg extraction
4. **caption_generator.py** — Claude vision + caption generation
5. **Extend clip_pipeline.py** — Wire all together
6. **test_upstream_pipeline.py** — End-to-end validation

---

## Dependencies to Add

```
yt-dlp>=2024.01.01          # YouTube download
opencv-python>=4.8.0        # Video analysis
librosa>=0.10.0             # Audio analysis
numpy>=1.24.0               # Array operations
anthropic>=0.7.0            # Claude API (already have)
```

Update requirements.txt:
```bash
pip install yt-dlp opencv-python librosa numpy anthropic
```

---

## Architecture Diagram

```
YouTube/TikTok Sources
         ↓
[YouTube Discovery] (yt-dlp)
         ↓ (video files)
[Moment Detection] (OpenCV + librosa heuristics)
         ↓ (timecode ranges)
[Auto-Clipping] (ffmpeg)
         ↓ (15-60s .mp4 clips)
[Caption Generation] (Claude vision)
         ↓ (clip + caption + hashtags)
[Queue Ingestion] (existing queue_manager)
         ↓ (Clip objects in DB)
[Quality Gate] (existing quality_monitor)
         ↓ (score ≥70)
[Campaign Validation] (existing campaign_validator)
         ↓ (matches creator rules)
[Parallel Posting] (existing platform_poster)
         ↓ (TikTok, Instagram, YouTube)
[Whop Submission + Earnings] (existing daemon)
         ↓
DONE - Autonomous end-to-end
```

---

## Success Criteria

- [ ] YouTube discovery finds and downloads videos
- [ ] Moment detector identifies 3-5 moments per video (no ML needed)
- [ ] Auto-clipper extracts valid 15-60s .mp4 files
- [ ] Caption generator produces human-readable captions
- [ ] Generated clips feed into existing queue without modification
- [ ] Existing quality gate approves ≥70% of generated clips
- [ ] End-to-end pipeline runs in < 5 min per source video
- [ ] Clips post successfully to all platforms
- [ ] Earnings tracked correctly

---

## Next: Build youtube_discovery.py
