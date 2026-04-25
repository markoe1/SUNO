# SUNO Clips — Product Hunt Pitch

**Tagline (60 chars)**
Automated clipping. Whop campaigns. 24/7.

**One-liner (<=80 chars)**
Automate Whop clips to TikTok, Instagram Reels, and YouTube Shorts.

**Short description (<=260 chars)**
SUNO Clips automates the full Whop clipping chain. It discovers active campaigns, manages your clip queue, posts to TikTok/IG/YouTube in parallel, and submits URLs back to Whop atomically — so every view counts toward your payout. Set it up once, run 24/7.

**Value props**
- 24/7 daemon: campaigns → queue → post → submit → track
- Parallel posting: TikTok, IG Reels, YouTube Shorts simultaneously
- Atomic URL submission — no missed payouts
- Account warmup system: 36hr hold, auto-ramp to 10 posts/day
- Cloudflare-safe: visible browser, session restore, human delays
- SQLite queue prevents duplicates; auto-retry on failures
- Earnings dashboard with daily/30-day goals

**Target users**
- Whop clippers, clip editors, growth teams, agency owners

**Why now**
- Whop campaigns pay per 1K views; speed and volume win
- Manual clippers spend 3-4 hours/day doing what SUNO Clips does automatically
- Browser automation is the only reliable path — platform APIs are locked down

**Makers' story (100-150 words)**
We built SUNO Clips after watching the Whop clipping ecosystem explode — and watching clippers waste hours on manual downloads, copy-pasting URLs, and hoping they hit the right posting times. The whole chain is automatable. SUNO Clips does it: scrape campaigns, manage the queue, post to all three platforms in parallel, and submit URLs back to Whop the moment each post goes live. No delayed submissions, no missed views, no manual anything. We focused on reliability — session restore so you log in once, warmup gating so new accounts don't get flagged, and debug snapshots when anything breaks. The goal is simple: more clips, posted faster, at better times. That's the only edge in the per-view game.

**FAQ**

Q: Is this safe for brand-new accounts?
A: Yes. SUNO Clips enforces a 36-hour warmup hold on new accounts, then ramps posting volume automatically (1 → 3 → 6 → 10/day) based on account age.

Q: Does it handle Cloudflare on Whop?
A: Yes. The browser runs in visible mode with human-paced navigation and session restore. Cloudflare bypass is built into the scraper.

Q: What about first login?
A: First run is manual — browser opens, you log in, session is saved. All future runs use the saved session.

Q: Which platforms are supported?
A: TikTok, Instagram Reels, YouTube Shorts. Facebook is built but disabled until business page setup.

**Links (add on launch day)**
- Repo: https://github.com/markoe1/SUNO
- Demo video: TBD
- Landing page: TBD
