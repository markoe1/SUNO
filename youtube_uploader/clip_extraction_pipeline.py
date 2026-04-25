#!/usr/bin/env python3
"""
SUNO Clip Extraction Pipeline
YouTube → Viral Clips (ready for TikTok, Instagram, YouTube Shorts)

Usage:
    python clip_extraction_pipeline.py <YOUTUBE_URL> [--num-clips 10]

Example:
    python clip_extraction_pipeline.py https://www.youtube.com/watch?v=dQw4w9WgXcQ --num-clips 15
"""

import os
import sys
import json
import subprocess
import tempfile
import re
from pathlib import Path
from datetime import timedelta
import argparse

try:
    import yt_dlp
    from pydub import AudioSegment
    from anthropic import Anthropic
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Install with: pip install yt-dlp openai-whisper pydub anthropic")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

CLIPS_DIR = Path("clips")
TEMP_DIR = Path(tempfile.gettempdir()) / "suno_clips"
OUTPUT_FORMAT = "9:16"  # Vertical (9:16 aspect ratio)
CLIP_DURATION_MIN = 15  # seconds
CLIP_DURATION_MAX = 45  # seconds
CLIP_RESOLUTION = (1080, 1920)  # 9:16 vertical

# ═══════════════════════════════════════════════════════════════
# STEP 1: DOWNLOAD VIDEO
# ═══════════════════════════════════════════════════════════════

def download_youtube_video(url: str) -> str:
    """Download YouTube video and return path."""
    TEMP_DIR.mkdir(exist_ok=True)
    output_path = TEMP_DIR / "%(title)s.%(ext)s"

    print(f"[INFO] Downloading video from: {url}")

    ydl_opts = {
        'format': 'best[ext=mp4]',
        'outtmpl': str(output_path),
        'quiet': False,
        'no_warnings': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
            print(f"[OK] Downloaded: {video_path}")
            return video_path
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# STEP 2: EXTRACT AUDIO & TRANSCRIBE
# ═══════════════════════════════════════════════════════════════

def extract_audio(video_path: str) -> str:
    """Extract audio from video using ffmpeg."""
    audio_path = str(TEMP_DIR / "audio.m4a")

    print(f"[INFO] Extracting audio...")
    cmd = [
        "ffmpeg", "-i", video_path, "-q:a", "9", "-n",
        "-vn", audio_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"[OK] Audio extracted: {audio_path}")
        return audio_path
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Audio extraction failed: {e}")
        sys.exit(1)

def transcribe_audio_with_whisper(audio_path: str) -> dict:
    """Transcribe audio using local Whisper model."""
    print(f"[INFO] Transcribing audio (this may take a minute)...")

    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, language="en")
        print(f"[OK] Transcription complete ({len(result['segments'])} segments)")
        return result
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# STEP 3: IDENTIFY VIRAL MOMENTS USING CLAUDE
# ═══════════════════════════════════════════════════════════════

def identify_viral_segments(transcript_data: dict, num_clips: int = 10) -> list:
    """Use Claude to identify high-engagement segments."""

    # Prepare transcript text
    segments = transcript_data.get('segments', [])
    transcript_text = "\n".join([
        f"[{s['start']:.1f}s-{s['end']:.1f}s] {s['text']}"
        for s in segments
    ])

    print(f"[INFO] Analyzing for viral moments with Claude...")

    client = Anthropic()

    prompt = f"""Analyze this transcript and identify the {num_clips} most viral, engaging segments.

CRITERIA FOR HIGH ENGAGEMENT:
- Sudden tone shifts (boring→exciting, serious→funny)
- Emotion keywords (surprising, shocking, inspiring, hilarious)
- Short impactful sentences
- Controversial statements
- Personal stories or relatable moments
- Actionable advice or "aha moments"
- Unexpected plot twists
- Strong opinions
- Moments that make people want to share

TRANSCRIPT:
{transcript_text}

OUTPUT FORMAT (JSON ARRAY):
[
  {{"start": 12.5, "end": 28.3, "reason": "sudden excitement shift - shock value"}},
  {{"start": 45.0, "end": 62.1, "reason": "relatable personal story - high engagement"}},
  ...
]

IMPORTANT:
- Only include segments that are 15-45 seconds long
- Prioritize the most viral-worthy moments
- Return ONLY the JSON array, no other text
"""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse JSON response
        response_text = response.content[0].text.strip()

        # Try to extract JSON from response
        try:
            segments_list = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                segments_list = json.loads(json_match.group(1))
            else:
                segments_list = json.loads(response_text)

        print(f"[OK] Identified {len(segments_list)} viral segments")
        return segments_list

    except Exception as e:
        print(f"[ERROR] Claude analysis failed: {e}")
        sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# STEP 4: GENERATE CLIPS WITH CAPTIONS
# ═══════════════════════════════════════════════════════════════

def get_segment_text(transcript_data: dict, start: float, end: float) -> str:
    """Extract transcript text for a specific time range."""
    segments = transcript_data.get('segments', [])
    text_parts = []

    for seg in segments:
        if seg['end'] > start and seg['start'] < end:
            text_parts.append(seg['text'].strip())

    return " ".join(text_parts)

def generate_clip_with_captions(
    video_path: str,
    transcript_data: dict,
    start: float,
    end: float,
    clip_num: int,
    output_path: str
) -> bool:
    """Generate a vertical clip (9:16) with burned-in captions."""

    duration = end - start
    segment_text = get_segment_text(transcript_data, start, end)

    # Build ffmpeg command
    # 1. Trim video
    # 2. Scale to 9:16 vertical (pad if needed)
    # 3. Add captions with drawtext

    # Get input video resolution first
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        video_path
    ]

    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split('x'))
    except:
        width, height = 1920, 1080  # Default fallback

    print(f"[INFO] [{clip_num}] Generating clip: {start:.1f}s-{end:.1f}s ({duration:.1f}s)")

    # Complex filter: trim, scale to 9:16, add captions
    # For vertical (9:16): width=1080, height=1920
    scale_filter = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"

    # Prepare caption text (wrap long text)
    caption_text = segment_text[:150] if len(segment_text) > 150 else segment_text
    caption_text_escaped = caption_text.replace("'", "\\'").replace(":", "\\:")

    drawtext_filter = (
        f"drawtext=fontsize=36:fontcolor=white:"
        f"font='C\\:/Windows/Fonts/arial.ttf':"
        f"text='{caption_text_escaped}':"
        f"borderw=2:bordercolor=black:"
        f"x=(w-text_w)/2:y=h-100"
    )

    filter_complex = f"[0:v]trim=start={start}:end={end},{scale_filter},{drawtext_filter}[v]"

    cmd = [
        "ffmpeg", "-i", video_path,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a",
        "-af", f"atrim=start={start}:end={end}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac",
        "-y", output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=60)
        print(f"[OK] Clip {clip_num} saved: {output_path}")
        return True
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Clip {clip_num} generation timed out")
        return False
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Clip {clip_num} generation failed: {e.stderr.decode()}")
        return False

# ═══════════════════════════════════════════════════════════════
# STEP 5: GENERATE ALL CLIPS
# ═══════════════════════════════════════════════════════════════

def generate_all_clips(
    video_path: str,
    transcript_data: dict,
    segments: list,
    output_dir: Path
) -> list:
    """Generate all clips and return list of successful outputs."""

    output_dir.mkdir(exist_ok=True)
    generated_clips = []

    for i, seg in enumerate(segments, 1):
        start = seg['start']
        end = seg['end']
        reason = seg.get('reason', 'viral moment')

        clip_filename = f"clip_{i:03d}.mp4"
        clip_path = output_dir / clip_filename

        success = generate_clip_with_captions(
            video_path, transcript_data,
            start, end, i, str(clip_path)
        )

        if success:
            generated_clips.append({
                'filename': clip_filename,
                'path': str(clip_path),
                'start': start,
                'end': end,
                'duration': end - start,
                'reason': reason
            })
            print(f"[PROGRESS] {i}/{len(segments)} clips")

    return generated_clips

# ═══════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Extract viral clips from YouTube video"
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--num-clips", type=int, default=10, help="Number of clips to extract (default: 10)")
    parser.add_argument("--output-dir", default="clips", help="Output directory (default: clips)")

    args = parser.parse_args()

    print("\n" + "="*60)
    print("SUNO CLIP EXTRACTION PIPELINE")
    print("="*60 + "\n")

    # Setup
    CLIPS_DIR_PATH = Path(args.output_dir)
    CLIPS_DIR_PATH.mkdir(exist_ok=True)

    try:
        # Step 1: Download
        video_path = download_youtube_video(args.url)

        # Step 2: Extract audio & transcribe
        audio_path = extract_audio(video_path)
        transcript_data = transcribe_audio_with_whisper(audio_path)

        # Step 3: Identify viral moments
        segments = identify_viral_segments(transcript_data, args.num_clips)

        if not segments:
            print("[ERROR] No segments identified")
            sys.exit(1)

        # Step 4: Generate clips
        print(f"\n[INFO] Generating {len(segments)} clips...\n")
        generated = generate_all_clips(video_path, transcript_data, segments, CLIPS_DIR_PATH)

        # Summary
        print("\n" + "="*60)
        print("PIPELINE COMPLETE")
        print("="*60)
        print(f"[OK] Generated {len(generated)} clips")
        print(f"[OK] Location: {CLIPS_DIR_PATH.absolute()}")

        for clip in generated:
            print(f"  • {clip['filename']} ({clip['duration']:.1f}s) - {clip['reason']}")

        print(f"\n[NEXT] Run: python batch_upload.py")
        print("="*60 + "\n")

        return 0

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
