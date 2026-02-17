# SUNO (Sold Up Not Out) — Product Hunt Pitch

Tagline (60 chars)
Automated short-form posting that pays you while you sleep.

One‑liner (<=80 chars)
Automate Vyro clips to TikTok, IG Reels, and YouTube Shorts.

Short description (<=260 chars)
SUNO automates the boring parts of clipping so you can focus on scale. It fetches brand‑approved Vyro clips, posts to TikTok/IG/YouTube in parallel, schedules peak times, retries failures, and tracks earnings — all from one simple CLI.

Value props
- 24/7 daemon: fetch → queue → post → track
- Parallel posting: TikTok, IG Reels, YouTube (FB optional)
- Real browser automation (Playwright) for reliability
- SQLite queue prevents duplicates; auto‑retry on failures
- Earnings dashboard with daily/30‑day goals

Target users
- Solo creators, clip editors, growth teams, agency owners

Why now
- Vyro campaigns pay per 1K views; speed and volume win
- Short‑form demand + platform APIs are messy → browser automation

Makers’ story (100–150 words)
We built SUNO after watching friends spend 3–4 hours/day downloading and posting clips manually. It’s tedious, easy to mess up, and throttles output. SUNO turns it into a background process: you set credentials once, choose daily volume, and the bot handles the rest. We focused on reliability (session restore, retries, visibility with headless off) and pragmatism (SQLite queue, Windows‑friendly). The goal isn’t fancy dashboards — it’s compounding output. Post more, more often, at better times. That’s how you win the per‑view game.

FAQ
Q: Is this safe for brand‑new accounts?
A: Start slow (1–3 posts/session). SUNO spaces uploads and supports manual review with headless=False.

Q: Does it support Facebook/X?
A: FB Page support is built but disabled by default. X is planned — placeholders are in the .env.

Q: What about Google login and Vyro email codes?
A: First run is manual; SUNO stores a session (storage state) for future runs.

Links (to add on launch day)
- Website/Repo: https://github.com/markoe1/SUNO
- Demo video: TBD
- Landing page: TBD