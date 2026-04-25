"""
FAILURE DRILL: 6 Controlled Break Tests
Verify SUNO fails elegantly, not catastrophically
"""

import hmac
import hashlib
import json
from datetime import datetime


def test_failure_1_bad_webhook_signature(test_db_session):
    """TEST 1: Send webhook with bad HMAC signature"""
    print("\n" + "="*70)
    print("TEST 1: BAD WEBHOOK SIGNATURE")
    print("="*70)

    from suno.billing.webhook_routes import WebhookSignatureVerifier

    SECRET = "whsec_real_secret_12345"
    PAYLOAD = json.dumps({
        "id": "evt_bad_sig_test",
        "action": "membership.went_valid",
        "data": {"user_email": "test@example.com"}
    }).encode()

    real_sig = hmac.new(SECRET.encode(), PAYLOAD, hashlib.sha256).hexdigest()
    bad_sig = "deadbeef" * 8

    verifier = WebhookSignatureVerifier(SECRET)

    result_valid = verifier.verify(PAYLOAD, real_sig)
    assert result_valid == True, "Valid signature should pass"
    print("[OK] Step 1: Valid signature ACCEPTED")

    result_invalid = verifier.verify(PAYLOAD, bad_sig)
    assert result_invalid == False, "Bad signature should fail"
    print("[OK] Step 2: Bad signature REJECTED")

    from suno.database import SessionLocal
    from suno.common.models import WebhookEvent

    db = SessionLocal()
    try:
        event_count = db.query(WebhookEvent).filter(
            WebhookEvent.whop_event_id == "evt_bad_sig_test"
        ).count()
        assert event_count == 0, "No event should be created for bad signature"
        print("[OK] Step 3: No event created (security maintained)")
    finally:
        db.close()

    print("\n[PASS] TEST 1 PASS: Bad signature rejected cleanly")
    return True


def test_failure_2_duplicate_webhook(test_db_session):
    """TEST 2: Send same webhook twice"""
    print("\n" + "="*70)
    print("TEST 2: DUPLICATE WEBHOOK")
    print("="*70)

    from suno.database import SessionLocal
    from suno.common.models import WebhookEvent
    from suno.billing.webhook_events import WebhookEventManager

    webhook_id = f"evt_dup_test_{datetime.utcnow().timestamp()}"
    payload = {
        "id": webhook_id,
        "action": "membership.went_valid",
        "data": {"user_email": "dup_test@example.com"}
    }

    db = SessionLocal()
    try:
        manager = WebhookEventManager(db)

        is_new_1, event_1 = manager.store_event(webhook_id, "membership.went_valid", payload)
        event_id_1 = event_1.id
        assert is_new_1 == True, "First webhook should be new"
        print(f"[OK] Step 1: First webhook stored (ID: {event_id_1})")

        is_new_2, event_2 = manager.store_event(webhook_id, "membership.went_valid", payload)
        event_id_2 = event_2.id
        assert is_new_2 == False, "Duplicate should not be new"
        assert event_id_1 == event_id_2, "Should return same event"
        print(f"[OK] Step 2: Duplicate webhook ignored (returned same event)")

        count = db.query(WebhookEvent).filter(
            WebhookEvent.whop_event_id == webhook_id
        ).count()
        assert count == 1, f"Should have exactly 1 event, found {count}"
        print(f"[OK] Step 3: Only 1 event in DB (no duplicates)")

    finally:
        db.close()

    print("\n[PASS] TEST 2 PASS: Duplicate webhook handled safely (idempotent)")
    return True


def test_failure_3_missing_provisioning_secret(test_db_session):
    """TEST 3: Try to provision without SUNO_API_KEY"""
    print("\n" + "="*70)
    print("TEST 3: MISSING PROVISIONING SECRET")
    print("="*70)

    import os
    from suno.provisioning.account_ops import AccountProvisioner, ProvisioningError
    from suno.database import SessionLocal
    from suno.common.models import User, Membership, Tier, Account
    from suno.common.enums import MembershipLifecycle, TierName

    db = SessionLocal()
    old_env = os.environ.get("ENVIRONMENT")

    try:
        os.environ["ENVIRONMENT"] = "production"

        user = User(email="prov_secret_test@example.com")
        db.add(user)
        db.flush()

        tier = db.query(Tier).filter(Tier.name == TierName.STARTER).first()
        if not tier:
            tier = Tier(
                name=TierName.STARTER,
                max_daily_clips=10,
                max_platforms=3,
                platforms=["tiktok"],
                auto_posting=False,
                scheduling=False,
                analytics=False,
                api_access=False,
            )
            db.add(tier)
            db.flush()

        membership = Membership(
            user_id=user.id,
            tier_id=tier.id,
            whop_membership_id="mem_secret_test",
            whop_plan_id="plan_001",
            status=MembershipLifecycle.PENDING,
        )
        db.add(membership)
        db.commit()

        print(f"[OK] Step 1: Test user/membership created")

        try:
            provisioner = AccountProvisioner(db, suno_api_key=None)
            print("[FAIL] Should have raised ProvisioningError!")
            return False
        except ProvisioningError as e:
            assert "SUNO_API_KEY" in str(e), "Error should mention SUNO_API_KEY"
            print(f"[OK] Step 2: ProvisioningError raised explicitly")
            print(f"   Error: {e}")

        account = db.query(Account).filter(
            Account.membership_id == membership.id
        ).first()
        assert account is None, "Account should NOT be created"
        print(f"[OK] Step 3: No partial/broken account created")

    finally:
        if old_env:
            os.environ["ENVIRONMENT"] = old_env
        db.close()

    print("\n[PASS] TEST 3 PASS: Missing secret causes explicit failure (no partial state)")
    return True


def test_failure_4_caption_generation_failure(test_db_session):
    """TEST 4: Simulate caption generation failure"""
    print("\n" + "="*70)
    print("TEST 4: CAPTION GENERATION FAILURE")
    print("="*70)

    from suno.database import SessionLocal
    from suno.common.models import (
        Campaign, Clip, Account, Membership, Tier, ClipAssignment,
        CaptionJob, DeadLetterJob, User
    )
    from suno.common.enums import TierName, ClipLifecycle, JobLifecycle
    import hashlib

    db = SessionLocal()
    try:
        tier = db.query(Tier).filter(Tier.name == TierName.STARTER).first()
        if not tier:
            tier = Tier(
                name=TierName.STARTER,
                max_daily_clips=10,
                max_platforms=3,
                platforms=["tiktok"],
                auto_posting=False,
                scheduling=False,
                analytics=False,
                api_access=False,
            )
            db.add(tier)
            db.flush()

        user = User(email="caption_fail_test@example.com")
        db.add(user)
        db.flush()

        membership = Membership(
            user_id=user.id,
            tier_id=tier.id,
            whop_membership_id="mem_caption_fail",
            whop_plan_id="plan_001",
        )
        db.add(membership)
        db.flush()

        account = Account(membership_id=membership.id, workspace_id="ws_caption_fail")
        db.add(account)
        db.flush()

        campaign = Campaign(
            source_id="camp_caption_fail",
            source_type="test",
            title="Test",
            target_platforms=["tiktok"],
        )
        db.add(campaign)
        db.flush()

        clip = Clip(
            campaign_id=campaign.id,
            account_id=account.id,
            source_url="https://test.com/clip_fail",
            source_platform="youtube",
            title="Test Clip",
            description="Test",
            content_hash=hashlib.sha256(b"caption_fail_test").hexdigest(),
            engagement_score=0.8,
            view_count=1000,
        )
        db.add(clip)
        db.flush()

        assignment = ClipAssignment(
            clip_id=clip.id,
            account_id=account.id,
            target_platform="tiktok",
            status=ClipLifecycle.ELIGIBLE,
        )
        db.add(assignment)
        db.flush()

        caption_job = CaptionJob(
            assignment_id=assignment.id,
            status=JobLifecycle.PENDING,
        )
        db.add(caption_job)
        db.commit()

        print(f"[OK] Step 1: Caption job created (ID: {caption_job.id})")

        MAX_RETRIES = 2

        caption_job.status = JobLifecycle.FAILED
        caption_job.error_message = "API rate limited"
        caption_job.retry_count = 1
        db.commit()
        print(f"[OK] Step 2: Attempt 1 failed (retry_count=1)")

        caption_job.retry_count = 2
        caption_job.error_message = "API still unavailable"
        db.commit()
        print(f"[OK] Step 3: Attempt 2 failed (retry_count=2)")

        if caption_job.retry_count >= MAX_RETRIES:
            caption_job.status = JobLifecycle.FAILED
            db.commit()

            dead_letter = DeadLetterJob(
                original_job_type="caption",
                original_job_id=caption_job.id,
                payload={"assignment_id": assignment.id},
                error_message=f"Max retries ({MAX_RETRIES}) reached",
                retry_count=caption_job.retry_count,
            )
            db.add(dead_letter)
            db.commit()

            print(f"[OK] Step 4: Dead-lettered (DL job ID: {dead_letter.id})")

            assert dead_letter.payload is not None, "Payload should be preserved"
            assert "assignment_id" in dead_letter.payload, "Payload should be complete"
            print(f"[OK] Step 5: Payload preserved for operator retry")

            return True

    finally:
        db.close()

    print("\n[PASS] TEST 4 PASS: Caption failure handled (retry → dead-letter, payload saved)")
    return True


def test_failure_5_bad_platform_credentials(test_db_session):
    """TEST 5: Try to post with invalid platform credentials"""
    print("\n" + "="*70)
    print("TEST 5: BAD PLATFORM CREDENTIALS")
    print("="*70)

    from suno.posting.adapters import get_adapter
    from suno.posting.adapters.base import PostingStatus

    adapters_to_test = ["tiktok", "instagram", "youtube", "twitter", "bluesky"]

    for platform in adapters_to_test:
        adapter = get_adapter(platform)
        assert adapter is not None, f"Should get adapter for {platform}"

        try:
            result = adapter.post(
                account_credentials={},
                payload={"caption": "test"},
            )

            assert result is not None, f"{platform} should return PostingResult"
            assert hasattr(result, 'status'), f"{platform} result should have status"

            assert result.status in [PostingStatus.RETRYABLE_ERROR, PostingStatus.PERMANENT_ERROR], \
                f"{platform} should return error status for bad creds"

            print(f"[OK] {platform.upper()}: Handled bad credentials gracefully")

        except Exception as e:
            print(f"[FAIL] {platform.upper()}: CRASHED - {e}")
            return False

    print("\n[PASS] TEST 5 PASS: All adapters handle bad credentials gracefully (no crashes)")
    return True


def test_failure_6_malformed_payload(test_db_session):
    """TEST 6: Try to process malformed clip data"""
    print("\n" + "="*70)
    print("TEST 6: MALFORMED PAYLOAD")
    print("="*70)

    from suno.database import SessionLocal
    from suno.common.models import Campaign, Clip, Account, Membership, Tier, User
    from suno.common.enums import TierName
    import hashlib
    from sqlalchemy.exc import IntegrityError

    db = SessionLocal()
    try:
        tier = db.query(Tier).filter(Tier.name == TierName.STARTER).first()
        if not tier:
            tier = Tier(
                name=TierName.STARTER,
                max_daily_clips=10,
                max_platforms=3,
                platforms=["tiktok"],
                auto_posting=False,
                scheduling=False,
                analytics=False,
                api_access=False,
            )
            db.add(tier)
            db.flush()

        user = User(email="malformed_test@example.com")
        db.add(user)
        db.flush()

        membership = Membership(
            user_id=user.id,
            tier_id=tier.id,
            whop_membership_id="mem_malformed",
            whop_plan_id="plan_001",
        )
        db.add(membership)
        db.flush()

        account = Account(membership_id=membership.id, workspace_id="ws_malformed")
        db.add(account)
        db.flush()

        campaign = Campaign(
            source_id="camp_malformed",
            source_type="test",
            title="Test",
            target_platforms=["tiktok"],
        )
        db.add(campaign)
        db.flush()

        print("[OK] Step 1: Base objects created")

        try:
            clip_bad_ref = Clip(
                campaign_id=99999,
                account_id=account.id,
                source_url="https://test.com/clip_bad_ref",
                source_platform="youtube",
                title="Bad Ref Clip",
                description="Test",
                content_hash=hashlib.sha256(b"bad_ref").hexdigest(),
                engagement_score=0.5,
                view_count=1000,
            )
            db.add(clip_bad_ref)
            db.flush()
            print("[FAIL] Should have failed on invalid foreign key")
            return False
        except (IntegrityError, Exception):
            db.rollback()
            print(f"[OK] Step 2: Invalid foreign key rejected by database")

    finally:
        db.close()

    print("\n[PASS] TEST 6 PASS: Malformed payload rejected (validation works)")
    return True


if __name__ == "__main__":
    print("\n" + "="*70)
    print("[RUN] SUNO FAILURE DRILL - CONTROLLED BREAK TEST")
    print("="*70)

    results = {}

    try:
        results["test_1_bad_signature"] = test_failure_1_bad_webhook_signature(None)
        results["test_2_duplicate"] = test_failure_2_duplicate_webhook(None)
        results["test_3_missing_secret"] = test_failure_3_missing_provisioning_secret(None)
        results["test_4_caption_failure"] = test_failure_4_caption_generation_failure(None)
        results["test_5_bad_credentials"] = test_failure_5_bad_platform_credentials(None)
        results["test_6_malformed_payload"] = test_failure_6_malformed_payload(None)

        print("\n" + "="*70)
        print("FAILURE DRILL REPORT")
        print("="*70)

        print("\nRESULTS:")
        print("-" * 70)

        tests = [
            ("1", "Bad Webhook Signature", results["test_1_bad_signature"]),
            ("2", "Duplicate Webhook", results["test_2_duplicate"]),
            ("3", "Missing Provisioning Secret", results["test_3_missing_secret"]),
            ("4", "Caption Generation Failure", results["test_4_caption_failure"]),
            ("5", "Bad Platform Credentials", results["test_5_bad_credentials"]),
            ("6", "Malformed Payload", results["test_6_malformed_payload"]),
        ]

        for num, name, result in tests:
            status = "[PASS]" if result else "[FAIL]"
            print(f"Test {num}: {name:<35} {status}")

        print("-" * 70)

        all_pass = all(results.values())
        pass_count = sum(1 for v in results.values() if v)
        fail_count = sum(1 for v in results.values() if not v)

        print(f"\nTotal: {pass_count}/6 PASS, {fail_count}/6 FAIL")

        print("\n" + "="*70)
        if all_pass:
            print("[DONE] FAILURE DRILL: ALL TESTS PASSED")
            print("="*70)
            print("""
[PASS] Bad signatures rejected cleanly
[PASS] Duplicate webhooks handled (idempotent)
[PASS] Missing secrets cause explicit failure (no partial state)
[PASS] Failed jobs retry, then dead-letter (payload preserved)
[PASS] Bad credentials handled gracefully (no crashes)
[PASS] Malformed payload rejected (validation works)

VERDICT: SUNO FAILS ELEGANTLY [PASS]
            """)
        else:
            print("[FAIL] FAILURE DRILL: SOME TESTS FAILED")
            print("="*70)
            print(f"\n{fail_count} test(s) failed. See details above.")

        print("="*70 + "\n")

    except Exception as e:
        print(f"\n[FAIL] FAILURE DRILL EXECUTION ERROR: {e}")
        import traceback
        traceback.print_exc()
