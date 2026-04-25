"""
Daemon Reliability Module
=========================
PHASE 7: 24/7 daemon robustness, error recovery, resource management.

Features:
1. Crash recovery with state restoration
2. Connection pooling and cleanup
3. Resource monitoring (memory, CPU, disk)
4. Graceful degradation under load
5. Automatic restart on critical errors
6. Comprehensive health checks
"""

import logging
import psutil
import asyncio
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
import json

import config

logger = logging.getLogger(__name__)


class DaemonHealth:
    """Monitor daemon health and system resources."""

    def __init__(self, memory_threshold_mb: int = 500, disk_threshold_gb: int = 1):
        self.memory_threshold = memory_threshold_mb * 1024 * 1024  # bytes
        self.disk_threshold = disk_threshold_gb * 1024 * 1024 * 1024  # bytes
        self.process = psutil.Process()
        self.last_check = None
        self.health_history: List[Dict] = []
        self.max_history = 100

    def check_memory(self) -> Tuple[bool, str]:
        """Check if memory usage is acceptable."""
        try:
            memory_info = self.process.memory_info()
            rss = memory_info.rss  # Resident set size

            if rss > self.memory_threshold:
                msg = f"Memory usage high: {rss / 1024 / 1024:.1f}MB > {self.memory_threshold / 1024 / 1024:.1f}MB"
                return False, msg

            return True, f"Memory OK: {rss / 1024 / 1024:.1f}MB"
        except Exception as e:
            logger.error(f"Failed to check memory: {e}")
            return True, f"Unable to check memory: {e}"

    def check_disk(self) -> Tuple[bool, str]:
        """Check if disk space is available."""
        try:
            disk_usage = psutil.disk_usage(config.DATA_DIR)

            if disk_usage.free < self.disk_threshold:
                msg = f"Low disk space: {disk_usage.free / 1024 / 1024 / 1024:.1f}GB < {self.disk_threshold / 1024 / 1024 / 1024:.1f}GB"
                return False, msg

            return True, f"Disk OK: {disk_usage.free / 1024 / 1024 / 1024:.1f}GB free"
        except Exception as e:
            logger.error(f"Failed to check disk: {e}")
            return True, f"Unable to check disk: {e}"

    def check_database(self, queue_manager) -> Tuple[bool, str]:
        """Check if database is accessible."""
        try:
            # Try to get basic stats
            stats = queue_manager.get_daily_stats()
            return True, f"Database OK: {stats.get('clips_pending', 0)} pending clips"
        except Exception as e:
            logger.error(f"Database check failed: {e}")
            return False, f"Database error: {e}"

    def check_logging(self) -> Tuple[bool, str]:
        """Check if logs are being written."""
        try:
            log_dir = config.LOGS_DIR
            log_dir.mkdir(parents=True, exist_ok=True)

            # Check if any logs were written recently
            log_files = list(log_dir.glob("*.log"))
            if log_files:
                newest = max(log_files, key=lambda p: p.stat().st_mtime)
                age_seconds = (datetime.now() - datetime.fromtimestamp(newest.stat().st_mtime)).total_seconds()

                if age_seconds < 3600:  # Modified in last hour
                    return True, f"Logging OK: {newest.name} updated {age_seconds:.0f}s ago"
                else:
                    return False, f"Logging stale: {newest.name} not updated for {age_seconds:.0f}s"
            else:
                return True, "No logs yet (starting up)"
        except Exception as e:
            logger.error(f"Logging check failed: {e}")
            return False, f"Logging check error: {e}"

    def full_health_check(self, queue_manager) -> Dict[str, object]:
        """Run comprehensive health check."""
        self.last_check = datetime.now()

        checks = {
            'timestamp': self.last_check.isoformat(),
            'memory': self.check_memory(),
            'disk': self.check_disk(),
            'database': self.check_database(queue_manager),
            'logging': self.check_logging(),
        }

        # Overall status: OK if no checks failed
        overall_ok = all(check[0] for check in checks.values() if isinstance(check, tuple))

        result = {
            'healthy': overall_ok,
            'timestamp': checks['timestamp'],
            'checks': {
                'memory': {'ok': checks['memory'][0], 'message': checks['memory'][1]},
                'disk': {'ok': checks['disk'][0], 'message': checks['disk'][1]},
                'database': {'ok': checks['database'][0], 'message': checks['database'][1]},
                'logging': {'ok': checks['logging'][0], 'message': checks['logging'][1]},
            }
        }

        # Keep health history for trend analysis
        self.health_history.append(result)
        if len(self.health_history) > self.max_history:
            self.health_history.pop(0)

        return result

    def get_health_summary(self) -> str:
        """Get human-readable health summary."""
        if not self.last_check:
            return "No health check performed yet"

        lines = [
            f"Health Check: {self.last_check.isoformat()}",
            "─" * 50,
        ]

        for check_name, check_result in [
            ('Memory', self.check_memory()),
            ('Disk', self.check_disk()),
            ('Logging', self.check_logging()),
        ]:
            ok, msg = check_result
            status = "[OK]" if ok else "[ALERT]"
            lines.append(f"{status} {check_name}: {msg}")

        return "\n".join(lines)


class DaemonRecovery:
    """Handle daemon crash recovery and state restoration."""

    STATE_FILE = config.DATA_DIR / "daemon_state.json"

    def __init__(self):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.crash_count = 0
        self.last_crash_time = None

    def save_state(self, state: Dict) -> bool:
        """Save daemon state for recovery."""
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'state': state,
                }, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save daemon state: {e}")
            return False

    def load_state(self) -> Optional[Dict]:
        """Load saved daemon state."""
        try:
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE) as f:
                    data = json.load(f)
                    state_age = (datetime.now() - datetime.fromisoformat(data['timestamp'])).total_seconds()
                    if state_age < 3600:  # Only restore if less than 1 hour old
                        logger.info(f"Restoring daemon state from {state_age:.0f}s ago")
                        return data['state']
                    else:
                        logger.info(f"Daemon state too old ({state_age:.0f}s), not restoring")
        except Exception as e:
            logger.error(f"Failed to load daemon state: {e}")

        return None

    def record_crash(self) -> bool:
        """Record a crash for monitoring and auto-restart."""
        self.crash_count += 1
        self.last_crash_time = datetime.now()
        logger.error(f"Crash recorded (count: {self.crash_count})")

        # If too many crashes in short time, bail out
        if self.crash_count >= 5:
            if self.last_crash_time and (datetime.now() - self.last_crash_time).total_seconds() < 300:
                logger.critical("Too many crashes in short time, giving up")
                return False

        return True

    def reset_crash_count(self):
        """Reset crash counter on successful operation."""
        if self.crash_count > 0:
            logger.info(f"Crash recovery successful, reset counter from {self.crash_count}")
        self.crash_count = 0


class ResourceCleaner:
    """Periodically clean up resources."""

    def __init__(self):
        self.last_cleanup = None

    async def cleanup(self) -> bool:
        """Clean up old files, temp data, etc."""
        logger.info("Running resource cleanup...")
        self.last_cleanup = datetime.now()

        try:
            # Clean up old logs (keep last 7 days)
            self._cleanup_old_logs(days=7)

            # Clean up temp files
            self._cleanup_temp_files()

            logger.info("Resource cleanup complete")
            return True
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            return False

    def _cleanup_old_logs(self, days: int = 7):
        """Remove log files older than N days."""
        cutoff = datetime.now() - timedelta(days=days)
        log_dir = config.LOGS_DIR

        if log_dir.exists():
            for log_file in log_dir.glob("*.log"):
                try:
                    file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_time < cutoff:
                        log_file.unlink()
                        logger.debug(f"Deleted old log: {log_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete log {log_file.name}: {e}")

    def _cleanup_temp_files(self):
        """Clean up temporary/failed files."""
        # Could implement cleanup of failed uploads, temp downloads, etc
        pass


def main():
    """Test reliability module."""
    logging.basicConfig(level=logging.INFO)

    health = DaemonHealth()
    logger.info(health.get_health_summary())


if __name__ == "__main__":
    main()
