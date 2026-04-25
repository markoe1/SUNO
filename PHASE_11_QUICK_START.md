# Phase 11 Quick Start — One Command to Finish

## Current Status

**Infrastructure:** ✓ Complete
**Blocking:** YouTube OAuth token needs re-authorization with proper scopes

## One Command to Unblock

```bash
cd ~/SUNO-repo
python setup_youtube_oauth.py
```

This will:
1. Check if token exists
2. If missing or has wrong scopes → Opens browser for Google OAuth
3. You click "Authorize" and approve scopes
4. Token saved automatically to `youtube_uploader/token.pickle`
5. Ready to post!

## Verify It Worked

```bash
python setup_youtube_oauth.py --validate
```

Expected output:
```
✓ Token is valid with proper scopes
```

## See Full Test Suite

```bash
python phase11_test_posting.py
```

Should show:
```
✓ PASS: adapter_registry
✓ PASS: youtube_token                   ← Now passes after OAuth
✓ PASS: youtube_adapter
✓ PASS: youtube_payload
... (Instagram/TikTok optional)
```

## What This Unblocks

Once YouTube token is set up:
- All 5 platform adapters ready to post
- Unified posting interface working
- Can post videos to YouTube with proper IDs/URLs returned
- Ready for Phase 12 (actual posting tests)

## Files Created

- `suno/posting/youtube_oauth.py` — OAuth token manager
- `setup_youtube_oauth.py` — CLI setup tool (what you'll run)
- `phase11_test_posting.py` — Validation test suite
- `PHASE_11_COMPLETION.md` — Full technical spec

## Optional Platforms

**Instagram:** Needs Meta Graph API credentials (see PHASE_11_SETUP_GUIDE.md)
**TikTok:** Needs developer app (not available, can be skipped)

## Phase 11 Deliverable Status

- ✓ Unified platform interface complete
- ✓ All adapters implemented
- ⏳ YouTube OAuth (fix: 1 command above)
- ⏳ Test posts (pending video infrastructure)

## Next Steps After OAuth

1. Run: `python phase11_test_posting.py` ← Verify everything
2. Upload test video to `clips/` folder
3. Test posting: `python test_post_video.py --platform youtube --video test.mp4`
4. Verify: Check post_id and URL returned
5. Phase 12: Hardening and multi-platform testing

## Timeline

- **Now:** Run OAuth setup (30 seconds)
- **Phase 12:** Test actual posting (posting infrastructure)
- **Phase 13+:** Creator validation, content ingestion

## Credentials File

Your OAuth credentials are already in place:
```
✓ youtube_uploader/credentials.json (410 bytes)
```

The setup script will use this to open OAuth flow and save your token to:
```
✓ youtube_uploader/token.pickle (created after first OAuth)
```

Both stay local — never committed to git.
