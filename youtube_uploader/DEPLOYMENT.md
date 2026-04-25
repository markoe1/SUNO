# YouTube Uploader — Deployment Guide

## For Production/Automation

### 1. Credentials Setup (One Time)

Place your OAuth credentials.json here:
```
/c/Users/ellio/SUNO-repo/youtube_uploader/credentials.json
```

First run will open browser for authorization. Token is saved automatically.

### 2. Run Dry Run (Safe Test)

```bash
cd /c/Users/ellio/SUNO-repo/youtube_uploader
python suno_integration.py
```

This lists clips without uploading. Verify it finds your clips.

### 3. Enable Real Uploads

Edit `suno_integration.py`, uncomment:
```python
# results = integration.upload_all_clips(dry_run=False)
```

### 4. Full Batch Upload

```bash
python suno_integration.py
```

All clips from `../clips/inbox/` upload to YouTube with:
- Auto-generated titles from filenames
- Tags: `['suno', 'ai-music', 'ai-generated']`
- Privacy: `unlisted` (visible by link only)
- Category: Music

### 5. Cron/Scheduled Uploads

Linux/Mac:
```bash
0 */6 * * * cd /c/Users/ellio/SUNO-repo/youtube_uploader && python suno_integration.py
```

Windows Task Scheduler:
```
Program: python
Arguments: /c/Users/ellio/SUNO-repo/youtube_uploader/suno_integration.py
Schedule: Every 6 hours
```

### 6. SUNO Orchestrator Integration

Add to SUNO's orchestrator.py:

```python
from youtube_uploader.suno_integration import SUNOYouTubeIntegration

class PipelineOrchestrator:
    def __init__(self, ...):
        self.youtube = SUNOYouTubeIntegration(
            suno_clips_dir='clips/inbox',
            credentials_file='youtube_uploader/credentials.json'
        )

    def post_to_youtube(self):
        """Upload all generated clips to YouTube"""
        results = self.youtube.upload_all_clips(dry_run=False)
        logger.info(f"YouTube upload: {results['uploaded']}/{results['total']} successful")
        return results
```

## Troubleshooting

**Q: "credentials.json not found"**
A: Download from Google Cloud and place in youtube_uploader/ folder

**Q: "Token expired"**
A: Delete token.pickle, next run will re-authorize (browser opens once)

**Q: "Upload rate limited"**
A: YouTube limits uploads. Space them out or use task scheduling.

**Q: "Video not found"**
A: Check file path. Use absolute paths: `/c/Users/ellio/SUNO-repo/clips/inbox/video.mp4`

## Architecture

```
SUNO (generates clips)
    ↓
clips/inbox/ (stores .mp4 files)
    ↓
youtube_uploader/suno_integration.py (reads inbox)
    ↓
YouTubeUploader (OAuth, upload)
    ↓
YouTube (published)
```

No password storage. OAuth token cached locally. Compliant with YouTube ToS.
