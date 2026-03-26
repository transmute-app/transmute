import secrets
import time
import uuid

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from api.deps import get_user_db, get_user_identity_db
from core import get_settings
from core.auth import create_access_token
from db import UserDB, UserRole
from db.user_identity_db import UserIdentityDB

router = APIRouter(prefix="/oidc", tags=["oidc"])

_oauth: OAuth | None = None
_metadata_cache: dict | None = None

# Short-lived, single-use code store: code -> (jwt, expiry_timestamp)
_pending_codes: dict[str, tuple[str, int, float]] = {}
_CODE_TTL_SECONDS = 60


def _internal_base() -> str:
    """Return the origin the backend should use for server-to-server calls."""
    settings = get_settings()
    url = settings.oidc_internal_url or settings.oidc_issuer_url
    return _origin(url)


def _external_base() -> str:
    """Return the public origin the browser uses."""
    return _origin(get_settings().oidc_issuer_url)


def _origin(url: str) -> str:
    """Extract scheme + host + port from a URL (e.g. 'http://host:9000')."""
    from urllib.parse import urlparse
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _to_internal(url: str) -> str:
    """Rewrite a URL from the external (public) base to the internal (container) base."""
    ext = _external_base()
    internal = _internal_base()
    if ext != internal and url.startswith(ext):
        return internal + url[len(ext):]
    return url


def _to_external(url: str) -> str:
    """Rewrite a URL from the internal (container) base to the external (public) base."""
    ext = _external_base()
    internal = _internal_base()
    if ext != internal and url.startswith(internal):
        return ext + url[len(internal):]
    return url


async def _load_metadata() -> dict:
    """Fetch and cache OIDC discovery metadata, rewriting URLs as needed.

    Since we fetch from the internal URL, all endpoints in the response use
    the internal hostname.  Browser-facing endpoints must be rewritten to
    the public URL; server-to-server endpoints stay internal.
    """
    global _metadata_cache
    if _metadata_cache is not None:
        return _metadata_cache

    settings = get_settings()
    metadata_url = f"{(settings.oidc_internal_url or settings.oidc_issuer_url).rstrip('/')}/.well-known/openid-configuration"
    async with httpx.AsyncClient() as client:
        resp = await client.get(metadata_url)
        resp.raise_for_status()
        metadata = resp.json()

    # Browser-facing endpoints: rewrite internal → external (public) URL
    for key in ("authorization_endpoint", "end_session_endpoint"):
        if key in metadata:
            metadata[key] = _to_external(metadata[key])

    # Server-to-server endpoints are already internal from the fetch, but
    # ensure they use the internal base in case the provider returns a
    # different canonical URL.
    for key in ("token_endpoint", "userinfo_endpoint", "jwks_uri", "introspection_endpoint", "revocation_endpoint"):
        if key in metadata:
            metadata[key] = _to_internal(metadata[key])

    _metadata_cache = metadata
    return metadata


def _get_oauth() -> OAuth:
    """Return a lazily-configured Authlib OAuth registry."""
    global _oauth
    if _oauth is not None:
        return _oauth

    settings = get_settings()
    _oauth = OAuth()
    _oauth.register(
        name="oidc",  # nosec B106 - this is not a secret, just an identifier for the provider configuration
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        token_endpoint_auth_method="client_secret_post",
        client_kwargs={"scope": "openid email profile"},
    )
    return _oauth


def _oidc_enabled() -> bool:
    settings = get_settings()
    return bool(settings.oidc_issuer_url and settings.oidc_client_id and settings.oidc_client_secret)


@router.get("/config", summary="Get OIDC configuration for the frontend")
def oidc_config():
    """Return whether OIDC is available and its display name (no secrets)."""
    settings = get_settings()
    return {
        "enabled": _oidc_enabled(),
        "display_name": settings.oidc_display_name,
        "allow_unauthenticated": settings.allow_unauthenticated,
    }


@router.get("/login", summary="Start OIDC login flow")
async def oidc_login(request: Request):
    """Redirect the user to the OIDC provider's authorization endpoint."""
    if not _oidc_enabled():
        raise HTTPException(status_code=404, detail="OIDC is not configured")

    oauth = _get_oauth()
    metadata = await _load_metadata()
    oauth.oidc.server_metadata = metadata

    settings = get_settings()
    if not settings.app_url:
        # If no explicit app_url is set, we must assume the provider can reach us at the same URL we use to reach it.
        redirect_uri = str(request.url_for("oidc_callback"))
    else:
        redirect_uri = settings.app_url.rstrip("/") + request.url_for("oidc_callback").path
    # Store a CSRF nonce in the session
    nonce = secrets.token_urlsafe(32)
    request.session["oidc_nonce"] = nonce
    return await oauth.oidc.authorize_redirect(request, redirect_uri, nonce=nonce)


@router.get("/callback", name="oidc_callback", summary="OIDC callback")
async def oidc_callback(
    request: Request,
    user_db: UserDB = Depends(get_user_db),
    identity_db: UserIdentityDB = Depends(get_user_identity_db),
):
    """Handle the OIDC provider callback, link or create a user, and redirect with a session token."""
    if not _oidc_enabled():
        raise HTTPException(status_code=404, detail="OIDC is not configured")

    settings = get_settings()
    oauth = _get_oauth()
    metadata = await _load_metadata()
    oauth.oidc.server_metadata = metadata

    token = await oauth.oidc.authorize_access_token(request)
    nonce = request.session.pop("oidc_nonce", None)
    userinfo = token.get("userinfo")
    if userinfo is None:
        raise HTTPException(status_code=400, detail="OIDC provider did not return user information")

    issuer = userinfo.get("iss", settings.oidc_issuer_url.rstrip("/"))
    subject = userinfo.get("sub")
    if not subject:
        raise HTTPException(status_code=400, detail="OIDC token missing 'sub' claim")

    # --- Lookup or create local user ---
    identity = identity_db.get_by_issuer_subject(issuer, subject)

    if identity is not None:
        # Existing linked identity
        user = user_db.get_user(identity["user_uuid"])
        if user is None:
            raise HTTPException(status_code=500, detail="Linked user no longer exists")
        if user["disabled"]:
            raise HTTPException(status_code=403, detail="User account is disabled")
    else:
        # Try to match by email first (if present and unique)
        email = userinfo.get("email")
        user = user_db.get_user_by_email(email) if email else None

        if user is not None:
            if user["disabled"]:
                raise HTTPException(status_code=403, detail="User account is disabled")
            # Link this OIDC identity to the existing local account
            identity_db.link_identity(user["uuid"], issuer, subject)
        elif settings.oidc_auto_create_users:
            # Auto-provision a new local account.
            # Mirror the bootstrap rule: the very first user becomes admin.
            role = UserRole.ADMIN.value if not user_db.has_users() else UserRole.MEMBER.value
            preferred = userinfo.get("preferred_username") or email or subject
            username = _unique_username(user_db, preferred)
            user = user_db.insert_user({
                "uuid": str(uuid.uuid4()),
                "username": username,
                "email": email,
                "full_name": userinfo.get("name"),
                "hashed_password": _unusable_password(),
                "role": role,
                "disabled": False,
            })
            identity_db.link_identity(user["uuid"], issuer, subject)
        else:
            raise HTTPException(
                status_code=403,
                detail="No local account is linked to this identity and automatic user creation is disabled",
            )

    # --- Issue a JWT and redirect the browser back to the SPA ---
    access_token, expires_in = create_access_token(
        subject=user["uuid"],
        extra_claims={"username": user["username"], "role": user["role"]},
    )

    # Store the JWT behind a single-use opaque code so the token never
    # appears in access logs, proxy logs, or browser history.
    code = secrets.token_urlsafe(48)
    _purge_expired_codes()
    _pending_codes[code] = (access_token, expires_in, time.monotonic() + _CODE_TTL_SECONDS)

    return RedirectResponse(url=f"/?oidc_code={code}")


class _OidcExchangeRequest(BaseModel):
    code: str


@router.post("/exchange", summary="Exchange a one-time OIDC code for a JWT")
def oidc_exchange(payload: _OidcExchangeRequest):
    """Trade the short-lived code from the callback redirect for the real JWT."""
    _purge_expired_codes()
    entry = _pending_codes.pop(payload.code, None)
    if entry is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OIDC code")
    access_token, expires_in, _expiry = entry
    return {
        "access_token": access_token,
        "token_type": "bearer",  # nosec B105
        "expires_in": expires_in,
    }


def _purge_expired_codes() -> None:
    """Remove any codes that have passed their TTL."""
    now = time.monotonic()
    expired = [k for k, (_, _, exp) in _pending_codes.items() if exp <= now]
    for k in expired:
        del _pending_codes[k]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _unusable_password() -> str:
    """Return a bcrypt-shaped hash that can never match any input.

    Users created via OIDC auto-provision don't have a password; this
    placeholder ensures the hashed_password column is always populated
    but can never validate.
    """
    return "!oidc-no-password"


def _unique_username(user_db: UserDB, base: str) -> str:
    """Derive a username that doesn't collide with existing accounts."""
    # Sanitize: keep only alphanumeric, dash, underscore, dot
    sanitized = "".join(c for c in base if c.isalnum() or c in "-_.")
    if not sanitized:
        sanitized = "user"
    candidate = sanitized
    suffix = 1
    while user_db.username_exists(candidate):
        candidate = f"{sanitized}_{suffix}"
        suffix += 1
    return candidate


def attach_session_middleware(app) -> None:
    """Add Starlette session middleware (required for Authlib OIDC state)."""
    settings = get_settings()
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.auth_secret_key,
        session_cookie="transmute_oidc_session",
        max_age=300,  # only needed during the OIDC round-trip
        same_site="lax",
        https_only=False,  # set True when behind TLS
    )
