"""Regression tests for credential-change and disabled-account handling.

Covers GHSA-6h5p-x9v3-h6x5 (password replaced with only a bearer token) and
GHSA-xv67-5v66-38qv (disabled admin's JWT still authorized user creation).
"""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import api.deps as deps
from api.routes.users import create_user, update_me
from api.schemas import UserCreateRequest, UserSelfUpdateRequest
from core.auth import get_password_hash_str

CURRENT_PASSWORD = "correct horse battery"


def _local_user(**overrides):
    user = {
        "uuid": str(uuid.uuid4()),
        "username": "victim",
        "email": "victim@example.test",
        "full_name": None,
        "role": "member",
        "disabled": False,
        "hashed_password": get_password_hash_str(CURRENT_PASSWORD),
    }
    user.update(overrides)
    return user


# --- Password change requires reauthentication ---------------------------


def test_password_change_without_current_password_is_rejected():
    """A stolen token alone must not be enough to replace the password."""
    user = _local_user()
    db = MagicMock()

    with pytest.raises(HTTPException) as exc:
        update_me(UserSelfUpdateRequest(password="attacker-chosen-pw"), db=db, current_user=user)

    assert exc.value.status_code == 403
    db.update_user.assert_not_called()


def test_password_change_with_wrong_current_password_is_rejected():
    user = _local_user()
    db = MagicMock()

    with pytest.raises(HTTPException) as exc:
        update_me(
            UserSelfUpdateRequest(password="attacker-chosen-pw", current_password="guess"),
            db=db,
            current_user=user,
        )

    assert exc.value.status_code == 403
    db.update_user.assert_not_called()


def test_password_change_with_correct_current_password_succeeds():
    user = _local_user()
    db = MagicMock()
    db.username_exists.return_value = False
    db.update_user.return_value = {**user, "username": "victim"}

    update_me(
        UserSelfUpdateRequest(password="a brand new password", current_password=CURRENT_PASSWORD),
        db=db,
        current_user=user,
    )

    stored = db.update_user.call_args.args[1]
    assert "password" not in stored
    assert "current_password" not in stored
    assert stored["hashed_password"] != user["hashed_password"]


def test_profile_update_without_password_needs_no_reauth():
    """The new check must not block ordinary profile edits."""
    user = _local_user()
    db = MagicMock()
    db.username_exists.return_value = False
    db.update_user.return_value = {**user, "full_name": "Victim Example"}

    update_me(UserSelfUpdateRequest(full_name="Victim Example"), db=db, current_user=user)

    stored = db.update_user.call_args.args[1]
    assert stored == {"full_name": "Victim Example"}


# --- Disabled accounts resolve to no user --------------------------------


def _resolve_optional(monkeypatch, user):
    monkeypatch.setattr(deps, "decode_access_token", lambda token: {"sub": user["uuid"]})
    user_db = MagicMock()
    user_db.get_user.return_value = user
    api_key_db = MagicMock()
    return deps.get_current_user_optional(token="jwt", user_db=user_db, api_key_db=api_key_db)


def test_optional_dependency_ignores_disabled_jwt_user(monkeypatch):
    assert _resolve_optional(monkeypatch, _local_user(disabled=True, role="admin")) is None


def test_optional_dependency_still_resolves_active_user(monkeypatch):
    user = _local_user(role="admin")
    assert _resolve_optional(monkeypatch, user) == user


def test_disabled_admin_token_cannot_create_users():
    """The disabled admin's JWT must not mint a fresh enabled admin."""
    db = MagicMock()
    db.username_exists.return_value = False
    db.has_non_guest_users.return_value = True

    payload = UserCreateRequest(username="recovery", password="a valid password", role="admin")

    # The dependency now yields None for a disabled account.
    with pytest.raises(HTTPException) as exc:
        create_user(payload, db=db, current_user=None)

    assert exc.value.status_code == 401
    db.insert_user.assert_not_called()
