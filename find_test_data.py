#!/usr/bin/env python3
"""
Find valid test data (campaign + user) for test_phase8_e2e.py
Run this on Render to identify valid TEST_CAMPAIGN_ID and TEST_USER_EMAIL
"""

import os
from suno.database import SessionLocal
from suno.common.models import Campaign, User, Membership, Account
from suno.common.enums import MembershipLifecycle

def find_test_data():
    """Find a valid campaign and user for testing."""
    db = SessionLocal()

    print("=" * 70)
    print("FINDING VALID TEST DATA FOR E2E TEST")
    print("=" * 70)
    print()

    # Find available campaigns
    print("[1] Available Campaigns:")
    campaigns = db.query(Campaign).filter(
        Campaign.available == True
    ).limit(5).all()

    if not campaigns:
        print("  ✗ No available campaigns found")
        print("  ACTION: Create a campaign and set available=True")
        db.close()
        return False

    for c in campaigns:
        print(f"  Campaign ID: {c.id}")
        print(f"    Title: {c.title}")
        print(f"    Brief: {c.brief[:50]}..." if c.brief else "    Brief: (empty)")
        print()

    selected_campaign_id = campaigns[0].id
    print(f"✓ Using Campaign ID: {selected_campaign_id}")
    print()

    # Find users with active membership and account
    print("[2] Users with Active Membership & Account:")
    users = (
        db.query(User)
        .join(Membership, User.id == Membership.user_id)
        .join(Account, Membership.id == Account.membership_id)
        .filter(Membership.status == MembershipLifecycle.ACTIVE)
        .limit(5)
        .all()
    )

    if not users:
        print("  ✗ No users with active membership found")
        print("  ACTION: Create a user with active membership")
        db.close()
        return False

    for u in users:
        membership = db.query(Membership).filter(
            Membership.user_id == u.id,
            Membership.status == MembershipLifecycle.ACTIVE
        ).first()
        print(f"  Email: {u.email}")
        print(f"    Membership Status: {membership.status.value}")
        print(f"    Clips Today: {membership.clips_today_count}")
        print()

    selected_user_email = users[0].email
    print(f"✓ Using User Email: {selected_user_email}")
    print()

    # Show the commands to run
    print("=" * 70)
    print("COMMANDS TO RUN E2E TEST")
    print("=" * 70)
    print()
    print("Windows CMD:")
    print(f'  set API_URL=https://suno-api-production.onrender.com')
    print(f'  set TEST_USER_EMAIL={selected_user_email}')
    print(f'  set TEST_CAMPAIGN_ID={selected_campaign_id}')
    print(f'  python test_phase8_e2e.py')
    print()
    print("PowerShell:")
    print(f'  $env:API_URL="https://suno-api-production.onrender.com"')
    print(f'  $env:TEST_USER_EMAIL="{selected_user_email}"')
    print(f'  $env:TEST_CAMPAIGN_ID="{selected_campaign_id}"')
    print(f'  python test_phase8_e2e.py')
    print()
    print("Bash/Unix:")
    print(f'  export API_URL="https://suno-api-production.onrender.com"')
    print(f'  export TEST_USER_EMAIL="{selected_user_email}"')
    print(f'  export TEST_CAMPAIGN_ID="{selected_campaign_id}"')
    print(f'  python test_phase8_e2e.py')
    print()

    db.close()
    return True

if __name__ == "__main__":
    try:
        success = find_test_data()
        exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Error: {e}")
        exit(1)
