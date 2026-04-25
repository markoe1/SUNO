# Clipping Pipeline Setup

## Prerequisites

### 1. FFmpeg (Required for video processing)

**Status**: Not installed

**Windows Installation Options:**

**Option A: Download + Add to PATH (Simplest)**
1. Download: https://ffmpeg.org/download.html#build-windows
2. Extract to: `C:\ffmpeg`
3. Add to PATH:
   - Open System Properties → Environment Variables
   - Edit `Path` user variable
   - Add: `C:\ffmpeg\bin`
   - Restart terminal/PowerShell
4. Verify:
   ```bash
   ffmpeg -version
   ffprobe -version
   ```

**Option B: Scoop (if you have it)**
```bash
scoop install ffmpeg
```

**Option C: Chocolatey (if you have it)**
```bash
choco install ffmpeg
```

### 2. Python Dependencies

Run this once:
```bash
pip install yt-dlp openai-whisper pydub anthropic
```

**What each does:**
- `yt-dlp`: Download YouTube videos
- `openai-whisper`: Transcribe audio (first run downloads ~1.4GB model)
- `pydub`: Audio processing
- `anthropic`: Claude API for segment analysis

### 3. First-Time Setup

**First run will download Whisper model** (~1.4GB). This is normal and only happens once.

---

## Usage

### Basic
```bash
python clip_extraction_pipeline.py <YOUTUBE_URL>
```

### With custom clip count
```bash
python clip_extraction_pipeline.py <YOUTUBE_URL> --num-clips 15
```

### Example
```bash
python clip_extraction_pipeline.py https://www.youtube.com/watch?v=dQw4w9WgXcQ --num-clips 10
```

---

## Output

Clips are saved to: `clips/`

Format:
- `clip_001.mp4` (15-45 seconds each)
- Vertical format (9:16 aspect ratio - ready for TikTok/Instagram Reels/YouTube Shorts)
- Captions burned-in
- Ready for immediate upload

---

## Integration with Batch Upload

Once clips are generated:

```bash
python batch_upload.py  # Will use existing clips in clips/ folder
```

Or create a batch config first:

```bash
# After generating clips, run batch upload
python batch_upload.py
```

---

## Troubleshooting

### `ffmpeg: command not found`
→ FFmpeg not installed. See "FFmpeg Installation" above.

### `ModuleNotFoundError: No module named 'yt_dlp'`
→ Dependencies not installed. Run:
```bash
pip install yt-dlp openai-whisper pydub anthropic
```

### `Whisper model download slow`
→ Normal on first run (~1.4GB). Subsequent runs use cached model.

### API Rate Limit
→ If Claude API fails, check your ANTHROPIC_API_KEY env variable:
```bash
echo $ANTHROPIC_API_KEY
```

---

## Architecture

```
YouTube URL
    ↓
[Download with yt-dlp]
    ↓
[Extract audio]
    ↓
[Transcribe with Whisper]
    ↓
[Analyze with Claude] → Find viral moments
    ↓
[Generate clips with ffmpeg] → 15-45s vertical format
    ↓
[Burn captions] → Readable on mobile
    ↓
clips/clip_001.mp4
clips/clip_002.mp4
...
```

---

## Next Steps

1. Install FFmpeg
2. Run: `python clip_extraction_pipeline.py <URL> --num-clips 10`
3. Check `clips/` folder
4. Verify clips with: `ffmpeg -i clips/clip_001.mp4` (should show duration)
5. Run batch upload: `python batch_upload.py`

