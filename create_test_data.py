#!/usr/bin/env python3
"""
Create minimal test data in production for E2E testing.
Creates: user, membership, account, campaign.
"""
import os
import sys
from datetime import datetime
from uuid import uuid4

# Add repo to path
sys.path.insert(0, ".")

from suno.database import SessionLocal
from suno.common.models import User, Membership, Account, Campaign, CreatorProfile
from suno.common.enums import MembershipLifecycle, AccountStatus, TierName

def create_test_data():
    db = SessionLocal()
    try:
        # 1. Create test user
        test_email = f"e2e-test-{uuid4().hex[:8]}@suno.local"
        user = User(email=test_email, whop_user_id=f"whop_test_{uuid4().hex[:8]}")
        db.add(user)
        db.flush()
        print(f"[OK] User created: {test_email}")

        # 2. Create membership (ACTIVE)
        membership = Membership(
            user_id=user.id,
            whop_user_id=f"test_user_{user.id}",
            whop_membership_id=f"test_membership_{user.id}",
            tier=TierName.PRO,
            status="active",
        )
        db.add(membership)
        db.flush()
        print(f"[OK] Membership created: {membership.id} (status={membership.status})")

        # 3. Create account
        account = Account(
            membership_id=membership.id,
            workspace_id=f"workspace_{uuid4().hex[:8]}",
            status=AccountStatus.ACTIVE,
        )
        db.add(account)
        db.flush()
        print(f"[OK] Account created: {account.id} (status={account.status})")

        # 4. Create creator profile
        profile = CreatorProfile(
            account_id=account.id,
            niche="test",
            tone="energetic",
        )
        db.add(profile)
        db.flush()
        print(f"[OK] CreatorProfile created: {profile.id}")

        # 5. Create campaign (AVAILABLE = TRUE)
        campaign_id = uuid4()
        campaign = Campaign(
            id=campaign_id,
            title=f"Test Campaign {campaign_id.hex[:8]}",
            description="E2E test campaign",
            available=True,  # ← CRITICAL
            approval_required=False,
        )
        db.add(campaign)
        db.flush()
        print(f"[OK] Campaign created: {campaign_id} (available={campaign.available})")

        db.commit()

        print("\n" + "="*60)
        print("TEST DATA READY")
        print("="*60)
        print(f"User Email:   {test_email}")
        print(f"Campaign ID:  {campaign_id}")
        print("="*60)

        return test_email, campaign_id

    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    create_test_data()
