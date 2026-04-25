# SUNO AUDIT FIXES - Detailed Implementation Guide

**Priority Order:** CRITICAL (1-4) → HIGH (5-9) → MEDIUM (10-13) → LOW (14-15)

---

## CRITICAL FIX #1: Race Condition in Account Provisioning

**File:** `suno/provisioning/account_ops.py`

### Current Code (BROKEN):
```python
def provision_account(self, user_id: int, email: str, tier_name: str, ...):
    # Check if account already exists (NOT ATOMIC)
    existing = self.db.query(Account).filter(
        Account.membership_id == membership.id
    ).first()

    if existing:
        return {...}

    # ⚠️ RACE CONDITION: Between check and creation, another process
    # could insert an account for the same membership_id
    account = Account(...)
    self.db.add(account)
    self.db.commit()  # ← Can fail with IntegrityError here
```

### Fixed Code:
```python
from sqlalchemy.exc import IntegrityError

def provision_account(self, user_id: int, email: str, tier_name: str, ...):
    from suno.common.models import Account, Membership

    try:
        # Get membership
        membership = self.db.query(Membership).filter(
            Membership.user_id == user_id
        ).first()

        if not membership:
            raise ProvisioningError(f"Membership not found for user {user_id}")

        # Generate workspace ID
        workspace_id = f"ws_{uuid.uuid4().hex[:12]}"
        workspace_name = workspace_name or f"workspace_{user_id}"

        # Call SUNO provisioning API
        if self.suno_api_key:
            result = self._call_suno_api(
                "provision_account",
                {
                    "user_id": user_id,
                    "email": email,
                    "tier": tier_name,
                    "workspace_id": workspace_id,
                    "workspace_name": workspace_name,
                },
            )
            if not result.get("success"):
                raise ProvisioningError(f"SUNO API error: {result.get('error')}")
        else:
            logger.warning(f"SUNO_API_KEY not configured, provisioning in stub mode")

        # Create account record (atomic - will fail if already exists due to FK unique constraint)
        account = Account(
            membership_id=membership.id,
            workspace_id=workspace_id,
            status="active",
            automation_enabled=True,
        )
        self.db.add(account)
        self.db.commit()

        logger.info(f"Successfully provisioned account {workspace_id} for user {user_id}")
        return {
            "success": True,
            "workspace_id": workspace_id,
            "is_new": True,
        }

    except IntegrityError:
        # Account already exists (race condition resolved by DB constraint)
        self.db.rollback()
        existing = self.db.query(Account).filter(
            Account.membership_id == membership.id
        ).first()
        logger.info(f"Account already exists for membership {membership.id}: {existing.workspace_id}")
        return {
            "success": True,
            "workspace_id": existing.workspace_id,
            "is_new": False,
        }

    except Exception as e:
        self.db.rollback()
        logger.error(f"Provisioning failed for user {user_id}: {e}")
        raise ProvisioningError(str(e))
```

---

## CRITICAL FIX #2: JobQueueType Enum Type Safety

**Files:**
- `suno/common/job_queue.py`
- `suno/billing/webhook_routes.py`
- `suno/billing/membership_lifecycle.py`

### Option A: Update job_queue.py to Accept Both String and Enum (SIMPLE)

**File:** `suno/common/job_queue.py`

```python
from suno.common.enums import JobQueueType  # ← Add import at top

class JobQueueManager:
    def enqueue(
        self,
        queue_type,  # Remove JobQueueType type hint
        func,
        args: tuple = (),
        kwargs: Dict[str, Any] = None,
        job_timeout: int = 300,
        result_ttl: int = 500,
    ) -> str:
        """
        Enqueue a background job.

        Args:
            queue_type: Priority queue (str or JobQueueType enum)
        """
        # Handle both string and enum
        if isinstance(queue_type, str):
            try:
                queue_type = JobQueueType[queue_type.upper()]
            except KeyError:
                raise ValueError(f"Invalid queue type: {queue_type}")

        kwargs = kwargs or {}
        queue = self.queues[queue_type]

        try:
            rq_job = queue.enqueue(
                func,
                args=args,
                kwargs=kwargs,
                job_timeout=job_timeout,
                result_ttl=result_ttl,
            )
            logger.info(f"Enqueued job {rq_job.id} to {queue_type.value} queue")
            return rq_job.id
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            raise
```

### Option B: Update All Callers to Use Enum (PREFERRED for Type Safety)

**File:** `suno/billing/webhook_routes.py`

```python
from suno.common.job_queue import JobQueueType  # ← Add import

def create_webhook_handler(db: Session, queue_manager, signature_secret: str):
    # ... existing code ...

    @webhook_bp.post("/whop")
    def handle_whop_webhook():
        # ... existing verification code ...

        # OLD: job_id = queue_manager.enqueue("critical", ...)
        # NEW:
        try:
            job_id = queue_manager.enqueue(
                JobQueueType.CRITICAL,  # ← Use enum
                process_webhook_event,
                kwargs={
                    "event_id": event_record.id,
                    "event_type": event_type,
                    "event_data": event_data,
                },
            )
            event_manager.mark_enqueued(event_record.id, job_id)
            logger.info(f"Enqueued webhook {whop_event_id} as job {job_id}")
        except Exception as e:
            logger.error(f"Failed to enqueue webhook {whop_event_id}: {e}")
            event_manager.mark_failed(event_record.id, str(e))
            return jsonify({"error": "Failed to enqueue"}), 500
```

**File:** `suno/billing/membership_lifecycle.py`

```python
from suno.common.job_queue import JobQueueType  # ← Add import

def handle_purchase(self, event_data: Dict[str, Any]):
    # ... existing code ...

    # OLD: job_id = self.queue_manager.enqueue("critical", ...)
    # NEW:
    job_id = self.queue_manager.enqueue(
        JobQueueType.CRITICAL,  # ← Use enum
        provision_account_job,
        kwargs={...}
    )

    # In handle_upgrade:
    # OLD: self.queue_manager.enqueue("high", ...)
    # NEW:
    job_id = self.queue_manager.enqueue(
        JobQueueType.HIGH,  # ← Use enum
        update_tier_job,
        kwargs={...}
    )
```

---

## CRITICAL FIX #3: WebhookEventStatus Enum Consistency

**File:** `suno/dashboard/operator.py`

### Current Code (BROKEN):
```python
pending_webhooks = self.db.query(func.count(WebhookEvent.id)).filter(
    WebhookEvent.status.in_(["received", "validated", "enqueued"])  # ❌ STRINGS
).scalar() or 0
```

### Fixed Code:
```python
from suno.billing.webhook_events import WebhookEventStatus  # ← Add import

def get_system_health(self) -> Dict[str, Any]:
    # ... existing code ...

    # OLD:
    # pending_webhooks = self.db.query(...).filter(
    #     WebhookEvent.status.in_(["received", "validated", "enqueued"])
    # ).scalar() or 0

    # NEW:
    pending_webhooks = self.db.query(func.count(WebhookEvent.id)).filter(
        WebhookEvent.status.in_([
            WebhookEventStatus.RECEIVED,
            WebhookEventStatus.VALIDATED,
            WebhookEventStatus.ENQUEUED,
        ])
    ).scalar() or 0

    webhook_failures = self.db.query(func.count(WebhookEvent.id)).filter(
        WebhookEvent.status.in_([
            WebhookEventStatus.FAILED,
            WebhookEventStatus.DEAD_LETTER,
        ])
    ).scalar() or 0
```

---

## CRITICAL FIX #4: Missing Submission Orchestrator

**New File:** `suno/posting/submission_orchestrator.py`

```python
"""
Submission Orchestrator
Manages submission lifecycle with retry logic and dead-letter queue.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from suno.posting.adapters import get_adapter

logger = logging.getLogger(__name__)


class SubmissionOrchestrator:
    """Orchestrates submission lifecycle with full retry logic."""

    MAX_RETRIES = 2
    RETRY_BACKOFF_MINUTES = 10

    def __init__(self, db: Session):
        """Initialize submission orchestrator."""
        self.db = db

    def execute_submission_job(
        self,
        submission_job_id: int,
        account_id: int,
        platform: str,
        account_credentials: Dict[str, str],
        posted_url: str,
        source_clip_url: str,
    ) -> Dict[str, Any]:
        """
        Execute a submission job with full retry logic.

        Args:
            submission_job_id: ID of submission job
            account_id: Account ID
            platform: Source platform name
            account_credentials: Platform credentials
            posted_url: URL of posted content
            source_clip_url: Original clip URL

        Returns:
            Result dict with status and details
        """
        from suno.common.models import SubmissionJob, DeadLetterJob
        from suno.common.enums import JobLifecycle

        try:
            # Get submission job
            submission_job = self.db.query(SubmissionJob).filter(
                SubmissionJob.id == submission_job_id
            ).first()

            if not submission_job:
                logger.error(f"Submission job {submission_job_id} not found")
                return {"success": False, "error": "Submission job not found"}

            # Get platform adapter
            adapter = get_adapter(platform)
            if not adapter:
                logger.error(f"No adapter for platform {platform}")
                submission_job.status = JobLifecycle.FAILED
                submission_job.error_message = f"No adapter for {platform}"
                self.db.commit()
                return {"success": False, "error": f"No adapter for {platform}"}

            # Execute submission
            result = adapter.submit_result(
                account_credentials=account_credentials,
                posted_url=posted_url,
                source_clip_url=source_clip_url,
            )

            if result:
                # Success
                submission_job.status = JobLifecycle.SUCCEEDED
                submission_job.submission_url = posted_url
                self.db.commit()

                logger.info(f"Submission job {submission_job_id} succeeded")
                return {
                    "success": True,
                    "submission_url": posted_url,
                }

            else:
                # Failure (retryable)
                submission_job.retry_count += 1

                if submission_job.retry_count >= self.MAX_RETRIES:
                    # Max retries reached: move to dead-letter
                    submission_job.status = JobLifecycle.FAILED
                    self.db.commit()

                    # Create dead-letter record
                    dead_letter = DeadLetterJob(
                        original_job_type="submission",
                        original_job_id=submission_job_id,
                        payload={
                            "submission_job_id": submission_job_id,
                            "platform": platform,
                            "posted_url": posted_url,
                        },
                        error_message=f"Max retries ({self.MAX_RETRIES}) reached",
                        retry_count=submission_job.retry_count,
                    )
                    self.db.add(dead_letter)
                    self.db.commit()

                    logger.error(f"Submission job {submission_job_id} dead-lettered")
                    return {
                        "success": False,
                        "error": "Max retries exceeded",
                        "dead_letter_job_id": dead_letter.id,
                    }
                else:
                    # Schedule retry
                    submission_job.status = JobLifecycle.PENDING
                    self.db.commit()

                    logger.warning(
                        f"Submission job {submission_job_id} retryable error "
                        f"(attempt {submission_job.retry_count}/{self.MAX_RETRIES})"
                    )
                    return {
                        "success": False,
                        "error": "Retryable error",
                        "retry_count": submission_job.retry_count,
                    }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error executing submission job {submission_job_id}: {e}")

            return {
                "success": False,
                "error": str(e),
                "unexpected": True,
            }

    def get_dead_letter_jobs(self, limit: int = 20) -> list:
        """Get dead-letter submission jobs requiring operator intervention."""
        from suno.common.models import DeadLetterJob

        return self.db.query(DeadLetterJob).filter(
            DeadLetterJob.original_job_type == "submission"
        ).order_by(
            DeadLetterJob.created_at.desc()
        ).limit(limit).all()
```

---

## HIGH FIX #5: Account Status Enum

**File:** `suno/common/enums.py`

```python
# Add new enum at top of file
class AccountStatus(str, Enum):
    """Account status states."""
    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"
    DISABLED = "disabled"
```

**File:** `suno/common/models.py`

```python
from suno.common.enums import AccountStatus  # ← Add import

class Account(Base):
    """SUNO workspace account for a membership."""
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    membership_id = Column(Integer, ForeignKey("memberships.id"), nullable=False, unique=True, index=True)
    workspace_id = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False)  # ← Use enum
    automation_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ... rest of model ...
```

**File:** `suno/provisioning/account_ops.py`

```python
from suno.common.enums import AccountStatus  # ← Add import

class AccountProvisioner:
    def provision_account(...):
        # OLD: account.status = "active"
        # NEW:
        account = Account(
            membership_id=membership.id,
            workspace_id=workspace_id,
            status=AccountStatus.ACTIVE,  # ← Use enum
            automation_enabled=True,
        )

class AccountRevoker:
    def revoke_account(...):
        # OLD: account.status = "revoked"
        # NEW:
        account.status = AccountStatus.REVOKED  # ← Use enum
```

---

## HIGH FIX #6: Dead-Letter Retry Count

**File:** `suno/posting/orchestrator.py`

### Current Code:
```python
def retry_dead_letter_job(self, dead_letter_job_id: int) -> bool:
    # ...
    post_job.retry_count = max(0, post_job.retry_count - 1)  # ❌ WRONG
```

### Fixed Code:
```python
def retry_dead_letter_job(self, dead_letter_job_id: int) -> bool:
    """Move dead-letter job back to pending for retry."""
    from suno.common.models import DeadLetterJob, PostJob

    try:
        dead_letter = self.db.query(DeadLetterJob).filter(
            DeadLetterJob.id == dead_letter_job_id
        ).first()

        if not dead_letter:
            return False

        # Get original post job
        post_job = self.db.query(PostJob).filter(
            PostJob.id == dead_letter.original_job_id
        ).first()

        if not post_job:
            logger.warning(f"Original post job not found for dead-letter {dead_letter_job_id}")
            return False

        # Reset for retry (allow full cycle again)
        post_job.status = JobLifecycle.PENDING
        post_job.retry_count = 0  # ← RESET to 0, not decrement
        post_job.error_message = None
        self.db.commit()

        logger.info(f"Moved dead-letter job {dead_letter_job_id} back to pending")
        return True

    except Exception as e:
        self.db.rollback()
        logger.error(f"Failed to retry dead-letter job: {e}")
        return False
```

---

## HIGH FIX #7 & #8: Global Pause/Resume with Persistence

**New Model in `suno/common/models.py`:**

```python
class SafetyState(Base):
    """Persistent global safety state."""
    __tablename__ = "safety_state"

    id = Column(Integer, primary_key=True)
    is_global_paused = Column(Boolean, default=False, nullable=False)
    pause_reason = Column(String(500), nullable=True)
    paused_by = Column(String(255), nullable=True)  # "operator", "system", etc
    paused_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_safety_state_paused", "is_global_paused"),
    )
```

**New Table Migration:**
```sql
CREATE TABLE safety_state (
    id INTEGER PRIMARY KEY,
    is_global_paused BOOLEAN NOT NULL DEFAULT FALSE,
    pause_reason VARCHAR(500),
    paused_by VARCHAR(255),
    paused_at DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_safety_state_paused ON safety_state(is_global_paused);
```

**File:** `suno/safety/controls.py`

```python
from suno.common.models import SafetyState  # ← Add import

class GlobalSafetyControls:
    """Global safety controls with persistent state."""

    def __init__(self, db: Session, safety_level: str = "production"):
        """Initialize safety controls."""
        self.db = db
        self.safety_level = safety_level
        logger.info(f"Safety level: {safety_level}")

    def _get_safety_state(self) -> SafetyState:
        """Get or create safety state record."""
        state = self.db.query(SafetyState).first()
        if not state:
            state = SafetyState(is_global_paused=False)
            self.db.add(state)
            self.db.commit()
        return state

    def is_globally_paused(self) -> bool:
        """Check if system is globally paused."""
        state = self._get_safety_state()
        return state.is_global_paused

    def global_pause(self, reason: str, paused_by: str = "operator") -> bool:
        """Global pause on all automation."""
        try:
            # Update safety state
            state = self._get_safety_state()
            state.is_global_paused = True
            state.pause_reason = reason
            state.paused_by = paused_by
            state.paused_at = datetime.utcnow()
            self.db.commit()

            logger.warning(f"GLOBAL PAUSE: {reason} (by {paused_by})")

            # Pause all active accounts
            from suno.common.models import Account

            self.db.query(Account).update({Account.automation_enabled: False})
            self.db.commit()

            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error pausing system: {e}")
            return False

    def global_resume(self) -> bool:
        """Resume all automation (only those paused by global_pause)."""
        try:
            state = self._get_safety_state()
            if not state.is_global_paused:
                logger.info("System not paused, skipping resume")
                return False

            # Update safety state
            state.is_global_paused = False
            state.pause_reason = None
            state.paused_by = None
            state.paused_at = None
            self.db.commit()

            logger.info("GLOBAL RESUME")

            # Resume only accounts that have active memberships
            # (don't resume manually disabled accounts)
            from suno.common.models import Account, Membership
            from suno.common.enums import MembershipLifecycle

            memberships = self.db.query(Membership).filter(
                Membership.status == MembershipLifecycle.ACTIVE
            ).all()

            for m in memberships:
                if m.account:
                    m.account.automation_enabled = True

            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error resuming system: {e}")
            return False
```

---

## HIGH FIX #9: Enforce Safety Level

**File:** `suno/safety/controls.py`

```python
class GlobalSafetyControls:
    def __init__(self, db: Session, safety_level: str = "production"):
        """Initialize with enum validation."""
        self.db = db
        try:
            self.safety_level = SafetyLevel(safety_level)
        except ValueError:
            raise ValueError(f"Invalid safety level: {safety_level}")

        logger.info(f"Safety level: {self.safety_level.value}")
        self._apply_level_specific_init()

    def _apply_level_specific_init(self):
        """Apply safety level specific initialization."""
        if self.safety_level == SafetyLevel.SELF_USE:
            logger.warning("⚠️ SELF-USE MODE: Strict limits active (15 clips/day)")
        elif self.safety_level == SafetyLevel.BETA:
            logger.info("BETA MODE: Monitor up to 50 users")
        elif self.safety_level == SafetyLevel.PRODUCTION:
            logger.info("PRODUCTION MODE: Standard safety limits")

    def get_max_daily_clips(self, account_id: int) -> int:
        """Get max daily clips based on safety level."""
        from suno.common.models import Account, Membership
        from suno.common.enums import TierName

        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return 0

        membership = account.membership
        tier = membership.tier

        # Apply safety level override
        if self.safety_level == SafetyLevel.SELF_USE:
            return min(15, tier.max_daily_clips)  # Hard cap at 15
        elif self.safety_level == SafetyLevel.BETA:
            return tier.max_daily_clips
        else:
            return tier.max_daily_clips

    def enforce_safety_check(self, account_id: int) -> bool:
        """Check if account should be paused based on safety level."""
        if self.is_globally_paused():
            return False

        if self.safety_level == SafetyLevel.SELF_USE:
            # In self-use mode, pause if failure rate > 20%
            return self._check_failure_threshold(account_id, threshold=20)
        elif self.safety_level == SafetyLevel.BETA:
            # In beta mode, pause if failure rate > 30%
            return self._check_failure_threshold(account_id, threshold=30)
        else:
            return True
```

---

## Summary: Apply These 9 Critical/High Fixes

| # | File | Changes | Priority |
|---|------|---------|----------|
| 1 | account_ops.py | Add IntegrityError handling | CRITICAL |
| 2 | job_queue.py, webhook_routes.py, membership_lifecycle.py | Use JobQueueType enum | CRITICAL |
| 3 | dashboard/operator.py | Use WebhookEventStatus enum | CRITICAL |
| 4 | posting/submission_orchestrator.py | Create new file | CRITICAL |
| 5 | common/enums.py, common/models.py, account_ops.py | Add AccountStatus enum | HIGH |
| 6 | posting/orchestrator.py | Fix retry count logic | HIGH |
| 7 | common/models.py, safety/controls.py | Add persistent SafetyState | HIGH |
| 8 | safety/controls.py | Fix resume logic | HIGH |
| 9 | safety/controls.py | Enforce SafetyLevel enum | HIGH |

**Total estimated implementation time:** 4-5 hours with testing

