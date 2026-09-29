"""Regression tests for OIDC identity linking (GHSA-gp9p-77f3-j7g5).

An incoming OIDC identity must not be attached to an existing local account on
the strength of an email claim the provider has not verified.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import api.routes.oidc as oidc_mod


@pytest.fixture
def oidc_env(monkeypatch, tmp_path):
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://idp.example.com")
    monkeypatch.setenv("OIDC_CLIENT_ID", "transmute")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    from core.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _drive_callback(monkeypatch, userinfo, existing_user, auto_create=True):
    """Run oidc_callback against a provider response and a local account table."""
    monkeypatch.setattr(oidc_mod, "_load_metadata", AsyncMock(return_value={}))

    oauth = MagicMock()
    oauth.oidc.authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})
    monkeypatch.setattr(oidc_mod, "_get_oauth", lambda: oauth)

    settings = oidc_mod.get_settings()
    monkeypatch.setattr(settings, "oidc_auto_create_users", auto_create, raising=False)

    user_db = MagicMock()
    user_db.get_user_by_email.return_value = existing_user
    user_db.has_users.return_value = True
    # Must be falsy: _unique_username() loops until this returns False.
    user_db.username_exists.return_value = False
    user_db.insert_user.side_effect = lambda payload: payload

    identity_db = MagicMock()
    identity_db.get_by_issuer_subject.return_value = None

    request = MagicMock()
    request.scope = {"root_path": ""}

    import asyncio
    response = asyncio.run(
        oidc_mod.oidc_callback(request, user_db=user_db, identity_db=identity_db)
    )
    return response, user_db, identity_db


ADMIN = {
    "uuid": str(uuid.uuid4()),
    "username": "admin",
    "email": "admin@example.test",
    "role": "admin",
    "disabled": False,
}


@pytest.mark.parametrize("email_verified", [False, "false", None, "", 0])
def test_unverified_email_is_not_linked_to_existing_account(monkeypatch, oidc_env, email_verified):
    userinfo = {
        "iss": "https://idp.example.com",
        "sub": "attacker-subject",
        "email": ADMIN["email"],
        "email_verified": email_verified,
    }

    with pytest.raises(HTTPException) as exc:
        _drive_callback(monkeypatch, userinfo, existing_user=ADMIN)

    assert exc.value.status_code == 403


def test_missing_email_verified_claim_is_not_linked(monkeypatch, oidc_env):
    """A provider that omits the claim entirely must fail closed."""
    userinfo = {
        "iss": "https://idp.example.com",
        "sub": "attacker-subject",
        "email": ADMIN["email"],
    }

    with pytest.raises(HTTPException) as exc:
        _drive_callback(monkeypatch, userinfo, existing_user=ADMIN)

    assert exc.value.status_code == 403


@pytest.mark.parametrize("email_verified", [True, "true", "True"])
def test_verified_email_links_to_existing_account(monkeypatch, oidc_env, email_verified):
    userinfo = {
        "iss": "https://idp.example.com",
        "sub": "legit-subject",
        "email": ADMIN["email"],
        "email_verified": email_verified,
    }

    _, _, identity_db = _drive_callback(monkeypatch, userinfo, existing_user=ADMIN)

    identity_db.link_identity.assert_called_once_with(
        ADMIN["uuid"], "https://idp.example.com", "legit-subject"
    )


def test_autocreated_account_does_not_store_unverified_email(monkeypatch, oidc_env):
    """An unverified address must not become a future match target."""
    userinfo = {
        "iss": "https://idp.example.com",
        "sub": "new-subject",
        "email": "someone@example.test",
        "email_verified": False,
        "preferred_username": "someone",
    }

    _, user_db, _ = _drive_callback(monkeypatch, userinfo, existing_user=None)

    created = user_db.insert_user.call_args.args[0]
    assert created["email"] is None
