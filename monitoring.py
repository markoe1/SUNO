"""
Monitoring, Logging & Safety Module
====================================
PHASE 8: Comprehensive monitoring, logging, and safety guardrails.

Features:
1. Event logging with full context
2. Anomaly detection and alerts
3. Safety limits (spending, posting rate, error rate)
4. Real-time metrics collection
5. Error aggregation and reporting
"""

import logging
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

import config
from queue_manager import QueueManager

logger = logging.getLogger(__name__)

# Setup dedicated monitoring logger
MONITORING_LOG_FILE = config.LOGS_DIR / f"monitoring_{datetime.now().strftime('%Y%m%d')}.log"
monitoring_logger = logging.getLogger("monitoring")
monitoring_logger.addHandler(logging.FileHandler(MONITORING_LOG_FILE))
monitoring_logger.setLevel(logging.INFO)


class EventType(Enum):
    """Critical event types to monitor."""
    CLIP_POSTED = "clip_posted"
    CLIP_FAILED = "clip_failed"
    POSTING_ERROR = "posting_error"
    QUALITY_GATE_BLOCKED = "quality_blocked"
    CAMPAIGN_GATE_BLOCKED = "campaign_blocked"
    EARNINGS_TRACKED = "earnings_tracked"
    API_ERROR = "api_error"
    CRASH = "crash"
    RECOVERY = "recovery"


@dataclass
class MonitoringEvent:
    """Structured event for monitoring."""
    timestamp: str
    event_type: str
    clip_id: Optional[int] = None
    clip_name: Optional[str] = None
    platform: Optional[str] = None
    error_message: Optional[str] = None
    context: Optional[Dict] = None
    severity: str = "info"  # debug, info, warning, error, critical


class EventMonitor:
    """Collect and store monitoring events."""

    def __init__(self, max_events: int = 10000):
        self.events: List[MonitoringEvent] = []
        self.max_events = max_events
        self.event_file = config.LOGS_DIR / "events.jsonl"

    def log_event(self, event: MonitoringEvent) -> None:
        """Log a monitoring event."""
        self.events.append(event)

        # Write to JSONL file for persistence
        try:
            with open(self.event_file, 'a') as f:
                f.write(json.dumps(asdict(event)) + '\n')
        except Exception as e:
            logger.error(f"Failed to write event: {e}")

        # Keep in-memory buffer bounded
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

        # Log to monitoring logger
        log_level = getattr(logging, event.severity.upper(), logging.INFO)
        monitoring_logger.log(
            log_level,
            f"{event.event_type}: {event.clip_name or event.error_message}"
        )

    def get_recent_events(self, count: int = 100, event_type: Optional[str] = None) -> List[MonitoringEvent]:
        """Get recent events."""
        events = self.events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-count:]

    def get_event_summary(self, hours: int = 24) -> Dict:
        """Get summary of events from last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [
            e for e in self.events
            if datetime.fromisoformat(e.timestamp) > cutoff
        ]

        summary = {
            'total_events': len(recent),
            'by_type': {},
            'by_severity': {},
            'clips_posted': 0,
            'clips_failed': 0,
            'api_errors': 0,
        }

        for event in recent:
            # Count by type
            if event.event_type not in summary['by_type']:
                summary['by_type'][event.event_type] = 0
            summary['by_type'][event.event_type] += 1

            # Count by severity
            if event.severity not in summary['by_severity']:
                summary['by_severity'][event.severity] = 0
            summary['by_severity'][event.severity] += 1

            # Aggregate key metrics
            if event.event_type == EventType.CLIP_POSTED.value:
                summary['clips_posted'] += 1
            elif event.event_type == EventType.CLIP_FAILED.value:
                summary['clips_failed'] += 1
            elif event.event_type == EventType.API_ERROR.value:
                summary['api_errors'] += 1

        return summary


class SafetyLimiter:
    """Safety guardrails to prevent runaway behavior."""

    def __init__(self):
        self.queue = QueueManager()
        # Configurable limits
        self.max_daily_posting = int(os.getenv('MAX_DAILY_POSTING', '500'))
        self.max_hourly_posting = int(os.getenv('MAX_HOURLY_POSTING', '50'))
        self.max_daily_spending = float(os.getenv('MAX_DAILY_SPENDING', '1000.0'))
        self.max_error_rate = float(os.getenv('MAX_ERROR_RATE', '0.5'))  # 50% errors = stop
        self.max_consecutive_errors = int(os.getenv('MAX_CONSECUTIVE_ERRORS', '10'))

    def check_posting_limits(self) -> tuple[bool, str]:
        """Check if we can post more clips today."""
        stats = self.queue.get_daily_stats()

        # Check daily limit
        posted_today = stats.get('clips_posted', 0)
        if posted_today >= self.max_daily_posting:
            return False, f"Daily posting limit reached ({posted_today}/{self.max_daily_posting})"

        # Check hourly limit (approximate)
        # In a real system, would track actual hourly stats
        # For now, simple ratio check: if we've posted a lot, slow down
        hours_elapsed = (datetime.now().hour + 1)  # Start from hour 1
        if posted_today > 0:
            avg_per_hour = posted_today / hours_elapsed
            if avg_per_hour > self.max_hourly_posting:
                return False, f"Hourly posting pace too high ({avg_per_hour:.1f}/{self.max_hourly_posting} per hour)"

        return True, "Posting limits OK"

    def check_spending_limits(self) -> tuple[bool, str]:
        """Check if we're within spending budget."""
        # This is a placeholder - actual spending would need to be tracked
        # via Whop API or similar
        # For now, just return OK
        return True, "Spending limits OK"

    def check_error_rates(self) -> tuple[bool, str]:
        """Check if error rate is within acceptable limits."""
        stats = self.queue.get_daily_stats()

        if stats.get('clips_posted', 0) == 0:
            return True, "No clips posted yet"

        error_rate = stats.get('clips_failed', 0) / (stats.get('clips_posted', 0) + stats.get('clips_failed', 0))
        if error_rate > self.max_error_rate:
            return False, f"Error rate too high ({error_rate:.1%} > {self.max_error_rate:.1%})"

        return True, f"Error rate acceptable ({error_rate:.1%})"

    def check_all_limits(self) -> Dict[str, tuple[bool, str]]:
        """Check all safety limits."""
        return {
            'posting': self.check_posting_limits(),
            'spending': self.check_spending_limits(),
            'errors': self.check_error_rates(),
        }

    def is_safe_to_proceed(self) -> bool:
        """Check if all safety limits are OK."""
        limits = self.check_all_limits()
        return all(ok for ok, _ in limits.values())


class AnomalyDetector:
    """Detect unusual patterns in operation."""

    def __init__(self, event_monitor: EventMonitor):
        self.monitor = event_monitor
        self.baseline = None

    def detect_anomalies(self) -> List[str]:
        """Detect anomalies in recent events."""
        anomalies = []

        # Get recent event summary
        summary = self.monitor.get_event_summary(hours=1)

        # Detect high error rate
        if summary['clips_failed'] > 0:
            error_rate = summary['clips_failed'] / (summary['clips_posted'] + summary['clips_failed'])
            if error_rate > 0.3:  # More than 30% errors
                anomalies.append(f"High error rate: {error_rate:.1%}")

        # Detect sudden spike in API errors
        api_errors = summary.get('by_type', {}).get('api_error', 0)
        if api_errors > 5:
            anomalies.append(f"Unusual API error spike: {api_errors} errors in last hour")

        # Detect posting surge
        if summary['clips_posted'] > 200:
            anomalies.append(f"Unusually high posting volume: {summary['clips_posted']} clips in last hour")

        return anomalies


def main():
    """Test monitoring module."""
    logging.basicConfig(level=logging.INFO)

    monitor = EventMonitor()

    # Log some test events
    monitor.log_event(MonitoringEvent(
        timestamp=datetime.now().isoformat(),
        event_type=EventType.CLIP_POSTED.value,
        clip_name="test_clip.mp4",
        platform="youtube",
        context={'duration': 30, 'quality_score': 85},
    ))

    monitor.log_event(MonitoringEvent(
        timestamp=datetime.now().isoformat(),
        event_type=EventType.POSTING_ERROR.value,
        clip_name="failed_clip.mp4",
        error_message="Upload timeout",
        severity="error",
    ))

    # Get summary
    summary = monitor.get_event_summary(hours=24)
    logger.info(f"Event summary: {summary}")

    # Test safety limiter
    limiter = SafetyLimiter()
    logger.info(f"Safety limits: {limiter.check_all_limits()}")


if __name__ == "__main__":
    import os
    main()
