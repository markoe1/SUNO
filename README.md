# VyroClipper

Automated Vyro clipping system for posting 10-15 clips/day across TikTok, Instagram Reels, and YouTube Shorts.

## Features

- **Automated Vyro Scraping**: Downloads pre-made clips from Vyro campaigns
- **Multi-Platform Posting**: Posts to TikTok, Instagram, YouTube simultaneously
- **24/7 Daemon Mode**: Runs continuously with scheduled posting times
- **Earnings Tracking**: Real-time dashboard showing views and earnings
- **SQLite Queue**: Tracks all clips, statuses, and URLs

## Quick Start

### 1. Install

```powershell
# Run the installer
.\install.ps1
```

### 2. Configure

Edit `.env` with your credentials:

```
VYRO_EMAIL=your@email.com
VYRO_PASSWORD=yourpassword

TIKTOK_USERNAME=yourusername
TIKTOK_PASSWORD=yourpassword

INSTAGRAM_USERNAME=yourusername
INSTAGRAM_PASSWORD=yourpassword

YOUTUBE_EMAIL=your@gmail.com
YOUTUBE_PASSWORD=yourpassword
```

### 3. Test

```powershell
python main.py --mode test
```

### 4. Run

```powershell
# Single run (15 clips)
python main.py --mode run --count 15

# 24/7 daemon
python main.py --mode daemon
```

## Commands

| Command | Description |
|---------|-------------|
| `--mode test` | Verify configuration |
| `--mode status` | Show current status |
| `--mode dashboard` | Show earnings dashboard |
| `--mode fetch --count N` | Download N clips from Vyro |
| `--mode post --count N` | Post N pending clips |
| `--mode run --count N` | Full workflow (fetch + post) |
| `--mode daemon` | Run 24/7 automation |

## Directory Structure

```
VyroClipper/
├── main.py              # Main entry point
├── config.py            # All configuration
├── daemon.py            # 24/7 runner
├── vyro_scraper.py      # Vyro browser automation
├── platform_poster.py   # Multi-platform posting
├── queue_manager.py     # SQLite clip tracking
├── earnings_tracker.py  # Dashboard and stats
├── .env                 # Your credentials (create from template)
├── clips/
│   ├── inbox/           # Downloaded clips
│   ├── ready/           # Processed clips
│   ├── posted/          # Successfully posted
│   └── failed/          # Failed posts
├── logs/                # Daily logs
└── data/                # SQLite database
```

## Configuration

Edit `config.py` to customize:

- **DAILY_CLIP_TARGET**: Clips per day (default: 15)
- **POSTING_TIMES**: When to post (default: 8am, 12:30pm, 7pm)
- **CLIPS_PER_SESSION**: Clips per posting session (default: 5)
- **CPM_RATE**: Dollars per 1K views (default: $3)

## How It Works

1. **Fetch**: Browser automation logs into Vyro, downloads available clips
2. **Queue**: Clips stored in SQLite with generated captions/hashtags
3. **Post**: Parallel posting to all 3 platforms
4. **Submit**: URLs submitted back to Vyro for view tracking
5. **Track**: Earnings dashboard shows views/earnings

## Earnings Math

```
15 clips/day × 5,000 views/clip × 3 platforms = 225,000 views
225,000 ÷ 1,000 × $3 = $675/day potential
```

## Troubleshooting

### Login Issues
- Platforms may require manual verification first time
- Set `HEADLESS = False` in config.py to see browser
- Complete any CAPTCHAs manually, then re-run

### Rate Limits
- System includes delays between posts
- Increase `POST_DELAY_MIN/MAX` if hitting limits

### Missing Clips
- Check Vyro has active campaigns
- Verify credentials in `.env`

## Safety Notes

- Browser automation can trigger security checks
- Start with small counts to test
- Keep credentials secure
- Don't run multiple instances

## License

For personal use only.
