import pytest
from datetime import timedelta

from core.auth import (
    verify_password,
    get_password_hash_str,
    create_access_token,
    decode_access_token,
)


# ── password hashing & verification ─────────────────────────────────

def test_hash_and_verify_password():
    raw = "sup3rS3cret!"
    hashed = get_password_hash_str(raw)
    assert hashed != raw
    assert verify_password(raw, hashed)

def test_verify_password_wrong():
    hashed = get_password_hash_str("correct-password")
    assert verify_password("wrong-password", hashed) is False

def test_hash_returns_unique_salts():
    h1 = get_password_hash_str("same")
    h2 = get_password_hash_str("same")
    assert h1 != h2  # bcrypt salts differ


# ── JWT token creation & decoding ────────────────────────────────────

@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    """Provide a deterministic secret key so tokens are verifiable."""
    class _FakeSettings:
        auth_secret_key = "test-secret-key-for-jwt-minimum-32bytes!"
        auth_algorithm = "HS256"
        auth_access_token_expire_minutes = 30

    monkeypatch.setattr("core.auth.get_settings", lambda: _FakeSettings())

def test_create_and_decode_token():
    token, ttl = create_access_token("user-42")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-42"
    assert ttl == 30 * 60

def test_token_with_custom_expiry():
    delta = timedelta(hours=2)
    token, ttl = create_access_token("u1", expires_delta=delta)
    assert ttl == 7200
    payload = decode_access_token(token)
    assert payload["sub"] == "u1"

def test_token_with_extra_claims():
    token, _ = create_access_token("u1", extra_claims={"role": "admin"})
    payload = decode_access_token(token)
    assert payload["role"] == "admin"
    assert payload["sub"] == "u1"

def test_decode_invalid_token():
    import jwt as pyjwt
    with pytest.raises(pyjwt.exceptions.DecodeError):
        decode_access_token("not.a.valid.token")

def test_decode_expired_token():
    import jwt as pyjwt
    token, _ = create_access_token("u1", expires_delta=timedelta(seconds=-1))
    with pytest.raises(pyjwt.exceptions.ExpiredSignatureError):
        decode_access_token(token)
