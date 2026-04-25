"""
Configuration Management with Startup Validation
Validates all required environment variables at startup.
No silent fallbacks in production.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration is invalid."""
    pass


class Config:
    """Application configuration with strict validation."""

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://suno:suno@localhost:5432/suno_clips")

    # Redis (for job queue)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Whop Webhook
    WHOP_WEBHOOK_SECRET: str = os.getenv("WHOP_WEBHOOK_SECRET", "")
    WHOP_API_KEY: str = os.getenv("WHOP_API_KEY", "")
    WHOP_PRODUCT_ID: str = os.getenv("WHOP_PRODUCT_ID", "")

    # SUNO Internal API
    SUNO_API_KEY: str = os.getenv("SUNO_API_KEY", "")
    SUNO_API_BASE: str = os.getenv("SUNO_API_BASE", "http://localhost:8001")

    # Anthropic (Claude AI)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Deployment environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Safety mode
    SUNO_MODE: str = os.getenv("SUNO_MODE", "production")  # self-use or production

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SQL_ECHO: bool = os.getenv("SQL_ECHO", "false").lower() == "true"

    @classmethod
    def validate(cls) -> None:
        """
        Validate all required configuration at startup.

        Raises:
            ConfigError: If any required config is missing or invalid
        """
        logger.info(f"Validating configuration (environment: {cls.ENVIRONMENT})...")

        # Database (always required)
        if not cls.DATABASE_URL:
            raise ConfigError("DATABASE_URL is required")
        logger.info(f"✓ Database configured: {cls.DATABASE_URL.split('@')[-1]}")

        # Redis (always required for queueing)
        if not cls.REDIS_URL:
            raise ConfigError("REDIS_URL is required for job queueing")
        logger.info(f"✓ Redis configured: {cls.REDIS_URL}")

        # Production-specific validation
        if cls.ENVIRONMENT == "production":
            logger.info("Production mode detected - enforcing strict validation...")

            # Webhook secret (required for webhook endpoint)
            if not cls.WHOP_WEBHOOK_SECRET:
                raise ConfigError(
                    "CRITICAL: WHOP_WEBHOOK_SECRET is required in production. "
                    "Cannot securely receive webhooks without it."
                )
            logger.info("✓ Whop webhook secret configured")

            # SUNO API key (required for account provisioning)
            if not cls.SUNO_API_KEY:
                raise ConfigError(
                    "CRITICAL: SUNO_API_KEY is required in production. "
                    "Provisioning cannot proceed without SUNO internal API credentials."
                )
            logger.info("✓ SUNO API key configured")

            # Anthropic API key (required for caption generation)
            if not cls.ANTHROPIC_API_KEY:
                raise ConfigError(
                    "CRITICAL: ANTHROPIC_API_KEY is required in production. "
                    "Caption generation cannot proceed without Claude AI access."
                )
            logger.info("✓ Anthropic API key configured")

        else:
            # Development mode - allow stubs
            logger.warning("Development mode - using stubs for optional APIs")

            if not cls.WHOP_WEBHOOK_SECRET:
                logger.warning("⚠ WHOP_WEBHOOK_SECRET not set - webhook validation disabled")

            if not cls.SUNO_API_KEY:
                logger.warning("⚠ SUNO_API_KEY not set - provisioning will stub")

            if not cls.ANTHROPIC_API_KEY:
                logger.warning("⚠ ANTHROPIC_API_KEY not set - caption generation will stub")

        # Validate environment is one of: development, staging, production
        if cls.ENVIRONMENT not in ["development", "staging", "production"]:
            raise ConfigError(f"ENVIRONMENT must be one of: development, staging, production")

        # Validate SUNO_MODE
        if cls.SUNO_MODE not in ["self-use", "production"]:
            raise ConfigError(f"SUNO_MODE must be 'self-use' or 'production'")

        if cls.SUNO_MODE == "self-use":
            logger.warning("⚠ SELF-USE MODE ENABLED - Applying strict safety limits")

        logger.info("✓ All configuration validated successfully")

    @classmethod
    def get_summary(cls) -> str:
        """Get configuration summary for logging."""
        return f"""
SUNO Configuration Summary:
├─ Environment: {cls.ENVIRONMENT}
├─ Mode: {cls.SUNO_MODE}
├─ Database: {cls.DATABASE_URL.split("@")[-1] if "@" in cls.DATABASE_URL else "sqlite"}
├─ Redis: {cls.REDIS_URL}
├─ Whop: {'✓' if cls.WHOP_WEBHOOK_SECRET else '✗'}
├─ SUNO API: {'✓' if cls.SUNO_API_KEY else '✗'}
├─ Claude AI: {'✓' if cls.ANTHROPIC_API_KEY else '✗'}
├─ Debug: {cls.DEBUG}
└─ Log Level: {cls.LOG_LEVEL}
"""


def init_config() -> None:
    """
    Initialize configuration at application startup.

    Call this once at app startup before any other imports.
    """
    logger.info("="*60)
    logger.info("SUNO STARTUP")
    logger.info("="*60)

    try:
        Config.validate()
        logger.info(Config.get_summary())
    except ConfigError as e:
        logger.error("="*60)
        logger.error(f"CONFIGURATION ERROR: {e}")
        logger.error("="*60)
        raise
    except Exception as e:
        logger.error("="*60)
        logger.error(f"UNEXPECTED ERROR: {e}")
        logger.error("="*60)
        raise
