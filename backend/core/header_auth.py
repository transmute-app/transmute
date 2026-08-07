"""HTTP header-based authentication helpers (oauth2-proxy and similar)."""
from __future__ import annotations

import re
import uuid

from fastapi import HTTPException, Request

from core.settings import get_settings
from db import UserDB, UserRole

_UNUSABLE_PASSWORD = "!header-auth-no-password"
_USERNAME_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def header_auth_enabled() -> bool:
    return bool(get_settings().header_auth_enabled)


def _header_value(request: Request, header_name: str) -> str | None:
    if not header_name:
        return None
    value = request.headers.get(header_name)
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _sanitize_username(raw: str) -> str:
    cleaned = _USERNAME_SAFE.sub(".", raw.strip())
    cleaned = cleaned.strip(".")
    return cleaned or "user"


def _unique_username(user_db: UserDB, base: str) -> str:
    candidate = _sanitize_username(base)
    if not user_db.username_exists(candidate):
        return candidate
    for index in range(2, 1000):
        next_candidate = f"{candidate}-{index}"
        if not user_db.username_exists(next_candidate):
            return next_candidate
    raise HTTPException(status_code=500, detail="Unable to allocate a unique username")


def resolve_user_from_headers(request: Request, user_db: UserDB) -> dict | None:
    """Resolve or provision a user from trusted reverse-proxy headers."""
    settings = get_settings()
    if not settings.header_auth_enabled:
        return None

    username = _header_value(request, settings.header_auth_username_header)
    if not username:
        return None

    email = _header_value(request, settings.header_auth_email_header)
    user = user_db.get_user_by_username(username)
    if user is None and email:
        user = user_db.get_user_by_email(email)

    if user is not None:
        if user.get("disabled"):
            raise HTTPException(status_code=403, detail="User account is disabled")
        return user

    can_auto_create = bool(settings.header_auth_auto_create or settings.allow_public_signup)
    if not can_auto_create:
        raise HTTPException(
            status_code=401,
            detail="Header authentication user does not exist and auto-create is disabled",
        )

    # Mirror bootstrap: first non-guest user becomes admin; later header users are members.
    role = UserRole.ADMIN.value if not user_db.has_non_guest_users() else UserRole.MEMBER.value
    created = user_db.insert_user({
        "uuid": str(uuid.uuid4()),
        "username": _unique_username(user_db, username),
        "email": email,
        "full_name": username,
        "hashed_password": _UNUSABLE_PASSWORD,
        "role": role,
        "disabled": False,
    })
    return created
