"""Regression tests for guest session resumption (GHSA-38pw-jjq6-6w6p).

A guest's UUID is disclosed by the admin user list, so possession of one must
not be enough to resume that guest's session and read their files.
"""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import api.routes.guest as guest_mod
from api.routes.guest import _sign_guest_id, create_guest_session

VICTIM_UUID = str(uuid.uuid4())


@pytest.fixture
def guest_settings(monkeypatch):
    settings = MagicMock()
    settings.allow_unauthenticated = True
    settings.auth_secret_key = "test-secret-key"
    settings.app_url = "https://transmute.example"
    monkeypatch.setattr(guest_mod, "get_settings", lambda: settings)
    return settings


def _guest_record(guest_uuid=VICTIM_UUID):
    return {
        "uuid": guest_uuid,
        "username": f"guest_{guest_uuid[:8]}",
        "email": None,
        "full_name": None,
        "role": "guest",
        "disabled": False,
        "is_guest": True,
    }


def _run(cookie_value):
    user_db = MagicMock()
    user_db.has_non_guest_users.return_value = True
    user_db.get_user.return_value = _guest_record()
    user_db.insert_user.side_effect = lambda payload: {**payload, "is_guest": True}

    request = MagicMock()
    request.cookies = {"transmute_guest_id": cookie_value} if cookie_value else {}

    result = create_guest_session(request, MagicMock(), user_db=user_db)
    return result, user_db


def test_raw_uuid_cookie_does_not_resume_session(guest_settings):
    """The pre-fix cookie format must no longer be accepted."""
    result, user_db = _run(VICTIM_UUID)

    user_db.get_user.assert_not_called()
    # A brand new guest is provisioned instead of resuming the victim's.
    assert result["user"]["uuid"] != VICTIM_UUID
    user_db.insert_user.assert_called_once()


def test_tampered_signature_does_not_resume_session(guest_settings):
    forged = f"{VICTIM_UUID}.{'0' * 64}"
    result, user_db = _run(forged)

    user_db.get_user.assert_not_called()
    assert result["user"]["uuid"] != VICTIM_UUID


def test_signature_is_bound_to_its_own_uuid(guest_settings):
    """A valid signature must not transfer to a different guest's UUID."""
    attacker_cookie = _sign_guest_id(str(uuid.uuid4()))
    stolen_signature = attacker_cookie.rpartition(".")[2]

    result, user_db = _run(f"{VICTIM_UUID}.{stolen_signature}")

    user_db.get_user.assert_not_called()
    assert result["user"]["uuid"] != VICTIM_UUID


def test_signed_cookie_resumes_the_session(guest_settings):
    result, user_db = _run(_sign_guest_id(VICTIM_UUID))

    user_db.get_user.assert_called_once_with(VICTIM_UUID)
    user_db.insert_user.assert_not_called()
    assert result["user"]["uuid"] == VICTIM_UUID


def test_issued_cookie_is_signed(guest_settings):
    user_db = MagicMock()
    user_db.has_non_guest_users.return_value = True
    user_db.insert_user.side_effect = lambda payload: {**payload, "is_guest": True}

    request = MagicMock()
    request.cookies = {}
    response = MagicMock()

    create_guest_session(request, response, user_db=user_db)

    cookie_value = response.set_cookie.call_args.kwargs["value"]
    guest_id, _, signature = cookie_value.rpartition(".")
    assert len(signature) == 64
    assert _sign_guest_id(guest_id) == cookie_value


def test_guest_access_still_gated_on_setting(guest_settings):
    guest_settings.allow_unauthenticated = False

    with pytest.raises(HTTPException) as exc:
        _run(None)

    assert exc.value.status_code == 403
