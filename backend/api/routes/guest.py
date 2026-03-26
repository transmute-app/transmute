import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.deps import get_user_db
from core import get_settings
from core.auth import create_access_token
from db import UserDB, UserRole

router = APIRouter(prefix="/guest", tags=["guest"])

_GUEST_COOKIE = "transmute_guest_id"
_GUEST_LIFETIME_DAYS = 30


def _serialize_guest(user: dict) -> dict:
    return {
        "uuid": user["uuid"],
        "username": user["username"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "disabled": user["disabled"],
        "is_guest": user["is_guest"],
    }


@router.post("/session", summary="Create or resume a guest session")
def create_guest_session(
    request: Request,
    response: Response,
    user_db: UserDB = Depends(get_user_db),
):
    """Create a new guest user or resume an existing guest session via cookie."""
    settings = get_settings()
    if not settings.allow_unauthenticated:
        raise HTTPException(status_code=403, detail="Guest access is not enabled")

    if not user_db.has_non_guest_users():
        raise HTTPException(status_code=403, detail="Application must be set up before guest access is available")

    # Try to resume an existing guest session from cookie
    guest_uuid = request.cookies.get(_GUEST_COOKIE)
    if guest_uuid:
        user = user_db.get_user(guest_uuid)
        if user and user.get("is_guest") and not user.get("disabled"):
            access_token, expires_in = create_access_token(
                subject=user["uuid"],
                extra_claims={"username": user["username"], "role": user["role"]},
            )
            return {
                "access_token": access_token,
                "token_type": "bearer",  # nosec B105 - this is just a string in the response body, not an actual cookie or header
                "expires_in": expires_in,
                "user": _serialize_guest(user),
            }

    # Create a new guest identity
    guest_id = str(uuid.uuid4())
    username = f"guest_{guest_id[:8]}"
    expires_at = (datetime.now(timezone.utc) + timedelta(days=_GUEST_LIFETIME_DAYS)).strftime("%Y-%m-%d %H:%M:%S")

    user = user_db.insert_user({
        "uuid": guest_id,
        "username": username,
        "email": None,
        "full_name": None,
        "hashed_password": "!guest-no-password",  # nosec B105 - this password is never used for authentication, its just a placeholder to satisfy the schema
        "role": UserRole.GUEST.value,
        "disabled": False,
        "is_guest": True,
        "expires_at": expires_at,
    })

    access_token, expires_in = create_access_token(
        subject=user["uuid"],
        extra_claims={"username": user["username"], "role": user["role"]},
    )

    response.set_cookie(
        key=_GUEST_COOKIE,
        value=guest_id,
        max_age=_GUEST_LIFETIME_DAYS * 24 * 3600,
        httponly=True,
        samesite="strict",
        secure=settings.app_url.startswith("https"),
        path="/api/guest",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",  # nosec B105 - this is just a string in the response body, not an actual cookie or header
        "expires_in": expires_in,
        "user": _serialize_guest(user),
    }
