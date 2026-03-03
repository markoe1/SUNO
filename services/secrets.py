"""Fernet-based encryption/decryption for user secrets (Whop cookie blobs)."""

import json
import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY environment variable is not set")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_blob(data: dict) -> str:
    """Encrypt a dict to a URL-safe Fernet token string."""
    raw = json.dumps(data).encode("utf-8")
    return _fernet().encrypt(raw).decode("utf-8")


def decrypt_blob(blob: str) -> dict:
    """Decrypt a Fernet token string back to a dict."""
    try:
        raw = _fernet().decrypt(blob.encode("utf-8"))
        return json.loads(raw)
    except (InvalidToken, Exception) as exc:
        raise ValueError(f"Failed to decrypt blob: {exc}") from exc
