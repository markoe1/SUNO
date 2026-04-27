#!/usr/bin/env python3
"""
Diagnose the User → Membership → Account chain
Traces exactly which gate is failing for the 403 error
"""

import os
from suno.database import SessionLocal
from suno.common.models import User, Membership, Account
from suno.common.enums import MembershipLifecycle, AccountStatus

def diagnose(email):
    """Trace the exact gate where the chain breaks."""
    db = SessionLocal()

    print("=" * 70)
    print(f"DIAGNOSING: {email}")
    print("=" * 70)
    print()

    # GATE 1: User Lookup
    print("[GATE 1] User Lookup")
    user = db.query(User).filter(User.email == email).first()

    if not user:
        print("✗ FAIL: User not found")
        db.close()
        return False

    print(f"✓ PASS: User found")
    print(f"  user.id = {user.id}")
    print()

    # GATE 2: Membership Lookup (The API's query)
    print("[GATE 2] Membership Lookup (API's exact query)")
    print(f"  Query: Membership.user_id == '{user.id}'")
    print(f"  Query: Membership.status.in_([PENDING, ACTIVE])")
    print()

    # First, show ALL memberships for this user
    all_memberships = db.query(Membership).filter(
        Membership.user_id == user.id
    ).all()

    if not all_memberships:
        print("✗ FAIL: No Membership records exist for this user")
        db.close()
        return False

    print(f"  Found {len(all_memberships)} Membership record(s):")
    for m in all_memberships:
        print(f"    - ID: {m.id}")
        print(f"      Status: '{m.status}' (type: {type(m.status).__name__})")
        print(f"      Status == 'active': {m.status == 'active'}")
        print(f"      Status == MembershipLifecycle.ACTIVE: {m.status == MembershipLifecycle.ACTIVE}")
        print(f"      Status in [PENDING, ACTIVE]: {m.status in [MembershipLifecycle.PENDING, MembershipLifecycle.ACTIVE]}")
        print()

    # Now run the EXACT API query
    membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.status.in_([MembershipLifecycle.PENDING, MembershipLifecycle.ACTIVE]),
    ).first()

    if not membership:
        print("✗ FAIL: API query returned None")
        print("  → This means status is NOT in [PENDING, ACTIVE]")
        print("  → OR there's an enum/string comparison issue")
        db.close()
        return False

    print(f"✓ PASS: Membership found")
    print(f"  membership.id = {membership.id}")
    print(f"  membership.status = '{membership.status}'")
    print()

    # GATE 3: Account Lookup (The missing link)
    print("[GATE 3] Account Lookup")
    print(f"  Query: Account.membership_id == {membership.id}")
    print()

    account = db.query(Account).filter(
        Account.membership_id == membership.id
    ).first()

    if not account:
        print("✗ FAIL: No Account record exists for this membership_id")
        print("  → This is the MISSING LINK")
        print("  ACTION: Create Account record with:")
        print(f"    membership_id = {membership.id}")
        print(f"    status = 'active'")
        db.close()
        return False

    print(f"✓ PASS: Account found")
    print(f"  account.id = {account.id}")
    print(f"  account.status = '{account.status}'")
    print()

    # GATE 4: Account status check
    print("[GATE 4] Account Status Check")
    print(f"  account.status == AccountStatus.ACTIVE: {account.status == AccountStatus.ACTIVE}")
    print(f"  account.status == 'active': {account.status == 'active'}")
    print()

    if account.status != AccountStatus.ACTIVE:
        print(f"✗ FAIL: Account status is '{account.status}', not 'active'")
        print(f"  ACTION: Update account.status to 'active'")
        db.close()
        return False

    print(f"✓ PASS: Account status is ACTIVE")
    print()

    # SUCCESS
    print("=" * 70)
    print("✓ SUCCESS: All gates passed")
    print("=" * 70)
    db.close()
    return True

if __name__ == "__main__":
    import sys
    email = sys.argv[1] if len(sys.argv) > 1 else "final_test@example.com"
    success = diagnose(email)
    sys.exit(0 if success else 1)
