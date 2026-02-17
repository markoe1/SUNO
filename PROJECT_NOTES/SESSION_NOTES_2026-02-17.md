# Session Notes — 2026-02-17

Scope
- SUNO (Sold Up Not Out) automation system, forked from VyroClipper
- Repos: markoe1/SUNO (primary), markoe1/VyroClipper (upstream history)

Decisions
- Facebook posting disabled until FB Page is created (config.PLATFORMS = ["tiktok","instagram","youtube"]).
- Vyro app domain fixed to app.vyro.com; manual login with session storage enabled.
- Optional X/Twitter credentials placeholders added; posting not yet implemented.
- Product Hunt will be used for launch; launch pack added at launch/producthunt/.

Status
- .env populated except Facebook (to be added later).
- Fetch flow tested; campaigns discovery WIP based on live selectors.
- GitHub repos private as needed; SUNO is active.

Next Actions
- Run: `python main.py --mode fetch -c 1` and complete Vyro email code login.
- When FB Page is ready, re-enable by setting PLATFORMS to include "facebook".
- Consider adding X posting after core 3 are verified.