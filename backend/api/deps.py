"""FastAPI dependency injection functions for database connections."""
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError

from core.auth import decode_access_token, verify_password
from db import FileDB, ConversionDB, ConversionRelationsDB, SettingsDB, DefaultFormatsDB, UserDB, ApiKeyDB

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/users/token", auto_error=False)


@lru_cache(maxsize=1)
def _file_db() -> FileDB:
    return FileDB()


@lru_cache(maxsize=1)
def _conversion_db() -> ConversionDB:
    return ConversionDB()


@lru_cache(maxsize=1)
def _conversion_relations_db() -> ConversionRelationsDB:
    return ConversionRelationsDB()


@lru_cache(maxsize=1)
def _settings_db() -> SettingsDB:
    return SettingsDB()


@lru_cache(maxsize=1)
def _user_db() -> UserDB:
    return UserDB()


def get_file_db() -> FileDB:
    """Dependency that provides a shared FileDB instance."""
    return _file_db()


def get_conversion_db() -> ConversionDB:
    """Dependency that provides a shared ConversionDB instance."""
    return _conversion_db()


def get_conversion_relations_db() -> ConversionRelationsDB:
    """Dependency that provides a shared ConversionRelationsDB instance."""
    return _conversion_relations_db()


def get_settings_db() -> SettingsDB:
    """Dependency that provides a shared SettingsDB instance."""
    return _settings_db()


def get_user_db() -> UserDB:
    """Dependency that provides a shared UserDB instance."""
    return _user_db()


@lru_cache(maxsize=1)
def _api_key_db() -> ApiKeyDB:
    return ApiKeyDB()


def get_api_key_db() -> ApiKeyDB:
    """Dependency that provides a shared ApiKeyDB instance."""
    return _api_key_db()


def _resolve_user_from_api_key(raw_key: str, api_key_db: ApiKeyDB, user_db: UserDB) -> dict | None:
    """Attempt to match a raw API key against stored hashes and return the owning user."""
    # bcrypt silently truncates at 72 bytes; API keys are always shorter.
    # If the token is longer it's certainly not an API key (likely a JWT).
    if len(raw_key.encode("utf-8")) > 72:
        return None
    # Use the stored prefix (first 8 chars) to narrow the search
    prefix = raw_key[:8]
    candidates = api_key_db.get_keys_by_prefix(prefix)
    for key_record in candidates:
        if verify_password(raw_key, key_record["key_hash"]):
            user = user_db.get_user(key_record["user_uuid"])
            if user is not None and user.get("disabled"):
                return None
            return user
    return None


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    user_db: UserDB = Depends(get_user_db),
    api_key_db: ApiKeyDB = Depends(get_api_key_db),
) -> dict:
    """Resolve the current user from a bearer token (JWT or API key)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Try JWT first
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if isinstance(subject, str) and subject:
            user = user_db.get_user(subject)
            if user is not None:
                return user
    except InvalidTokenError:
        pass

    # Fall back to API key
    user = _resolve_user_from_api_key(token, api_key_db, user_db)
    if user is not None:
        return user

    raise credentials_exception


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme_optional),
    user_db: UserDB = Depends(get_user_db),
    api_key_db: ApiKeyDB = Depends(get_api_key_db),
) -> dict | None:
    """Best-effort bearer token resolution for bootstrap-aware routes."""
    if not token:
        return None

    # Try JWT first
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if isinstance(subject, str) and subject:
            user = user_db.get_user(subject)
            if user is not None:
                return user
    except InvalidTokenError:
        pass

    # Fall back to API key
    return _resolve_user_from_api_key(token, api_key_db, user_db)


def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Ensure the current user exists and is not disabled."""
    if current_user["disabled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    return current_user


def get_current_admin_user(current_user: dict = Depends(get_current_active_user)) -> dict:
    """Ensure the current user has the admin role."""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges are required",
        )
    return current_user


@lru_cache(maxsize=1)
def _default_formats_db() -> DefaultFormatsDB:
    return DefaultFormatsDB()


def get_default_formats_db() -> DefaultFormatsDB:
    """Dependency that provides a shared DefaultFormatsDB instance."""
    return _default_formats_db()
