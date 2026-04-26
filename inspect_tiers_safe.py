#!/usr/bin/env python
"""
Safe read-only inspection of tiers table
No modifications, no deletions, read-only queries only.
"""

import os
import sys

def inspect_tiers():
    """Safely inspect tiers table without modifications."""

    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Set it and try again: export DATABASE_URL='postgresql://...'")
        return False

    print(f"\n{'='*70}")
    print(f"TIERS TABLE INSPECTION (READ-ONLY)")
    print(f"{'='*70}\n")

    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import Session

        # Create engine
        engine = create_engine(DATABASE_URL)

        # Test connection
        print(f"Connecting to database...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.close()
        print(f"OK: Connected\n")

        # Query tiers table
        print(f"{'='*70}")
        print(f"TIERS TABLE CONTENTS")
        print(f"{'='*70}\n")

        with Session(engine) as db:
            from suno.common.models import Tier

            tiers = db.query(Tier).all()

            if not tiers:
                print(f"No tiers found in database\n")
                return False

            print(f"{'ID':<5} {'Name':<12} {'Daily Clips':<15} {'Platforms':<12}")
            print(f"{'-'*70}")

            for tier in tiers:
                tier_name = tier.name.value if tier.name else "UNKNOWN"
                print(f"{tier.id:<5} {tier_name:<12} {tier.max_daily_clips:<15} {tier.max_platforms:<12}")

            print(f"\n")

            # Check for issues
            print(f"{'='*70}")
            print(f"VALIDATION")
            print(f"{'='*70}\n")

            from suno.common.enums import TierName

            # Find each tier by name
            starter = db.query(Tier).filter(Tier.name == TierName.STARTER).first()
            pro = db.query(Tier).filter(Tier.name == TierName.PRO).first()

            print(f"Query: Tier.name == 'starter' (TierName.STARTER)")
            if starter:
                print(f"  Found: ID={starter.id}, name='{starter.name.value}', clips={starter.max_daily_clips}")
                if starter.max_daily_clips == 10:
                    print(f"  Status: CORRECT (10 clips = STARTER)")
                else:
                    print(f"  Status: WRONG! Expected 10 clips, got {starter.max_daily_clips}")
            else:
                print(f"  Found: None - MISSING from database!")

            print()

            print(f"Query: Tier.name == 'pro' (TierName.PRO)")
            if pro:
                print(f"  Found: ID={pro.id}, name='{pro.name.value}', clips={pro.max_daily_clips}")
                if pro.max_daily_clips == 30:
                    print(f"  Status: CORRECT (30 clips = PRO)")
                else:
                    print(f"  Status: WRONG! Expected 30 clips, got {pro.max_daily_clips}")
            else:
                print(f"  Found: None - MISSING from database!")

            print()

            # Check latest memberships
            print(f"{'='*70}")
            print(f"LATEST MEMBERSHIPS (last 5)")
            print(f"{'='*70}\n")

            from suno.common.models import Membership

            recent = db.query(Membership).order_by(Membership.id.desc()).limit(5).all()

            if not recent:
                print(f"No memberships found")
            else:
                print(f"{'ID':<6} {'Plan':<15} {'Tier ID':<10} {'Tier Name':<12} {'Status':<10}")
                print(f"{'-'*70}")

                for m in reversed(recent):  # Show oldest first
                    tier = db.query(Tier).filter(Tier.id == m.tier_id).first()
                    tier_name = tier.name.value if tier else "UNKNOWN"
                    print(f"{m.id:<6} {m.whop_plan_id or 'None':<15} {m.tier_id:<10} {tier_name:<12} {m.status.value:<10}")

            print(f"\n")
            return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = inspect_tiers()
    sys.exit(0 if success else 1)
