"""
Account Provisioning and Revocation
Real operations for account lifecycle with explicit error handling.
"""

import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from suno.common.enums import AccountStatus

logger = logging.getLogger(__name__)


class ProvisioningError(Exception):
    """Raised when account provisioning fails"""
    pass


class RevocationError(Exception):
    """Raised when account revocation fails"""
    pass


class AccountProvisioner:
    """Provisions SUNO accounts for new members."""

    def __init__(self, db: Session, suno_api_key: Optional[str] = None):
        """
        Initialize provisioner.

        Args:
            db: SQLAlchemy session
            suno_api_key: API key (unused - kept for compatibility)
        """
        self.db = db

    def provision_account(
        self,
        user_id: int,
        email: str,
        tier_name: str,
        workspace_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Provision account for new member.

        Args:
            user_id: User ID
            email: User email
            tier_name: Tier name (starter, pro)
            workspace_name: Optional custom workspace name

        Returns:
            Result dict with workspace_id and status

        Raises:
            ProvisioningError: If provisioning fails
        """
        from suno.common.models import Account, Membership
        from sqlalchemy.exc import IntegrityError

        try:
            # Check if account already exists
            membership = self.db.query(Membership).filter(
                Membership.user_id == user_id
            ).first()

            if not membership:
                raise ProvisioningError(f"Membership not found for user {user_id}")

            # Generate workspace ID
            workspace_id = f"ws_{uuid.uuid4().hex[:12]}"
            workspace_name = workspace_name or f"workspace_{user_id}"

            # Direct provisioning logic (internal service, no external API call)
            logger.info(f"Provisioning workspace {workspace_id} for {email} (tier: {tier_name})")

            # Create account record (atomic - race condition handled by DB constraint)
            account = Account(
                membership_id=membership.id,
                workspace_id=workspace_id,
                status=AccountStatus.ACTIVE,
                automation_enabled=True,
            )
            self.db.add(account)
            self.db.commit()

            logger.info(f"Successfully provisioned account {workspace_id} for user {user_id}")
            return {
                "success": True,
                "workspace_id": workspace_id,
                "is_new": True,
            }

        except IntegrityError:
            # Account already exists (race condition resolved by DB constraint)
            self.db.rollback()
            existing = self.db.query(Account).filter(
                Account.membership_id == membership.id
            ).first()
            logger.info(f"Account already exists for membership {membership.id}: {existing.workspace_id}")
            return {
                "success": True,
                "workspace_id": existing.workspace_id,
                "is_new": False,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Provisioning failed for user {user_id}: {e}")
            raise ProvisioningError(str(e))


class AccountRevoker:
    """Revokes access for cancelled members."""

    def __init__(self, db: Session, suno_api_key: Optional[str] = None):
        """
        Initialize revoker.

        Args:
            db: SQLAlchemy session
            suno_api_key: API key (unused - kept for compatibility)
        """
        self.db = db

    def revoke_account(self, membership_id: int) -> Dict[str, Any]:
        """
        Revoke account access immediately and completely.

        This is a hard revocation:
        - Disables all automation
        - Marks account inactive
        - Prevents any new jobs

        Args:
            membership_id: Membership ID to revoke

        Returns:
            Result dict with success status

        Raises:
            RevocationError: If revocation fails critically
        """
        from suno.common.models import Account, Membership
        from suno.common.enums import MembershipLifecycle

        try:
            # Get membership and account
            membership = self.db.query(Membership).filter(
                Membership.id == membership_id
            ).first()

            if not membership:
                raise RevocationError(f"Membership {membership_id} not found")

            account = self.db.query(Account).filter(
                Account.membership_id == membership_id
            ).first()

            if not account:
                logger.warning(f"No account found for membership {membership_id}, marking membership revoked only")
            else:
                # Disable automation immediately
                account.automation_enabled = False
                account.status = AccountStatus.REVOKED
                self.db.commit()
                logger.info(f"Disabled automation for account {account.workspace_id}")

            # Mark membership as revoked
            membership.status = MembershipLifecycle.REVOKED
            membership.revoked_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Successfully revoked membership {membership_id}")
            return {
                "success": True,
                "membership_id": membership_id,
                "revoked_at": membership.revoked_at.isoformat(),
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Revocation failed for membership {membership_id}: {e}")
            raise RevocationError(str(e))
