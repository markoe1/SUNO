#!/usr/bin/env python
"""
Diagnostic script to inspect tier data and code logic
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

def diagnose():
    """Check tier configuration and recent membership"""

    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set")
        return False

    print(f"\n{'='*70}")
    print(f"TIER DIAGNOSTIC TEST")
    print(f"{'='*70}\n")

    try:
        engine = create_engine(DATABASE_URL)
        with Session(engine) as db:
            from suno.common.models import Tier, Membership, User
            from suno.common.enums import TierName

            # Check all tiers in database
            print(f"[STEP 1] All tiers in database:")
            print(f"{'='*70}")
            tiers = db.query(Tier).all()

            if not tiers:
                print("ERROR: No tiers found in database")
                return False

            for tier in tiers:
                print(f"  ID: {tier.id}")
                print(f"    Name (Enum):    {tier.name}")
                print(f"    Name (Value):   {tier.name.value if tier.name else 'None'}")
                print(f"    Daily Clips:    {tier.max_daily_clips}")
                print(f"    Platforms:      {tier.max_platforms}")
                print()

            # Check what the enum values are
            print(f"\n[STEP 2] Enum values:")
            print(f"{'='*70}")
            print(f"  TierName.STARTER.value = '{TierName.STARTER.value}'")
            print(f"  TierName.PRO.value     = '{TierName.PRO.value}'")

            # Query for tiers by name
            print(f"\n[STEP 3] Query results:")
            print(f"{'='*70}")

            starter_tier = db.query(Tier).filter(Tier.name == TierName.STARTER).first()
            pro_tier = db.query(Tier).filter(Tier.name == TierName.PRO).first()

            print(f"  Query: Tier.name == TierName.STARTER")
            if starter_tier:
                print(f"    Result: ID={starter_tier.id}, name={starter_tier.name.value}, clips={starter_tier.max_daily_clips}")
            else:
                print(f"    Result: None (NOT FOUND)")

            print(f"\n  Query: Tier.name == TierName.PRO")
            if pro_tier:
                print(f"    Result: ID={pro_tier.id}, name={pro_tier.name.value}, clips={pro_tier.max_daily_clips}")
            else:
                print(f"    Result: None (NOT FOUND)")

            # Check latest membership and what tier it points to
            print(f"\n[STEP 4] Latest membership:")
            print(f"{'='*70}")
            latest_membership = db.query(Membership).order_by(Membership.id.desc()).first()

            if latest_membership:
                pointed_tier = db.query(Tier).filter(Tier.id == latest_membership.tier_id).first()
                print(f"  Membership ID: {latest_membership.id}")
                print(f"  Plan ID:       {latest_membership.whop_plan_id}")
                print(f"  Tier ID:       {latest_membership.tier_id}")
                print(f"  Tier Name:     {pointed_tier.name.value if pointed_tier else 'NOT FOUND'}")
                print(f"  Tier Clips:    {pointed_tier.max_daily_clips if pointed_tier else 'N/A'}")

                # Check if this is correct
                print(f"\n[STEP 5] Validation:")
                print(f"{'='*70}")

                if latest_membership.whop_plan_id == "plan_starter":
                    expected_tier = starter_tier
                    expected_name = "starter"
                    expected_clips = 10
                elif latest_membership.whop_plan_id == "plan_pro":
                    expected_tier = pro_tier
                    expected_name = "pro"
                    expected_clips = 30
                else:
                    expected_tier = None
                    expected_name = "unknown"
                    expected_clips = None

                print(f"  Plan:             {latest_membership.whop_plan_id}")
                print(f"  Expected Tier:    {expected_name}")
                print(f"  Expected Clips:   {expected_clips}")
                print(f"  Actual Tier:      {pointed_tier.name.value if pointed_tier else 'NOT FOUND'}")
                print(f"  Actual Clips:     {pointed_tier.max_daily_clips if pointed_tier else 'N/A'}")

                if pointed_tier and expected_tier:
                    if pointed_tier.id == expected_tier.id:
                        print(f"\n  RESULT: CORRECT - Tier matches expected")
                        return True
                    else:
                        print(f"\n  RESULT: WRONG - Tier ID mismatch!")
                        print(f"    Expected tier ID: {expected_tier.id}")
                        print(f"    Actual tier ID:   {pointed_tier.id}")
                        return False
            else:
                print(f"  No memberships found")

            return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = diagnose()
    sys.exit(0 if success else 1)
