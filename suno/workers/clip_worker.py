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
    Phase 8: Real Claude AI for hooks, retention, revenue, and ROI.
    """
    import os
    import inspect
    from suno.database import SessionLocal
    from suno.common.models import Clip, Membership, Campaign, CreatorProfile
    from suno.product.tier_helpers import can_create_clip_sync
    from suno.vantage.hook_engine import HookEngine
    from suno.vantage.retention_predictor import RetentionPredictor
    from suno.vantage.variant_engine import VariantEngine
    from suno.vantage.revenue_engine import RevenueEngine

    logger.info(f"[JOB_START] job_context=generate_clip, clip_id={clip_id}, account_id={account_id}, membership_id={membership_id}")

    db = SessionLocal()
    try:
        # Fetch clip
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            logger.error(f"[JOB_FAILED] clip_id={clip_id} reason=clip_not_found")
            return {"success": False, "error": "Clip not found"}

        # Fetch membership
        membership = db.query(Membership).filter(Membership.id == membership_id).first()
        if not membership:
            logger.error(f"[JOB_FAILED] clip_id={clip_id} reason=membership_not_found")
            clip.status = "failed"
            db.commit()
            return {"success": False, "error": "Membership not found"}

        # Worker gate: can_create_clip check (use sync version for RQ worker)
        logger.info(f"[VALIDATION_START] clip_id={clip_id}")
        can_create, reason = can_create_clip_sync(membership.user_id, db)

        # TASK 2: Hard fail if async function is used (safety guard)
        if inspect.iscoroutine(can_create):
            raise RuntimeError(f"[CRITICAL] Async function returned coroutine in worker context. clip_id={clip_id}")

        if not can_create:
            logger.info(f"[VALIDATION_FAILED] clip_id={clip_id} reason={reason}")
            clip.status = "failed"
            db.commit()
            return {"success": False, "error": reason}

        logger.info(f"[VALIDATION_PASSED] clip_id={clip_id}")

        # Fetch campaign and creator profile
        campaign = db.query(Campaign).filter(Campaign.id == clip.campaign_id).first()
        creator_profile = db.query(CreatorProfile).filter(
            CreatorProfile.account_id == account_id
        ).first()

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        total_ai_cost = 0.0

        logger.info(f"[PROCESSING_START] clip_id={clip_id}")

        # 1. Generate 10 hooks via Haiku
        hook_engine = HookEngine(api_key)
        hook_result = hook_engine.generate_hooks(clip, campaign, creator_profile)
        hooks = hook_result["hooks"]
        total_ai_cost += hook_result["cost_usd"]

        # 2. Predict retention via Haiku
        predictor = RetentionPredictor(api_key)
        retention = predictor.predict(clip, campaign, creator_profile)
        clip.predicted_watch_time = retention["predicted_watch_time"]
        clip.predicted_completion_rate = retention["predicted_completion_rate"]
        clip.predicted_dropoff_ms = retention["predicted_dropoff_ms"]
        total_ai_cost += retention["cost_usd"]

        # 3. Create variant records
        variant_engine = VariantEngine()
        variants = variant_engine.create_variants(clip.id, hooks, db)
        winner = variant_engine.select_winner(variants)

        # 4. Polish winner via Sonnet
        polish_result = hook_engine.polish_winner(winner.content, winner.hook_type, {
            "niche": creator_profile.niche if creator_profile else None,
            "brief": campaign.brief if campaign else "",
        })
        winner.content = polish_result["content"]
        winner.model_used = hook_engine.elite_model
        winner.quality_tier = "elite"
        total_ai_cost += polish_result["cost_usd"]

        # 5. Assign posting schedule
        variant_engine.assign_posting_schedule(variants, winner, cooldown_minutes=120)

        # 6. Estimate revenue + compute ROI
        revenue_engine = RevenueEngine()
        revenue = revenue_engine.estimate(clip, campaign, creator_profile)
        clip.predicted_views = revenue["predicted_views"]
        clip.estimated_value = revenue["estimated_value"]
        clip.ai_generation_cost_usd = round(total_ai_cost, 6)
        clip.ai_roi = revenue_engine.compute_roi(clip.estimated_value, clip.ai_generation_cost_usd)

        # 7. Real overall_score from retention + quality
        clip.overall_score = round((
            (winner.predicted_engagement or 0.5) * 0.25 +
            (clip.viral_score or 0.5) * 0.20 +
            retention["predicted_completion_rate"] * 0.30 +
            (clip.brand_alignment_score or 0.5) * 0.15 +
            (clip.monetization_score or 0.5) * 0.10
        ), 4)

        # 8. Set emotional trigger from winner
        clip.hook_score = winner.predicted_engagement or 0.5
        clip.emotional_trigger_type = winner.hook_type or "unknown"
        clip.relevance_score = 0.5
        clip.platform_fit_score = 0.5
        clip.duration_score = 0.5
        clip.brand_alignment_score = 0.5
        clip.social_proof_score = 0.5

        clip.status = "needs_review"
        clip.last_seen_at = datetime.utcnow()
        membership.clips_today_count += 1

        logger.info(f"[DB_COMMIT_START] clip_id={clip_id}")
        db.commit()
        logger.info(f"[DB_COMMIT_SUCCESS] clip_id={clip_id} status_written=needs_review")

        logger.info(
            f"[JOB_COMPLETE] clip_id={clip_id}, overall_score={clip.overall_score}, "
            f"predicted_views={clip.predicted_views}, estimated_value=${clip.estimated_value}, "
            f"ai_cost=${clip.ai_generation_cost_usd:.4f}, roi={clip.ai_roi}x"
        )
        # TASK 5: Minimal debug return (powerful for E2E validation)
        return {
            "clip_id": clip_id,
            "status": "completed",
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[JOB_FAILED] clip_id={clip_id} exception={type(e).__name__} message={str(e)}")
        # Try to set failed status (TASK 4: Verify DB write)
        try:
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if clip:
                clip.status = "failed"
                db.commit()
                logger.info(f"[DB_ROLLBACK_AND_FAIL_STATUS] clip_id={clip_id} status_written=failed")
            else:
                logger.error(f"[FAIL_STATUS_SKIPPED] clip_id={clip_id} reason=clip_not_found_in_exception_handler")
        except Exception as inner_e:
            logger.error(f"[FAIL_STATUS_FAILED] clip_id={clip_id} exception={type(inner_e).__name__}")
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
            Membership.status.in_(["active", "pending"]),
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
    from suno.common.enums import AccountStatus, MembershipLifecycle
    from suno.product.tier_helpers import can_create_clip_sync
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

            # Check can_create_clip (use sync version for RQ worker)
            can_create, reason = can_create_clip_sync(membership.user_id, db)
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
                Clip.status.notin_(["failed", "rejected", "expired"])
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
                status="queued",
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


def post_approved_clip_job(clip_id: int):
    """
    Post an approved clip and schedule its variants.
    Phase 8: DB-only scheduling (no live platform API calls).
    """
    from suno.database import SessionLocal
    from suno.common.models import Clip
    from suno.posting.clip_poster import PostingEngine

    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            logger.error(f"[POST_FAILED] Clip not found: {clip_id}")
            return {"success": False, "error": "Clip not found"}

        if clip.status != "approved":
            logger.error(f"[POST_FAILED] clip_id={clip_id}, status={clip.status}, expected=approved")
            clip.status = "failed"
            db.commit()
            return {"success": False, "error": f"Clip not approved: {clip.status}"}

        # Get variants
        variants = clip.variants
        if not variants:
            logger.error(f"[POST_FAILED] clip_id={clip_id}, no variants")
            clip.status = "failed"
            db.commit()
            return {"success": False, "error": "No variants"}

        # Schedule posting
        engine = PostingEngine()
        result = engine.schedule_clip_posting(clip, variants, db, cooldown_minutes=120)
        db.commit()

        logger.info(
            f"[CLIP_POSTED] clip_id={clip_id}, variants_scheduled={result['variants_scheduled']}"
        )

        return {"success": True, **result}

    except Exception as e:
        db.rollback()
        logger.error(f"[POST_FAILED] clip_id={clip_id}: {e}")
        try:
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if clip:
                clip.status = "failed"
                db.commit()
        except:
            pass
        raise

    finally:
        db.close()


def evaluate_variant_signal_job(variant_id: int):
    """
    Evaluate early performance of a posted variant and adapt sibling schedule.
    Enqueued at first_signal_at timestamp.
    Phase 8: Dynamic suppression of underperformers.
    """
    from suno.database import SessionLocal
    from suno.common.models import ClipVariant
    from suno.vantage.variant_engine import VariantEngine
    from suno.performance.learning_engine import PerformanceLearningEngine

    db = SessionLocal()
    try:
        variant = db.query(ClipVariant).filter(ClipVariant.id == variant_id).first()
        if not variant:
            logger.error(f"[SIGNAL_EVAL_FAILED] Variant not found: {variant_id}")
            return {"success": False, "error": "Variant not found"}

        clip = variant.clip
        if not clip:
            logger.error(f"[SIGNAL_EVAL_FAILED] Clip not found for variant {variant_id}")
            return {"success": False, "error": "Clip not found"}

        # Evaluate signal and suppress siblings if strong
        variant_engine = VariantEngine()
        result = variant_engine.evaluate_signal_and_adapt(variant_id, db)

        # Update creator profile based on signal
        learning = PerformanceLearningEngine()
        learning.update_creator_profile(clip.account_id, db)

        logger.info(
            f"[SIGNAL_EVALUATED] variant_id={variant_id}, signal_status={result['signal_status']}, "
            f"suppressed={result['suppressed_count']}"
        )

        return {"success": True, **result}

    except Exception as e:
        db.rollback()
        logger.error(f"[SIGNAL_EVAL_FAILED] variant_id={variant_id}: {e}")
        raise

    finally:
        db.close()


def update_creator_profile_job(account_id: int):
    """
    Update creator profile based on performance data.
    Enqueued async from performance endpoint.
    Phase 8: Learn winning hook types and clips.
    """
    from suno.database import SessionLocal
    from suno.performance.learning_engine import PerformanceLearningEngine

    db = SessionLocal()
    try:
        learning = PerformanceLearningEngine()
        profile = learning.update_creator_profile(account_id, db)

        logger.info(
            f"[PROFILE_JOB_COMPLETE] account_id={account_id}, "
            f"hook_style={profile.hook_style if profile else 'N/A'}"
        )

        return {"success": True, "account_id": account_id}

    except Exception as e:
        db.rollback()
        logger.error(f"[PROFILE_JOB_FAILED] account_id={account_id}: {e}")
        raise

    finally:
        db.close()
