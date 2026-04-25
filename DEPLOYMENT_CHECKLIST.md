# SUNO Production Deployment Checklist

## Pre-Deployment (Before Going Live)

### Phase 1: Environment Setup
- [ ] Copy `.env.production.example` to `.env`
- [ ] Set `WHOP_API_KEY` from Whop dashboard
- [ ] Set `WHOP_COMPANY_ID` from Whop dashboard
- [ ] Set `ANTHROPIC_API_KEY` (if using Claude features)
- [ ] Set production YouTube credentials path
- [ ] Review all environment variables: `python main.py --mode test`

### Phase 2: Database Preparation
- [ ] Database schema verified (run daemon once to initialize)
- [ ] Database file location accessible: `data/whop_clips.db`
- [ ] Backup strategy in place (if migrating existing data)
- [ ] At least 1GB free disk space available

### Phase 3: Content Pipeline Setup
- [ ] Create `clips/inbox/` directory
- [ ] Test with 1-2 sample clips in inbox
- [ ] Verify clip discovery: `python test_e2e.py`
- [ ] All 5 E2E tests pass

### Phase 4: Platform Credentials
- [ ] YouTube: `youtube_uploader/credentials.json` downloaded
- [ ] YouTube: OAuth manually authorized (browser popup expected on first run)
- [ ] YouTube: `youtube_uploader/token.pickle` created after auth
- [ ] TikTok: Email & password set (optional)
- [ ] Instagram: Email & password set (optional)

### Phase 5: Safety Configuration
- [ ] `MAX_DAILY_POSTING` set to desired limit (default 500)
- [ ] `MAX_HOURLY_POSTING` set to desired limit (default 50)
- [ ] `MAX_DAILY_SPENDING` set to daily budget (default $1000)
- [ ] `MIN_QUALITY_SCORE` set to quality threshold (default 70)
- [ ] Safety limits reviewed and understood

### Phase 6: Testing & Validation
- [ ] Run full test suite: `python test_e2e.py` (all pass)
- [ ] Daemon starts without errors: `python main.py --mode test`
- [ ] Clip discovery working: Check logs after 5 minutes
- [ ] At least one test clip successfully posted to YouTube

### Phase 7: Monitoring & Alerts
- [ ] Logs directory writable: `logs/`
- [ ] Event logging configured: `logs/events.jsonl`
- [ ] Monitoring log created: `logs/monitoring_*.log`
- [ ] Log rotation understood (auto-deletes logs >7 days old)

### Phase 8: Backup & Recovery
- [ ] `.env` file backed up securely (NOT in git)
- [ ] YouTube credentials backed up securely
- [ ] Database backup strategy documented
- [ ] Recovery procedure documented

## Deployment (Going Live)

### Launch Procedure
1. **Verify all checks above are complete**
2. **Start daemon process:**
   ```bash
   python main.py --mode daemon &
   ```
   Or with process manager (recommended):
   ```bash
   nohup python main.py --mode daemon > logs/daemon_startup.log 2>&1 &
   ```

3. **Verify daemon is running:**
   ```bash
   python main.py --mode status
   ```

4. **Monitor initial startup (first 10 minutes):**
   ```bash
   tail -f logs/daemon_*.log
   ```

5. **Check for errors in logs**

### First 24 Hours Monitoring

- [ ] Daemon is still running after 24 hours
- [ ] At least one clip was discovered and posted
- [ ] URLs submitted to Whop
- [ ] No memory leaks (check memory every 4 hours)
- [ ] No error rate spikes in logs
- [ ] Earnings started tracking

### First Week

- [ ] 100+ clips processed through pipeline
- [ ] Success rate >70% for posting
- [ ] No unrecovered crashes
- [ ] Safety limits never triggered
- [ ] Disk space usage stable
- [ ] Memory usage stable (<500MB normal)

## Ongoing Operations

### Daily Checks
- [ ] Daemon process still running: `ps aux | grep "python main.py"`
- [ ] Recent log entries (no old logs only): `ls -lt logs/*.log | head -1`
- [ ] Status check: `python main.py --mode status`

### Weekly Checks
- [ ] Review logs for anomalies: `grep ERROR logs/daemon_*.log`
- [ ] Check disk space: `df -h`
- [ ] Memory usage: Check peak in daemon_reliability logs
- [ ] Earnings growth tracking on Whop dashboard

### Monthly Tasks
- [ ] Archive old logs (>30 days)
- [ ] Review safety limits and adjust if needed
- [ ] Check clip quality trends in quality_log.json
- [ ] Update environment variables if needed
- [ ] Test recovery procedure (optional): Stop and restart daemon

## Emergency Procedures

### Daemon Crashes (Auto-Recovery)
- Daemon will attempt to restart automatically
- If >5 crashes in 5 minutes, it gives up and logs critical error
- Check logs for crash reason
- Manual restart: `python main.py --mode daemon &`

### Too Many Errors (Safety Stop)
- If error rate exceeds configured limit, posting stops
- Check logs for error type
- Investigate and fix root cause
- Manually reset: Delete `data/daemon_state.json` and restart

### Database Corruption
- If database becomes locked or corrupted:
  ```bash
  # Backup current database
  mv data/whop_clips.db data/whop_clips.db.backup

  # Daemon will recreate on restart
  python main.py --mode test
  ```
- This will lose clip history but preserves schema

### High Memory Usage (>500MB)
- Daemon automatically alerts and requests cleanup
- Check for:
  - Open file handles: Too many clips in memory
  - Large log files: Rotate logs with `python -c "import shutil; shutil.rmtree('logs/old')"`
  - Memory leak: Restart daemon

### Disk Full
- Daemon will refuse to post
- Check: `df -h`
- Clean up:
  ```bash
  # Archive logs
  tar czf logs_archive_$(date +%Y%m%d).tar.gz logs/*.log
  rm logs/*.log
  ```

## Rollback Procedure

If deployment needs to be rolled back:

1. **Stop daemon:**
   ```bash
   pkill -f "python main.py"
   ```

2. **Restore .env from backup:**
   ```bash
   cp .env.backup .env
   ```

3. **Restore database if needed:**
   ```bash
   mv data/whop_clips.db.new data/whop_clips.db.backup
   mv data/whop_clips.db.old data/whop_clips.db
   ```

4. **Restart with previous version** if code rolled back

5. **Verify**: `python main.py --mode status`

## Success Criteria

Deployment is successful when:

- ✅ Daemon runs for 24+ hours without crashing
- ✅ At least 10 clips posted in first 24 hours
- ✅ Success rate >50% (more clips posted than failed)
- ✅ No unrecovered safety limit triggers
- ✅ Earnings showing on Whop dashboard
- ✅ Memory usage stable (<500MB)
- ✅ No uncaught exceptions in logs

## Post-Deployment Optimization

Once stable (after 1 week):

- [ ] Review quality_log.json, adjust MIN_QUALITY_SCORE if needed
- [ ] Adjust posting times based on Whop dashboard insights
- [ ] Consider enabling TikTok/Instagram if YouTube is stable
- [ ] Increase CLIPS_PER_SESSION if system handles it easily
- [ ] Setup log rotation cron job (if not auto-rotating)
- [ ] Setup daily backup of database (cron job)

## Contact & Support

**If deployment fails:**
1. Check logs for specific error
2. Verify all environment variables are set
3. Run: `python main.py --mode test`
4. Review SETUP.md troubleshooting section
5. Check GitHub issues or documentation

**Production monitoring dashboard:**
```bash
# View real-time status
watch -n 30 'python main.py --mode status'
```
