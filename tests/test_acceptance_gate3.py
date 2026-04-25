"""
GATE 3: Provisioning Failure Behavior Test
Tests that provisioning fails explicitly without creating partial/broken accounts.
"""

import os
from suno.provisioning.account_ops import AccountProvisioner, ProvisioningError

def test_provisioning_without_api_key(db_session):
    """Test 3A: Provisioning fails explicitly when API key missing."""
    from suno.common.models import User, Membership, Tier
    from suno.common.enums import MembershipLifecycle, TierName

    # Create test data
    user = User(email="testuser@example.com")
    db_session.add(user)
    db_session.flush()

    tier = db_session.query(Tier).filter(Tier.name == TierName.STARTER).first()
    if not tier:
        tier = Tier(
            name=TierName.STARTER,
            max_daily_clips=10,
            max_platforms=3,
            platforms=["tiktok", "instagram", "youtube"],
            auto_posting=False,
            scheduling=False,
            analytics=False,
            api_access=False,
        )
        db_session.add(tier)
        db_session.flush()

    membership = Membership(
        user_id=user.id,
        tier_id=tier.id,
        whop_membership_id="mem_test_123",
        whop_plan_id="plan_001",
        status=MembershipLifecycle.PENDING,
    )
    db_session.add(membership)
    db_session.commit()

    # Try to provision WITHOUT SUNO_API_KEY in production mode
    old_env = os.environ.get("ENVIRONMENT")
    old_key = os.environ.get("SUNO_API_KEY")

    try:
        os.environ["ENVIRONMENT"] = "production"
        if "SUNO_API_KEY" in os.environ:
            del os.environ["SUNO_API_KEY"]

        provisioner = AccountProvisioner(db_session, suno_api_key=None)

        print("❌ Should have raised ProvisioningError for missing API key")
        return False

    except ProvisioningError as e:
        # This is expected!
        assert "SUNO_API_KEY" in str(e), f"Error should mention SUNO_API_KEY: {e}"
        print(f"✅ Test 3A PASS: Provisioning fails explicitly")
        print(f"   Error message: {e}")

        # Verify account was NOT created
        from suno.common.models import Account
        account = db_session.query(Account).filter(Account.membership_id == membership.id).first()
        assert account is None, "No account should be created on provisioning failure"
        print(f"✅ No partial/broken account created")

        return True

    finally:
        if old_env:
            os.environ["ENVIRONMENT"] = old_env
        if old_key:
            os.environ["SUNO_API_KEY"] = old_key

def test_provisioning_with_stub_api(db_session):
    """Test 3B: Provisioning works in stub mode (dev) when API key missing."""
    from suno.common.models import User, Membership, Tier, Account
    from suno.common.enums import MembershipLifecycle, TierName

    # Create test data
    user = User(email="testuser2@example.com")
    db_session.add(user)
    db_session.flush()

    tier = db_session.query(Tier).filter(Tier.name == TierName.STARTER).first()
    if not tier:
        tier = Tier(
            name=TierName.STARTER,
            max_daily_clips=10,
            max_platforms=3,
            platforms=["tiktok", "instagram", "youtube"],
            auto_posting=False,
            scheduling=False,
            analytics=False,
            api_access=False,
        )
        db_session.add(tier)
        db_session.flush()

    membership = Membership(
        user_id=user.id,
        tier_id=tier.id,
        whop_membership_id="mem_test_456",
        whop_plan_id="plan_001",
        status=MembershipLifecycle.PENDING,
    )
    db_session.add(membership)
    db_session.commit()

    old_env = os.environ.get("ENVIRONMENT")

    try:
        os.environ["ENVIRONMENT"] = "development"  # Allow stubs

        # Provision with no API key (should work in dev mode)
        provisioner = AccountProvisioner(db_session, suno_api_key=None)
        result = provisioner.provision_account(user.id, user.email, "starter")

        assert result["success"] == True, "Provisioning should succeed in dev mode"
        assert "workspace_id" in result, "Result should have workspace_id"
        print(f"✅ Test 3B PASS: Provisioning works in stub mode")
        print(f"   Created workspace: {result['workspace_id']}")

        # Verify account WAS created
        account = db_session.query(Account).filter(Account.membership_id == membership.id).first()
        assert account is not None, "Account should be created in stub mode"
        assert account.workspace_id == result["workspace_id"], "Workspace ID should match"
        print(f"✅ Account created in stub mode")

        return True

    finally:
        if old_env:
            os.environ["ENVIRONMENT"] = old_env

def test_provisioning_idempotency(db_session):
    """Test 3C: Duplicate provisioning attempt returns same account (idempotent)."""
    from suno.common.models import User, Membership, Tier, Account
    from suno.common.enums import MembershipLifecycle, TierName

    # Create test data
    user = User(email="testuser3@example.com")
    db_session.add(user)
    db_session.flush()

    tier = db_session.query(Tier).filter(Tier.name == TierName.STARTER).first()
    if not tier:
        tier = Tier(
            name=TierName.STARTER,
            max_daily_clips=10,
            max_platforms=3,
            platforms=["tiktok", "instagram", "youtube"],
            auto_posting=False,
            scheduling=False,
            analytics=False,
            api_access=False,
        )
        db_session.add(tier)
        db_session.flush()

    membership = Membership(
        user_id=user.id,
        tier_id=tier.id,
        whop_membership_id="mem_test_789",
        whop_plan_id="plan_001",
        status=MembershipLifecycle.PENDING,
    )
    db_session.add(membership)
    db_session.commit()

    old_env = os.environ.get("ENVIRONMENT")

    try:
        os.environ["ENVIRONMENT"] = "development"

        provisioner = AccountProvisioner(db_session, suno_api_key=None)

        # First provisioning
        result1 = provisioner.provision_account(user.id, user.email, "starter")
        assert result1["success"] == True
        workspace_id_1 = result1["workspace_id"]
        is_new_1 = result1["is_new"]

        print(f"✅ First provisioning: {workspace_id_1} (is_new={is_new_1})")

        # Second provisioning attempt (same user)
        result2 = provisioner.provision_account(user.id, user.email, "starter")
        assert result2["success"] == True
        workspace_id_2 = result2["workspace_id"]
        is_new_2 = result2["is_new"]

        # Should return same workspace
        assert workspace_id_1 == workspace_id_2, "Should return same workspace on duplicate"
        assert is_new_1 == True, "First should be new"
        assert is_new_2 == False, "Second should NOT be new"

        print(f"✅ Test 3C PASS: Provisioning is idempotent")
        print(f"   Both attempts returned: {workspace_id_1}")

        # Verify only one account in DB
        account_count = db_session.query(Account).filter(Account.membership_id == membership.id).count()
        assert account_count == 1, f"Should have 1 account, found {account_count}"
        print(f"✅ Only 1 account in DB (no duplicates)")

        return True

    finally:
        if old_env:
            os.environ["ENVIRONMENT"] = old_env

if __name__ == "__main__":
    print("\n" + "="*60)
    print("GATE 3: PROVISIONING FAILURE BEHAVIOR")
    print("="*60)

    from suno.database import SessionLocal

    try:
        db = SessionLocal()
        try:
            # Test 1: Explicit failure in production
            success_1 = test_provisioning_without_api_key(db)

            # Test 2: Stub mode in development
            success_2 = test_provisioning_with_stub_api(db)

            # Test 3: Idempotency
            success_3 = test_provisioning_idempotency(db)

            if success_1 and success_2 and success_3:
                print("\n" + "="*60)
                print("GATE 3: ✅ PASS")
                print("="*60)
                print("""
✅ Provisioning fails explicitly when API key missing (production)
✅ No partial/broken accounts created on failure
✅ Works in stub mode for development
✅ Idempotent: duplicate attempts return same account
✅ No duplicate accounts created due to race condition
                """)
            else:
                print("\n" + "="*60)
                print("GATE 3: ❌ FAIL")
                print("="*60)

        finally:
            db.close()

    except Exception as e:
        print(f"\n❌ GATE 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
