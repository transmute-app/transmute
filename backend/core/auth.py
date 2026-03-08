from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from core.settings import get_settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password using bcrypt.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to compare against

    Returns:
        True if the password is correct, False otherwise
    """
    return bcrypt.checkpw(
        bytes(plain_password, encoding="utf-8"),
        bytes(hashed_password, encoding="utf-8"),
    )

def get_password_hash_str(password: str) -> str:
    """Hash a password using bcrypt and return the hashed password as a string.

    Args:
        password: The plain text password to hash

    Returns:
        The hashed password as a string
    """
    return bcrypt.hashpw(
        bytes(password, encoding="utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def create_access_token(subject: str, expires_delta: timedelta | None = None, extra_claims: dict | None = None) -> tuple[str, int]:
    """Create a signed JWT access token for the given subject."""
    settings = get_settings()
    lifetime = expires_delta or timedelta(minutes=settings.auth_access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + lifetime,
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.auth_secret_key, algorithm=settings.auth_algorithm)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    settings = get_settings()
    return jwt.decode(token, settings.auth_secret_key, algorithms=[settings.auth_algorithm])