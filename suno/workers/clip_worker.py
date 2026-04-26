"""
Clip Worker Functions
Background jobs for clip generation, daily reset, and automation loop.
"""

import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


def generate_clip_job(clip_id: int, account_id: int, membership_id: int):
    """
    Background job to generate clip scores and set status to NEEDS_REVIEW.
    Phase 7: Stub scores (all 0.5).
    """
    from suno.database import SessionLocal
    from suno.common.models import Clip, Membership
    from suno.common.enums import ClipLifecycle
    from suno.product.tier_helpers import can_create_clip

    db = SessionLocal()
    try:
        # Fetch clip
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            logger.error(f"[CLIP_FAILED] Clip not found: {clip_id}")
            return {"success": False, "error": "Clip not found"}

        # Fetch membership
        membership = db.query(Membership).filter(Membership.id == membership_id).first()
        if not membership:
            logger.error(f"[CLIP_FAILED] Membership not found: {membership_id}")
            clip.status = ClipLifecycle.FAILED
            db.commit()
            return {"success": False, "error": "Membership not found"}

        # Worker gate: can_create_clip check
        can_create, reason = can_create_clip(membership.user_id, db)
        if not can_create:
            logger.info(f"[CLIP_BLOCKED] clip_id={clip_id}: {reason}")
            clip.status = ClipLifecycle.FAILED
            db.commit()
            return {"success": False, "error": reason}

        # Generate stub scores (Phase 7: all 0.5)
        scores = {
            "hook_score": 0.5,
            "relevance_score": 0.5,
            "platform_fit_score": 0.5,
            "duration_score": 0.5,
            "brand_alignment_score": 0.5,
            "viral_score": 0.5,
            "social_proof_score": 0.5,
            "overall_score": 0.5,
            "monetization_score": 0.5,
        }

        # Apply scores
        clip.hook_score = scores["hook_score"]
        clip.relevance_score = scores["relevance_score"]
        clip.platform_fit_score = scores["platform_fit_score"]
        clip.duration_score = scores["duration_score"]
        clip.brand_alignment_score = scores["brand_alignment_score"]
        clip.viral_score = scores["viral_score"]
        clip.social_proof_score = scores["social_proof_score"]
        clip.overall_score = scores["overall_score"]
        clip.monetization_score = scores["monetization_score"]
        clip.emotional_trigger_type = "unknown"
        clip.status = ClipLifecycle.NEEDS_REVIEW
        clip.last_seen_at = datetime.utcnow()

        # Increment membership.clips_today_count
        membership.clips_today_count += 1

        db.commit()
        logger.info(f"[CLIP_GENERATED] clip_id={clip_id}, account_id={account_id}, clips_today={membership.clips_today_count}, overall_score=0.5")
        return {
            "success": True,
            "clip_id": clip_id,
            "status": ClipLifecycle.NEEDS_REVIEW.value,
            "overall_score": 0.5
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[CLIP_FAILED] clip_id={clip_id}: {e}")
        # Try to set failed status
        try:
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if clip:
                clip.status = ClipLifecycle.FAILED
                db.commit()
        except:
            pass
        raise

    finally:
        db.close()


def reset_daily_clips_job():
    """
    Reset clips_today_count for all ACTIVE/PENDING memberships with count > 0.
    Scheduled daily job.
    """
    from suno.database import SessionLocal
    from suno.common.models import Membership
    from suno.common.enums import MembershipLifecycle

    db = SessionLocal()
    try:
        memberships = db.query(Membership).filter(
            Membership.status.in_([MembershipLifecycle.ACTIVE, MembershipLifecycle.PENDING]),
            Membership.clips_today_count > 0
        ).all()

        for membership in memberships:
            membership.clips_today_count = 0

        db.commit()
        logger.info(f"[DAILY_RESET] Reset {len(memberships)} memberships")
        return {"success": True, "reset_count": len(memberships)}

    except Exception as e:
        db.rollback()
        logger.error(f"[DAILY_RESET_FAILED] {e}")
        raise

    finally:
        db.close()


def run_automation_loop():
    """
    Automation loop: create clips for all automation_enabled=True accounts.
    Scheduled periodic job (Phase 8: configurable frequency).
    """
    from suno.database import SessionLocal
    from suno.common.models import Account, Membership, Campaign, Clip
    from suno.common.enums import AccountStatus, MembershipLifecycle, ClipLifecycle
    from suno.product.tier_helpers import can_create_clip
    from suno.common.job_queue import JobQueueManager, JobQueueType

    db = SessionLocal()
    queue_manager = JobQueueManager()
    accounts_found = 0
    jobs_enqueued = 0

    try:
        # Fetch all automation_enabled accounts with ACTIVE status
        accounts = db.query(Account).filter(
            Account.automation_enabled == True,
            Account.status == AccountStatus.ACTIVE
        ).all()

        accounts_found = len(accounts)
        logger.info(f"[AUTOMATION_LOOP] Found {accounts_found} automation-enabled accounts")

        for account in accounts:
            membership = account.membership
            if not membership:
                logger.info(f"[AUTOMATION_SKIPPED] account_id={account.id} reason=no_membership")
                continue

            # Check can_create_clip
            can_create, reason = can_create_clip(membership.user_id, db)
            if not can_create:
                logger.info(f"[AUTOMATION_SKIPPED] account_id={account.id} reason={reason}")
                continue

            # Get available campaign
            campaign = db.query(Campaign).filter(
                Campaign.available == True
            ).first()

            if not campaign:
                logger.info(f"[AUTOMATION_SKIPPED] account_id={account.id} reason=no_campaign")
                continue

            # Check for duplicate in progress
            existing_clip = db.query(Clip).filter(
                Clip.campaign_id == campaign.id,
                Clip.account_id == account.id,
                Clip.status.notin_([ClipLifecycle.FAILED, ClipLifecycle.REJECTED, ClipLifecycle.EXPIRED])
            ).first()

            if existing_clip:
                logger.info(f"[AUTOMATION_SKIPPED] account_id={account.id} reason=duplicate_in_progress")
                continue

            # Create stub clip
            clip = Clip(
                campaign_id=campaign.id,
                account_id=account.id,
                source_url=f"stub://{uuid.uuid4().hex}",
                source_platform="generated",
                title=f"Automation clip for {campaign.title}",
                description="",
                content_hash=uuid.uuid4().hex,
                status=ClipLifecycle.QUEUED,
                clip_metadata={
                    "automation": True,
                    "generated_at": datetime.utcnow().isoformat(),
                }
            )
            db.add(clip)
            db.flush()
            clip_id = clip.id

            # Enqueue job
            job_id = queue_manager.enqueue(
                JobQueueType.NORMAL,
                generate_clip_job,
                kwargs={
                    "clip_id": clip_id,
                    "account_id": account.id,
                    "membership_id": membership.id,
                }
            )
            jobs_enqueued += 1
            logger.info(f"[AUTOMATION_JOB_ENQUEUED] clip_id={clip_id}, job_id={job_id}, account_id={account.id}")

        db.commit()
        logger.info(f"[AUTOMATION_LOOP] accounts_found={accounts_found}, jobs_enqueued={jobs_enqueued}")
        return {
            "success": True,
            "accounts_found": accounts_found,
            "jobs_enqueued": jobs_enqueued
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[AUTOMATION_LOOP_FAILED] {e}")
        raise

    finally:
        db.close()
