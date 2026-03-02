# SUNO Clips

Automated clipping. Whop campaigns. 24/7.

SUNO Clips scrapes live Whop clipping campaigns, manages your clip queue, and posts to TikTok, Instagram Reels, and YouTube Shorts on a 24/7 schedule — with automatic URL submission back to Whop so every view counts toward your payout.

> Product Hunt launch pack in `launch/producthunt/`

## How It Works

1. **Campaigns** — Scrapes `whop.com/discover/clipping`, filters by CPM and budget
2. **Inbox** — Drop AI-clipped `.mp4` files into `clips/inbox/`
3. **Post** — Parallel posting to TikTok, Instagram, YouTube
4. **Submit** — URLs submitted to Whop atomically after every post
5. **Track** — Earnings dashboard shows views and payouts

## Quick Start

### 1. Install

```powershell
.\install.ps1
```

### 2. Configure

Copy `.env.template` to `.env` and fill in credentials:

```
WHOP_EMAIL=your@email.com
TIKTOK_USERNAME=yourusername
TIKTOK_PASSWORD=yourpassword
INSTAGRAM_USERNAME=yourusername
INSTAGRAM_PASSWORD=yourpassword
YOUTUBE_EMAIL=your@gmail.com
YOUTUBE_PASSWORD=yourpassword
```

### 3. Login to Whop (one time)

```powershell
python main.py --mode login
```

Browser opens. Log in manually. Session saved to `data/whop_session.json` — not needed again.

### 4. Run

```powershell
# Refresh campaigns
python main.py --mode campaigns

# Post clips from inbox
python main.py --mode post --count 5

# Full cycle (campaigns + post)
python main.py --mode run --count 15

# 24/7 daemon
python main.py --mode daemon
```

## Commands

| Command | Description |
|---------|-------------|
| `--mode login` | Save Whop session (run once) |
| `--mode campaigns` | Discover and refresh Whop campaigns |
| `--mode post --count N` | Post N clips from inbox |
| `--mode run --count N` | Full cycle (campaigns + post) |
| `--mode daemon` | 24/7 automation |
| `--mode status` | Queue + account warmup status |
| `--mode dashboard` | Earnings overview |
| `--mode test` | Verify config and credentials |

## Account Warmup

New accounts are held for 36 hours before any posting, then ramped automatically:

| Account Age | Posts/Day |
|-------------|-----------|
| Day 1–3 | 1 |
| Day 4–7 | 3 |
| Day 14+ | 6 |
| Day 30+ | 10 |

## Directory Structure

```
SUNO-repo/
├── main.py              # Entry point
├── config.py            # All settings
├── daemon.py            # 24/7 runner
├── whop_scraper.py      # Whop campaign scraper + URL submission
├── platform_poster.py   # TikTok / Instagram / YouTube posting
├── queue_manager.py     # SQLite clip + account tracking
├── earnings_tracker.py  # Dashboard and stats
├── .env                 # Credentials (create from .env.template)
├── clips/
│   ├── inbox/           # Drop clips here to post
│   ├── posted/          # Successfully posted
│   └── failed/          # Failed posts
├── logs/                # Daily daemon logs
└── data/                # SQLite DB + Whop session
```

## Earnings Math

```
15 clips/day x 5,000 views/clip x 3 platforms = 225,000 views
225,000 / 1,000 x $3 = $675/day potential
```

## Troubleshooting

**Whop login fails** — Run `--mode login`, complete login manually in the browser window.

**Cloudflare block** — `HEADLESS = False` in config.py is required. Do not change it.

**Rate limits** — Increase `POST_DELAY_MIN/MAX` in config.py.

**Zero campaigns found** — Check `data/whop_debug_*.html` for a snapshot of what the scraper saw.

## License

For personal use only.
