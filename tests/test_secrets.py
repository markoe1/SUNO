"""Secrets service tests."""

import os
import pytest
from cryptography.fernet import Fernet


def test_encrypt_decrypt_roundtrip():
    from services.secrets import encrypt_blob, decrypt_blob

    original = {"cookies": {"session": "abc123", "auth": "xyz789"}, "extra": 42}
    blob = encrypt_blob(original)
    assert isinstance(blob, str)
    assert blob != str(original)

    recovered = decrypt_blob(blob)
    assert recovered == original


def test_wrong_key_fails(monkeypatch):
    from services import secrets

    # Encrypt with one key
    key1 = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key1)
    blob = secrets.encrypt_blob({"data": "secret"})

    # Try decrypting with a different key
    key2 = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key2)

    with pytest.raises(ValueError, match="Failed to decrypt"):
        secrets.decrypt_blob(blob)


def test_empty_blob():
    from services.secrets import encrypt_blob, decrypt_blob

    original = {}
    blob = encrypt_blob(original)
    assert decrypt_blob(blob) == {}


def test_nested_data_preserved():
    from services.secrets import encrypt_blob, decrypt_blob

    original = {
        "cookies": {
            "_session": "abc",
            "auth_token": "xyz",
            "cf_clearance": "clearance_value",
        },
        "metadata": {"exported_at": "2026-03-03"},
    }
    assert decrypt_blob(encrypt_blob(original)) == original


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    from importlib import reload
    import services.secrets as s_mod

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        s_mod._fernet()
