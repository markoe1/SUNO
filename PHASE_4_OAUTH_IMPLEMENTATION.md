# PHASE 4: OAUTH IMPLEMENTATION — SUNO Clips (April 18, 2026)

## OVERVIEW

**Goal:** Implement proper OAuth token management for TikTok and Instagram/Meta so we can:
1. Get production access tokens (not sandbox)
2. Refresh tokens automatically
3. Store credentials securely in database
4. Remove plaintext passwords from .env

**Current Status:**
- YouTube ✅ OAuth working (production-ready)
- TikTok 🟡 Using browser automation + sandbox (needs OAuth)
- Instagram 🟡 Using browser automation + temp token (needs OAuth)

---

## IMPLEMENTATION PLAN

### Step 1: Add OAuth Routes to FastAPI (30 min)

Location: `api/routes/platform_oauth.py` (NEW FILE)

Creates three endpoint pairs:
- `/api/oauth/tiktok/start` → Redirects user to TikTok OAuth
- `/api/oauth/tiktok/callback` → Captures auth code, exchanges for token
- `/api/oauth/instagram/start` → Redirects user to Instagram OAuth
- `/api/oauth/instagram/callback` → Captures auth code, exchanges for token

### Step 2: Add Credential Storage to Database (30 min)

Location: `db/models.py` → ADD TABLE

```python
class PlatformCredential(Base):
    """Stores OAuth tokens for social platforms."""
    __tablename__ = "platform_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    platform: Mapped[str]  # 'tiktok', 'instagram', 'youtube', etc.
    platform_user_id: Mapped[Optional[str]]  # TikTok UID, IG business account ID, etc.

    # Encrypted tokens
    access_token: Mapped[str]  # encrypted with ENCRYPTION_KEY from .env
    refresh_token: Mapped[Optional[str]]  # encrypted
    token_expires_at: Mapped[Optional[datetime]]

    is_valid: Mapped[bool] = mapped_column(default=True)
    last_refreshed_at: Mapped[Optional[datetime]]

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
```

Alembic migration:
```bash
cd C:\Users\ellio\SUNO-repo
alembic revision --autogenerate -m "Add platform_credentials table"
alembic upgrade head
```

### Step 3: Create OAuth Service Layer (1 hour)

Location: `services/platform_oauth.py` (NEW FILE)

Handles:
- TikTok OAuth token exchange
- Instagram/Meta OAuth token exchange
- Token refresh logic
- Secure token storage/retrieval

### Step 4: Update TikTok Adapter to Use DB Tokens (15 min)

Location: `suno/posting/adapters/tiktok.py`

Change from:
```python
access_token = account_credentials.get("access_token")  # from .env or browser
```

To:
```python
# Query database for stored token
cred = await db.query(PlatformCredential).filter(
    PlatformCredential.user_id == user_id,
    PlatformCredential.platform == "tiktok"
).first()

access_token = decrypt(cred.access_token)  # decrypt from storage
```

### Step 5: Update Instagram Adapter to Use DB Tokens (15 min)

Similar to TikTok — query database instead of using hardcoded token

### Step 6: Add Token Refresh Middleware (30 min)

Location: `api/middleware.py` → ADD

Periodically checks if tokens are about to expire and refreshes them.

---

## DETAILED IMPLEMENTATION

### 1️⃣ OAUTH ROUTES (`api/routes/platform_oauth.py`)

```python
"""Platform OAuth routes: TikTok, Instagram, Meta."""

import os
import logging
from datetime import datetime, timedelta
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from api.deps import get_db, get_current_user
from db.models import User, PlatformCredential
from services.platform_oauth import TikTokOAuthService, InstagramOAuthService

router = APIRouter(prefix="/api/oauth", tags=["oauth"])
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# TIKTOK OAUTH
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/tiktok/start")
async def tiktok_oauth_start(
    user: User = Depends(get_current_user),
):
    """
    Initiate TikTok OAuth flow.
    Redirects user to TikTok authorization page.
    """
    redirect_uri = os.getenv("BASE_URL", "http://localhost:8000") + "/api/oauth/tiktok/callback"
    auth_url = TikTokOAuthService.get_authorization_url(redirect_uri)

    logger.info(f"TikTok OAuth: Initiating flow for user {user.id}")
    return RedirectResponse(url=auth_url)


@router.get("/tiktok/callback")
async def tiktok_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    TikTok OAuth callback handler.
    Exchanges auth code for access token and stores it.
    """
    if error:
        logger.warning(f"TikTok OAuth error: {error}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"TikTok auth failed: {error}")

    try:
        redirect_uri = os.getenv("BASE_URL", "http://localhost:8000") + "/api/oauth/tiktok/callback"

        # Exchange code for token
        token_data = await TikTokOAuthService.exchange_code_for_token(code, redirect_uri)

        # Store credential in database
        cred = await PlatformCredential.store(
            db=db,
            user_id=user.id,
            platform="tiktok",
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_expires_at=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 86400)),
            platform_user_id=token_data.get("open_id"),  # TikTok's user ID
        )

        logger.info(f"TikTok OAuth: Token stored for user {user.id}")

        # Redirect to dashboard
        return RedirectResponse(url="/dashboard?platform=tiktok&status=connected")

    except Exception as e:
        logger.error(f"TikTok OAuth callback error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token exchange failed")


# ─────────────────────────────────────────────────────────────────────────────
# INSTAGRAM/META OAUTH
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/instagram/start")
async def instagram_oauth_start(
    user: User = Depends(get_current_user),
):
    """
    Initiate Instagram/Meta OAuth flow.
    Redirects user to Meta authorization page.
    """
    redirect_uri = os.getenv("BASE_URL", "http://localhost:8000") + "/api/oauth/instagram/callback"
    auth_url = InstagramOAuthService.get_authorization_url(redirect_uri)

    logger.info(f"Instagram OAuth: Initiating flow for user {user.id}")
    return RedirectResponse(url=auth_url)


@router.get("/instagram/callback")
async def instagram_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Instagram/Meta OAuth callback handler.
    Exchanges auth code for access token and stores it.
    """
    if error:
        logger.warning(f"Instagram OAuth error: {error}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Instagram auth failed: {error}")

    try:
        redirect_uri = os.getenv("BASE_URL", "http://localhost:8000") + "/api/oauth/instagram/callback"

        # Exchange code for token
        token_data = await InstagramOAuthService.exchange_code_for_token(code, redirect_uri)

        # Store credential in database
        cred = await PlatformCredential.store(
            db=db,
            user_id=user.id,
            platform="instagram",
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_expires_at=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 5184000)),
            platform_user_id=token_data.get("instagram_business_account_id"),
        )

        logger.info(f"Instagram OAuth: Token stored for user {user.id}")

        # Redirect to dashboard
        return RedirectResponse(url="/dashboard?platform=instagram&status=connected")

    except Exception as e:
        logger.error(f"Instagram OAuth callback error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token exchange failed")


@router.get("/credentials/{platform}")
async def get_credentials(
    platform: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get stored credentials for a platform."""
    cred = await PlatformCredential.get_for_user(db, user.id, platform)
    if not cred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No credentials found")

    return {
        "platform": cred.platform,
        "platform_user_id": cred.platform_user_id,
        "is_valid": cred.is_valid,
        "expires_at": cred.token_expires_at,
    }
```

### 2️⃣ OAUTH SERVICE LAYER (`services/platform_oauth.py`)

```python
"""Platform OAuth handlers for TikTok and Instagram/Meta."""

import os
import logging
import httpx
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlencode
import secrets

logger = logging.getLogger(__name__)


class TikTokOAuthService:
    """TikTok OAuth 2.0 handler."""

    CLIENT_ID = os.getenv("TIKTOK_CLIENT_ID")  # Production app
    CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
    AUTH_URL = "https://www.tiktok.com/v1/oauth/authorize"
    TOKEN_URL = "https://open-api.tiktok.com/v1/oauth/token"

    @staticmethod
    def get_authorization_url(redirect_uri: str) -> str:
        """Generate TikTok OAuth authorization URL."""
        params = {
            "client_key": TikTokOAuthService.CLIENT_ID,
            "scope": "user.info.basic,video.upload",
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": secrets.token_urlsafe(32),
        }
        return f"{TikTokOAuthService.AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code_for_token(code: str, redirect_uri: str) -> Dict:
        """Exchange auth code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TikTokOAuthService.TOKEN_URL,
                json={
                    "client_key": TikTokOAuthService.CLIENT_ID,
                    "client_secret": TikTokOAuthService.CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )

            if response.status_code != 200:
                logger.error(f"TikTok token exchange failed: {response.text}")
                raise Exception("Token exchange failed")

            data = response.json()
            return {
                "access_token": data.get("access_token"),
                "refresh_token": data.get("refresh_token"),
                "expires_in": data.get("expires_in", 86400),
                "open_id": data.get("open_id"),
            }

    @staticmethod
    async def refresh_token(refresh_token: str) -> Dict:
        """Refresh TikTok access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TikTokOAuthService.TOKEN_URL,
                json={
                    "client_key": TikTokOAuthService.CLIENT_ID,
                    "client_secret": TikTokOAuthService.CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )

            if response.status_code != 200:
                logger.error(f"TikTok token refresh failed: {response.text}")
                raise Exception("Token refresh failed")

            data = response.json()
            return {
                "access_token": data.get("access_token"),
                "refresh_token": data.get("refresh_token"),
                "expires_in": data.get("expires_in", 86400),
            }


class InstagramOAuthService:
    """Instagram/Meta OAuth 2.0 handler."""

    APP_ID = os.getenv("META_APP_ID")
    APP_SECRET = os.getenv("META_APP_SECRET")
    AUTH_URL = "https://www.instagram.com/oauth/authorize"  # or Facebook for more control
    TOKEN_URL = "https://graph.instagram.com/v18.0/oauth/access_token"

    @staticmethod
    def get_authorization_url(redirect_uri: str) -> str:
        """Generate Instagram/Meta OAuth authorization URL."""
        params = {
            "client_id": InstagramOAuthService.APP_ID,
            "redirect_uri": redirect_uri,
            "scope": "instagram_basic,instagram_content_publish",
            "response_type": "code",
            "state": secrets.token_urlsafe(32),
        }
        return f"{InstagramOAuthService.AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code_for_token(code: str, redirect_uri: str) -> Dict:
        """Exchange auth code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                InstagramOAuthService.TOKEN_URL,
                data={
                    "client_id": InstagramOAuthService.APP_ID,
                    "client_secret": InstagramOAuthService.APP_SECRET,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )

            if response.status_code != 200:
                logger.error(f"Instagram token exchange failed: {response.text}")
                raise Exception("Token exchange failed")

            data = response.json()

            # Get Instagram Business Account ID
            ig_account_id = await InstagramOAuthService.get_instagram_business_account(
                data.get("access_token")
            )

            return {
                "access_token": data.get("access_token"),
                "user_id": data.get("user_id"),
                "instagram_business_account_id": ig_account_id,
                "expires_in": data.get("expires_in", 5184000),  # 60 days
            }

    @staticmethod
    async def get_instagram_business_account(access_token: str) -> str:
        """Get Instagram Business Account ID from access token."""
        async with httpx.AsyncClient() as client:
            # Get user's Instagram business account
            response = await client.get(
                "https://graph.instagram.com/v18.0/me/ig_business_account",
                params={"access_token": access_token},
            )

            if response.status_code == 200:
                return response.json().get("instagram_business_account_id")
            else:
                logger.warning("Could not fetch Instagram Business Account ID")
                return None

    @staticmethod
    async def refresh_token(access_token: str) -> Dict:
        """Refresh Instagram access token (long-lived)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.instagram.com/v18.0/refresh_access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "access_token": access_token,
                },
            )

            if response.status_code != 200:
                logger.error(f"Instagram token refresh failed: {response.text}")
                raise Exception("Token refresh failed")

            data = response.json()
            return {
                "access_token": data.get("access_token"),
                "expires_in": data.get("expires_in", 5184000),
            }
```

### 3️⃣ CREDENTIAL MODEL (`db/models.py` → ADD)

```python
class PlatformCredential(Base):
    """Stores OAuth tokens for social platforms."""
    __tablename__ = "platform_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    platform: Mapped[str]  # 'tiktok', 'instagram', 'youtube', 'twitter', 'bluesky'
    platform_user_id: Mapped[Optional[str]]  # User ID from platform (for reference)

    # Encrypted storage
    access_token: Mapped[str]  # encrypted with ENCRYPTION_KEY
    refresh_token: Mapped[Optional[str]]  # encrypted (nullable)
    token_expires_at: Mapped[Optional[datetime]]

    is_valid: Mapped[bool] = mapped_column(default=True)
    last_refreshed_at: Mapped[Optional[datetime]]

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_platform_credentials_user_platform", "user_id", "platform", unique=True),
    )

    @classmethod
    async def store(
        cls,
        db: AsyncSession,
        user_id: int,
        platform: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        platform_user_id: Optional[str] = None,
    ) -> "PlatformCredential":
        """Store or update credentials for a platform."""
        from services.encryption import encrypt_token

        # Check if exists
        result = await db.execute(
            select(cls).where(
                (cls.user_id == user_id) & (cls.platform == platform)
            )
        )
        cred = result.scalar_one_or_none()

        if cred:
            # Update existing
            cred.access_token = encrypt_token(access_token)
            cred.refresh_token = encrypt_token(refresh_token) if refresh_token else None
            cred.token_expires_at = token_expires_at
            cred.platform_user_id = platform_user_id
            cred.is_valid = True
            cred.last_refreshed_at = datetime.utcnow()
        else:
            # Create new
            cred = cls(
                user_id=user_id,
                platform=platform,
                access_token=encrypt_token(access_token),
                refresh_token=encrypt_token(refresh_token) if refresh_token else None,
                token_expires_at=token_expires_at,
                platform_user_id=platform_user_id,
                is_valid=True,
            )
            db.add(cred)

        await db.commit()
        await db.refresh(cred)
        return cred

    @classmethod
    async def get_for_user(
        cls,
        db: AsyncSession,
        user_id: int,
        platform: str,
    ) -> Optional["PlatformCredential"]:
        """Get credentials for a user + platform."""
        result = await db.execute(
            select(cls).where(
                (cls.user_id == user_id) & (cls.platform == platform)
            )
        )
        return result.scalar_one_or_none()

    def get_access_token(self) -> str:
        """Decrypt and return access token."""
        from services.encryption import decrypt_token
        return decrypt_token(self.access_token)

    def get_refresh_token(self) -> Optional[str]:
        """Decrypt and return refresh token."""
        if not self.refresh_token:
            return None
        from services.encryption import decrypt_token
        return decrypt_token(self.refresh_token)
```

### 4️⃣ TOKEN ENCRYPTION (`services/encryption.py`)

```python
"""Token encryption/decryption using Fernet (symmetric)."""

import os
from cryptography.fernet import Fernet

# Load encryption key from .env (already there)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode()
cipher = Fernet(ENCRYPTION_KEY)


def encrypt_token(token: str) -> str:
    """Encrypt a token for storage."""
    return cipher.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token."""
    return cipher.decrypt(encrypted_token.encode()).decode()
```

### 5️⃣ UPDATE .ENV

Add these to your `.env`:

```bash
# TikTok OAuth (Production)
TIKTOK_CLIENT_ID=your_prod_client_id
TIKTOK_CLIENT_SECRET=your_prod_client_secret

# Instagram/Meta OAuth (Production)
META_APP_ID=your_app_id
META_APP_SECRET=your_app_secret

# Remove these (using OAuth instead):
# TIKTOK_USERNAME=
# TIKTOK_PASSWORD=
# INSTAGRAM_USERNAME=
# INSTAGRAM_PASSWORD=
# INSTAGRAM_ACCESS_TOKEN=
```

---

## DEPLOYMENT CHECKLIST

### Before Launch
- [ ] TikTok production app credentials obtained
- [ ] Meta production app credentials obtained
- [ ] Database migration created and tested
- [ ] OAuth endpoints implemented and tested locally
- [ ] Token encryption working
- [ ] Token refresh logic tested
- [ ] Adapters updated to use database tokens

### After Launch
- [ ] Users can authenticate with `/api/oauth/tiktok/start`
- [ ] Users can authenticate with `/api/oauth/instagram/start`
- [ ] Tokens stored securely in database
- [ ] Posting works with new token system
- [ ] Token refresh happens automatically

---

## TIMELINE

- **4A (30 min):** Create OAuth routes
- **4B (30 min):** Add database model + migration
- **4C (1 hour):** Create OAuth service layer
- **4D (30 min):** Update adapters to use DB tokens
- **4E (1 hour):** Testing + validation
- **4F (30 min):** Documentation + deployment

**Total: ~4-5 hours for Phase 4**

