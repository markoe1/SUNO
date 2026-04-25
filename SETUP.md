# SUNO Setup & Deployment Guide

**SUNO** is a 24/7 automated video clipping platform that discovers, clips, and posts content to YouTube, Instagram, and TikTok, with earnings tracked via Whop.

## Requirements

- Python 3.8+
- SQLite3 (included with Python)
- 1GB+ free disk space
- YouTube account for API testing

## Installation

### 1. Clone & Install Dependencies

```bash
cd SUNO-repo
pip install -r requirements.txt
```

### 2. Setup Environment

Create `.env` file with your credentials:

```bash
# Copy template and fill in values
cp .env.production.example .env
```

**Required keys:**
```
WHOP_API_KEY=apik_YOUR_KEY_HERE
WHOP_COMPANY_ID=biz_YOUR_COMPANY_ID
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
```

**For YouTube posting:**
```
# 1. Visit https://console.cloud.google.com
# 2. Create OAuth 2.0 credentials (Desktop app)
# 3. Download JSON file as youtube_uploader/credentials.json
# 4. First upload will open browser for manual auth
# 5. Token saved to youtube_uploader/token.pickle (reused automatically)
```

**Optional platform credentials:**
```
TIKTOK_USERNAME=your_email@example.com
TIKTOK_PASSWORD=your_password

INSTAGRAM_USERNAME=your_email@example.com
INSTAGRAM_PASSWORD=your_password
```

### 3. Verify Setup

```bash
python main.py --mode test
```

This checks:
- Whop API connectivity
- YouTube credentials
- Database readiness
- All required environment variables

## Running SUNO

### Daemon Mode (24/7 Autonomous)

```bash
python main.py --mode daemon
```

This starts the autonomous 24/7 operation:
- Monitors clips/inbox for new files
- Applies quality checks
- Validates campaign requirements
- Posts to enabled platforms
- Submits URLs to Whop
- Tracks earnings

Runs in a loop with:
- Health checks every 2 minutes
- Clip discovery every 5 minutes
- Posting sessions on configured schedule
- URL submission every 5 minutes

### Single Operations

**Refresh Whop campaigns:**
```bash
python main.py --mode campaigns
```

**Post pending clips:**
```bash
python main.py --mode post --count 5
```

**Show current status:**
```bash
python main.py --mode status
```

**View earnings:**
```bash
python main.py --mode dashboard
```

## Clip Input

SUNO expects video files in `clips/inbox/` with format:

```
{creator}_{source}_{campaign}_{title}_{duration}.mp4
```

Example:
```
mrbeast_youtube_viral_compilation_30.mp4
```

### Metadata File (Optional)

For richer metadata, create `.meta.json` with same base name:

```json
{
  "creator_name": "MrBeast",
  "source_platform": "youtube",
  "source_url": "https://youtube.com/watch?v=abc123",
  "clip_duration": 30,
  "caption": "Epic compilation",
  "hashtags": "viral,compilation"
}
```

## Logs

All logs saved to `logs/` directory:

- `daemon_YYYYMMDD.log` - Daemon operations
- `monitoring_YYYYMMDD.log` - Safety and monitoring events
- `events.jsonl` - Structured event log (JSON lines format)

## Safety & Limits

SUNO includes safety guardrails (configurable via .env):

- `MAX_DAILY_POSTING=500` - Max clips per day
- `MAX_HOURLY_POSTING=50` - Max clips per hour
- `MAX_DAILY_SPENDING=1000.0` - Max budget per day
- `MAX_ERROR_RATE=0.5` - Stop if >50% errors
- `MAX_CONSECUTIVE_ERRORS=10` - Stop after 10 errors
- `MIN_QUALITY_SCORE=70` - Reject clips below 70/100

## Testing

Run end-to-end tests:

```bash
python test_e2e.py
```

Tests verify:
- Clip discovery and ingestion
- Quality gating
- Campaign requirements
- Safety limits
- Event monitoring

## Troubleshooting

### No clips appear in database

1. Check `clips/inbox/` has video files
2. Run `python test_e2e.py` to test discovery
3. Check logs: `tail -f logs/daemon_*.log`

### YouTube posting fails

1. Verify `youtube_uploader/credentials.json` exists
2. Delete `youtube_uploader/token.pickle` to re-authenticate
3. Run: `python -c "from youtube_uploader.suno_integration import main; main()"`

### High memory usage

SUNO will auto-alert and slow down if memory exceeds 500MB (configurable).

Check current usage:
```bash
python -c "import psutil; p = psutil.Process(); print(f'Memory: {p.memory_info().rss / 1024 / 1024:.1f}MB')"
```

### Database locked

If you see "database is locked", close any other instances of SUNO:

```bash
# Find SUNO processes
ps aux | grep "python main.py"

# Kill process
kill PID
```

Delete old lock files:
```bash
rm data/whop_clips.db-journal 2>/dev/null
```

## Architecture

```
clips/inbox
    ↓ (Clip Discovery - PHASE 6)
Metadata Extraction
    ↓ (Quality Check - PHASE 4)
Quality Gating
    ↓ (Campaign Validation - PHASE 5)
Campaign Requirements
    ↓ (Platform Selection - PHASE 2)
Platform Posting (YouTube/TikTok/Instagram)
    ↓
URL Submission to Whop
    ↓ (Earnings - continuous tracking)
Earnings Dashboard
```

## Deployment Checklist

- [ ] Rename `.env.production.example` to `.env`
- [ ] Add WHOP_API_KEY and WHOP_COMPANY_ID
- [ ] Add ANTHROPIC_API_KEY
- [ ] Setup YouTube OAuth (download credentials.json)
- [ ] Run `python main.py --mode test` (should pass)
- [ ] Create `clips/inbox/` directory if missing
- [ ] Run `python test_e2e.py` (all tests pass)
- [ ] Start daemon: `python main.py --mode daemon &`
- [ ] Monitor logs: `tail -f logs/daemon_*.log`
- [ ] Check status: `python main.py --mode status`
- [ ] Wait 5+ minutes for clip discovery to start

## Support

If you encounter issues:

1. Check logs for error messages
2. Run `python main.py --mode test` to verify setup
3. Verify all required environment variables are set
4. Ensure clips/inbox has readable video files
5. Delete `data/whop_clips.db` to reset database
