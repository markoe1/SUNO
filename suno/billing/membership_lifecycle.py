"""
Membership Lifecycle Event Handlers
Handles purchase, activation, cancellation, upgrade, downgrade events
with proper state machine transitions and job enqueueing.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MembershipLifecycleHandler:
    """Handles membership state transitions and event routing."""

    def __init__(self, db: Session, queue_manager):
        """
        Initialize membership lifecycle handler.

        Args:
            db: SQLAlchemy session
            queue_manager: JobQueueManager instance
        """
        self.db = db
        self.queue_manager = queue_manager

    def handle_purchase(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle new membership purchase.

        Event data includes:
        - user_email: Customer email
        - whop_membership_id: Whop membership ID
        - plan_id: Whop plan ID

        Returns:
            Result dict with membership_id and next action
        """
        from suno.common.models import User, Tier, Membership
        from suno.common.enums import MembershipLifecycle

        try:
            email = event_data.get("user_email")
            whop_membership_id = event_data.get("whop_membership_id")
            plan_id = event_data.get("plan_id")

            # === ENTRY LOGGING ===
            logger.info(f"[PURCHASE_START] handle_purchase called with plan_id='{plan_id}'")

            if not all([email, whop_membership_id, plan_id]):
                raise ValueError("Missing required fields: user_email, whop_membership_id, plan_id")

            # Create or find user
            user = self.db.query(User).filter(User.email == email).first()
            if not user:
                user = User(email=email)
                self.db.add(user)
                self.db.flush()
                logger.info(f"Created user {email}")

            # Discover tier from plan_id
            logger.info(f"[TIER_DISCOVER] Calling _discover_tier_from_plan('{plan_id}')")
            tier = self._discover_tier_from_plan(plan_id)
            if not tier:
                raise ValueError(f"Unknown plan_id: {plan_id}")
            logger.info(f"[TIER_RETURNED] _discover_tier_from_plan returned tier id={tier.id}, name='{tier.name}', clips={tier.max_daily_clips}")

            # Create membership
            membership = Membership(
                user_id=user.id,
                tier_id=tier.id,
                whop_membership_id=whop_membership_id,
                whop_plan_id=plan_id,  # Store plan ID for tier mapping
                status="active",
                activated_at=datetime.utcnow(),
            )
            self.db.add(membership)
            self.db.commit()

            logger.info(f"Created membership {membership.id} for user {email} (tier: {tier.name}) - status: ACTIVE")

            # Enqueue provisioning job
            job_id = self.queue_manager.enqueue(
                "critical",
                provision_account_job,
                kwargs={
                    "membership_id": membership.id,
                    "user_id": user.id,
                    "email": email,
                    "tier_name": tier.name,
                },
            )

            return {
                "success": True,
                "membership_id": membership.id,
                "user_id": user.id,
                "tier": tier.name,
                "job_id": job_id,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Purchase event handling failed: {e}")
            return {"success": False, "error": str(e)}

    def handle_cancellation(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle membership cancellation.

        Event data includes:
        - whop_membership_id: Whop membership ID

        Returns:
            Result dict with revocation status
        """
        from suno.common.models import Membership
        from suno.common.enums import MembershipLifecycle

        try:
            whop_membership_id = event_data.get("whop_membership_id")
            if not whop_membership_id:
                raise ValueError("Missing whop_membership_id")

            # Find membership
            membership = self.db.query(Membership).filter(
                Membership.whop_membership_id == whop_membership_id
            ).first()

            if not membership:
                logger.warning(f"Membership {whop_membership_id} not found for cancellation")
                return {"success": False, "error": "Membership not found"}

            # Mark as cancelled
            membership.status = "cancelled"
            membership.cancelled_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Marked membership {membership.id} as cancelled")

            # Enqueue revocation job
            job_id = self.queue_manager.enqueue(
                "critical",
                revoke_account_job,
                kwargs={"membership_id": membership.id},
            )

            return {
                "success": True,
                "membership_id": membership.id,
                "job_id": job_id,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Cancellation event handling failed: {e}")
            return {"success": False, "error": str(e)}

    def handle_activation(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle membership activation.

        Event data includes:
        - whop_membership_id: Whop membership ID

        Returns:
            Result dict
        """
        from suno.common.models import Membership
        from suno.common.enums import MembershipLifecycle

        try:
            whop_membership_id = event_data.get("whop_membership_id")
            if not whop_membership_id:
                raise ValueError("Missing whop_membership_id")

            membership = self.db.query(Membership).filter(
                Membership.whop_membership_id == whop_membership_id
            ).first()

            if not membership:
                logger.warning(f"Membership {whop_membership_id} not found for activation")
                return {"success": False, "error": "Membership not found"}

            # Update status to active
            membership.status = "active"
            membership.activated_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Activated membership {membership.id}")

            return {
                "success": True,
                "membership_id": membership.id,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Activation event handling failed: {e}")
            return {"success": False, "error": str(e)}

    def handle_upgrade(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle membership upgrade (plan change to better tier).

        Event data includes:
        - whop_membership_id: Whop membership ID
        - new_plan_id: New plan ID
        """
        from suno.common.models import Membership

        try:
            whop_membership_id = event_data.get("whop_membership_id")
            new_plan_id = event_data.get("new_plan_id")

            if not all([whop_membership_id, new_plan_id]):
                raise ValueError("Missing whop_membership_id or new_plan_id")

            membership = self.db.query(Membership).filter(
                Membership.whop_membership_id == whop_membership_id
            ).first()

            if not membership:
                return {"success": False, "error": "Membership not found"}

            # Discover new tier
            new_tier = self._discover_tier_from_plan(new_plan_id)
            if not new_tier:
                raise ValueError(f"Unknown plan_id: {new_plan_id}")

            # Update tier
            old_tier_id = membership.tier_id
            membership.tier_id = new_tier.id
            self.db.commit()

            logger.info(f"Upgraded membership {membership.id} from tier {old_tier_id} to {new_tier.id}")

            # Enqueue tier update job
            job_id = self.queue_manager.enqueue(
                "high",
                update_tier_job,
                kwargs={
                    "membership_id": membership.id,
                    "new_tier_name": new_tier.name,
                },
            )

            return {
                "success": True,
                "membership_id": membership.id,
                "new_tier": new_tier.name,
                "job_id": job_id,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Upgrade event handling failed: {e}")
            return {"success": False, "error": str(e)}

    def handle_downgrade(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle membership downgrade (plan change to lower tier).

        Event data includes:
        - whop_membership_id: Whop membership ID
        - new_plan_id: New plan ID
        """
        # Same as upgrade for now (tier is just updated)
        return self.handle_upgrade(event_data)

    def _discover_tier_from_plan(self, plan_id: str):
        """
        Discover tier from Whop plan_id with intelligent fallback.

        Tiers are pre-created at startup, so discovery just maps plan_id to existing tier.

        Args:
            plan_id: Whop plan ID

        Returns:
            Tier object or None
        """
        from suno.common.models import Tier, Membership
        from suno.common.enums import TierName

        # Ensure tiers exist (created at startup)
        starter = self.db.query(Tier).filter(Tier.name == "starter").first()
        pro = self.db.query(Tier).filter(Tier.name == "pro").first()

        if not starter or not pro:
            # Create tiers if they don't exist
            if not starter:
                starter = Tier(
                    name=TierName.STARTER.value,
                    max_daily_clips=10,
                    max_platforms=3,
                    platforms=["tiktok", "instagram", "youtube"],
                    auto_posting=False,
                    scheduling=False,
                    analytics=False,
                    api_access=False,
                )
                self.db.add(starter)

            if not pro:
                pro = Tier(
                    name=TierName.PRO.value,
                    max_daily_clips=30,
                    max_platforms=6,
                    platforms=["tiktok", "instagram", "youtube", "twitter", "bluesky", "threads"],
                    auto_posting=True,
                    scheduling=True,
                    analytics=True,
                    api_access=True,
                )
                self.db.add(pro)

            self.db.commit()

        # === TIER MAPPING DIAGNOSTIC LOGGING ===
        logger.info(f"[TIER_MAP_START] Discovering tier for plan_id='{plan_id}'")

        # Log starter tier details
        if starter:
            logger.info(f"[TIER_STARTER] id={starter.id}, name='{starter.name}', max_daily_clips={starter.max_daily_clips}, max_platforms={starter.max_platforms}")
        else:
            logger.warning(f"[TIER_STARTER] NOT FOUND in database")

        # Log pro tier details
        if pro:
            logger.info(f"[TIER_PRO] id={pro.id}, name='{pro.name}', max_daily_clips={pro.max_daily_clips}, max_platforms={pro.max_platforms}")
        else:
            logger.warning(f"[TIER_PRO] NOT FOUND in database")

        # Map plan_id to tier
        plan_to_tier = {
            "plan_starter": starter,
            "plan_pro": pro,
        }

        tier = plan_to_tier.get(plan_id)
        if tier:
            logger.info(f"[TIER_SELECTED] plan_id='{plan_id}' → id={tier.id}, name='{tier.name}', max_daily_clips={tier.max_daily_clips}, max_platforms={tier.max_platforms}")
            logger.info(f"Plan_id {plan_id} → {tier.name} tier")
            return tier

        # Unknown plan_id: default to STARTER for safety
        logger.warning(f"[TIER_UNKNOWN] plan_id='{plan_id}' not recognized, defaulting to STARTER")
        if starter:
            logger.warning(f"[TIER_SELECTED_DEFAULT] Defaulting to STARTER: id={starter.id}, name='{starter.name}', max_daily_clips={starter.max_daily_clips}")
        return starter


# Background job functions (called by RQ workers)


def provision_account_job(membership_id: int, user_id: int, email: str, tier_name: str):
    """Provision account in background."""
    from suno.database import SessionLocal
    from suno.provisioning.account_ops import AccountProvisioner

    db = SessionLocal()
    try:
        provisioner = AccountProvisioner(db)
        result = provisioner.provision_account(user_id, email, tier_name)
        logger.info(f"Provisioning job completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Provisioning job failed: {e}")
        raise
    finally:
        db.close()


def revoke_account_job(membership_id: int):
    """Revoke account in background."""
    from suno.database import SessionLocal
    from suno.provisioning.account_ops import AccountRevoker

    db = SessionLocal()
    try:
        revoker = AccountRevoker(db)
        result = revoker.revoke_account(membership_id)
        logger.info(f"Revocation job completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Revocation job failed: {e}")
        raise
    finally:
        db.close()


def update_tier_job(membership_id: int, new_tier_name: str):
    """Update tier in background."""
    from suno.database import SessionLocal
    from suno.common.models import Membership

    db = SessionLocal()
    try:
        membership = db.query(Membership).filter(Membership.id == membership_id).first()
        if membership:
            logger.info(f"Tier updated for membership {membership_id} to {new_tier_name}")
        return {"success": True, "membership_id": membership_id}
    finally:
        db.close()
