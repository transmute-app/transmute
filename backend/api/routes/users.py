import sqlite3
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api.deps import (
    get_current_active_user, get_current_admin_user, get_current_user_optional, get_user_db,
    get_api_key_db, get_file_db, get_conversion_db, get_conversion_relations_db, get_settings_db,
    get_default_formats_db,
)
from api.schemas import (
    ErrorResponse,
    UserAuthRequest,
    UserAuthResponse,
    UserBootstrapStatusResponse,
    UserCreateRequest,
    UserDeleteResponse,
    UserListResponse,
    UserResponse,
    UserSelfUpdateRequest,
    UserUpdateRequest,
)
from core import delete_file_and_metadata
from core.auth import create_access_token, get_password_hash_str, verify_password
from db import UserDB, ApiKeyDB, FileDB, ConversionDB, ConversionRelationsDB, SettingsDB, DefaultFormatsDB

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/bootstrap-status",
    summary="Get bootstrap status",
    responses={
        200: {
            "model": UserBootstrapStatusResponse,
            "description": "Whether first-time user setup is required"
        }
    }
)
def get_bootstrap_status(db: UserDB = Depends(get_user_db)):
    """Return whether the application still needs its first admin account."""
    user_count = db.count_users()
    return {"requires_setup": user_count == 0, "user_count": user_count}


def _serialize_user(user: dict) -> dict:
    """Return a response-safe user representation."""
    return {
        "uuid": user["uuid"],
        "username": user["username"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "disabled": user["disabled"],
    }


def _build_auth_response(user: dict) -> dict:
    """Issue a JWT for a validated user and return an OAuth2-style response."""
    access_token, expires_in = create_access_token(
        subject=user["uuid"],
        extra_claims={
            "username": user["username"],
            "role": user["role"],
        },
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",  # nosec B105, not a hardcoded password
        "expires_in": expires_in,
        "user": _serialize_user(user),
    }


@router.get(
    "",
    summary="List all users",
    responses={
        200: {
            "model": UserListResponse,
            "description": "List of users"
        }
    }
)
def list_users(
    db: UserDB = Depends(get_user_db),
    current_user: dict = Depends(get_current_admin_user)
):
    """Return all users without exposing password hashes."""
    return {"users": [_serialize_user(user) for user in db.list_users()]}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
    responses={
        201: {
            "model": UserResponse,
            "description": "Created user"
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid input"
        },
        409: {
            "model": ErrorResponse,
            "description": "Username already exists"
        }
    }
)
def create_user(
    payload: UserCreateRequest,
    db: UserDB = Depends(get_user_db),
    current_user: dict | None = Depends(get_current_user_optional)
):
    """Create a new user and hash the provided password before storage."""
    if db.username_exists(payload.username):
        raise HTTPException(status_code=409, detail=f"Username '{payload.username}' already exists")

    has_existing_users = db.has_users()
    if has_existing_users:
        if current_user is None:
            raise HTTPException(status_code=401, detail="Authentication is required to create additional users")
        if current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin privileges are required")

    role = "admin" if not has_existing_users else payload.role
    disabled = False if not has_existing_users else payload.disabled

    try:
        created_user = db.insert_user({
            "uuid": str(uuid.uuid4()),
            "username": payload.username,
            "email": payload.email,
            "full_name": payload.full_name,
            "hashed_password": get_password_hash_str(payload.password),
            "role": role,
            "disabled": disabled,
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Username '{payload.username}' already exists")

    return _serialize_user(created_user)


@router.post(
    "/token",
    summary="Issue an OAuth2 bearer token",
    responses={
        200: {
            "model": UserAuthResponse,
            "description": "Token issued successfully"
        },
        401: {
            "model": ErrorResponse,
            "description": "Invalid credentials"
        },
        403: {
            "model": ErrorResponse,
            "description": "User account is disabled"
        }
    }
)
def issue_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: UserDB = Depends(get_user_db)
):
    """Issue a JWT bearer token using the OAuth2 password flow form."""
    user = db.get_user_by_username(form_data.username)
    if user is None or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if user["disabled"]:
        raise HTTPException(status_code=403, detail="User account is disabled")
    return _build_auth_response(user)


@router.post(
    "/authenticate",
    summary="Authenticate a user",
    responses={
        200: {
            "model": UserAuthResponse,
            "description": "Authentication succeeded"
        },
        401: {
            "model": ErrorResponse,
            "description": "Invalid credentials"
        },
        403: {
            "model": ErrorResponse,
            "description": "User account is disabled"
        }
    }
)
def authenticate_user(
    payload: UserAuthRequest,
    db: UserDB = Depends(get_user_db)
):
    """Validate username and password and issue a JWT bearer token."""
    user = db.get_user_by_username(payload.username)
    if user is None or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if user["disabled"]:
        raise HTTPException(status_code=403, detail="User account is disabled")
    return _build_auth_response(user)


@router.get(
    "/me",
    summary="Get the authenticated user",
    responses={
        200: {
            "model": UserResponse,
            "description": "Current authenticated user"
        },
        401: {
            "model": ErrorResponse,
            "description": "Missing or invalid bearer token"
        },
        403: {
            "model": ErrorResponse,
            "description": "User account is disabled"
        }
    }
)
def get_me(current_user: dict = Depends(get_current_active_user)):
    """Return the authenticated user derived from the bearer token."""
    return _serialize_user(current_user)


@router.get(
    "/{user_uuid}",
    summary="Get a user by UUID",
    responses={
        200: {
            "model": UserResponse,
            "description": "User details"
        },
        404: {
            "model": ErrorResponse,
            "description": "User not found"
        }
    }
)
def get_user(
    user_uuid: str,
    db: UserDB = Depends(get_user_db),
    current_user: dict = Depends(get_current_admin_user)
):
    """Return a user by UUID without exposing the password hash."""
    user = db.get_user(user_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail=f"No user found with uuid {user_uuid}")
    return _serialize_user(user)


@router.patch(
    "/me",
    summary="Update the authenticated user",
    responses={
        200: {
            "model": UserResponse,
            "description": "Updated current user"
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid input"
        },
        401: {
            "model": ErrorResponse,
            "description": "Missing or invalid bearer token"
        },
        409: {
            "model": ErrorResponse,
            "description": "Username already exists"
        }
    }
)
def update_me(
    updates: UserSelfUpdateRequest,
    db: UserDB = Depends(get_user_db),
    current_user: dict = Depends(get_current_active_user)
):
    """Allow a user to update their own account except for role changes."""
    payload = updates.model_dump(exclude_none=True)
    if "username" in payload and db.username_exists(payload["username"], exclude_uuid=current_user["uuid"]):
        raise HTTPException(status_code=409, detail=f"Username '{payload['username']}' already exists")
    if "password" in payload:
        payload["hashed_password"] = get_password_hash_str(payload.pop("password"))

    try:
        user = db.update_user(current_user["uuid"], payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already exists")

    if user is None:
        raise HTTPException(status_code=404, detail=f"No user found with uuid {current_user['uuid']}")
    return _serialize_user(user)


@router.patch(
    "/{user_uuid}",
    summary="Update a user",
    responses={
        200: {
            "model": UserResponse,
            "description": "Updated user"
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid input"
        },
        404: {
            "model": ErrorResponse,
            "description": "User not found"
        },
        409: {
            "model": ErrorResponse,
            "description": "Username already exists"
        }
    }
)
def update_user(
    user_uuid: str,
    updates: UserUpdateRequest,
    db: UserDB = Depends(get_user_db),
    current_user: dict = Depends(get_current_admin_user)
):
    """Partially update a user, hashing a replacement password when provided."""
    if db.get_user(user_uuid) is None:
        raise HTTPException(status_code=404, detail=f"No user found with uuid {user_uuid}")

    payload = updates.model_dump(exclude_none=True)
    if "username" in payload and db.username_exists(payload["username"], exclude_uuid=user_uuid):
        raise HTTPException(status_code=409, detail=f"Username '{payload['username']}' already exists")
    if "password" in payload:
        payload["hashed_password"] = get_password_hash_str(payload.pop("password"))

    # Prevent admins from demoting themselves
    if user_uuid == current_user["uuid"] and payload.get("role") and payload["role"] != "admin":
        raise HTTPException(status_code=400, detail="Cannot demote your own admin account")

    try:
        user = db.update_user(user_uuid, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already exists")

    if user is None:
        raise HTTPException(status_code=404, detail=f"No user found with uuid {user_uuid}")
    return _serialize_user(user)


@router.delete(
    "/{user_uuid}",
    summary="Delete a user",
    responses={
        200: {
            "model": UserDeleteResponse,
            "description": "User deleted successfully"
        },
        404: {
            "model": ErrorResponse,
            "description": "User not found"
        }
    }
)
def delete_user(
    user_uuid: str,
    db: UserDB = Depends(get_user_db),
    current_user: dict = Depends(get_current_admin_user),
    api_key_db: ApiKeyDB = Depends(get_api_key_db),
    file_db: FileDB = Depends(get_file_db),
    conversion_db: ConversionDB = Depends(get_conversion_db),
    conversion_relations_db: ConversionRelationsDB = Depends(get_conversion_relations_db),
    settings_db: SettingsDB = Depends(get_settings_db),
    default_formats_db: DefaultFormatsDB = Depends(get_default_formats_db),
):
    """Delete a user by UUID and cascade-remove all their data."""
    if user_uuid == current_user["uuid"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    if not db.get_user(user_uuid):
        raise HTTPException(status_code=404, detail=f"No user found with uuid {user_uuid}")

    # Cascade: remove all data belonging to the user
    api_key_db.delete_all_keys_for_user(user_uuid)
    for f in file_db.list_files(user_id=user_uuid):
        delete_file_and_metadata(f["id"], file_db, raise_if_not_found=False)
    for c in conversion_db.list_files(user_id=user_uuid):
        delete_file_and_metadata(c["id"], conversion_db, raise_if_not_found=False)
        conversion_relations_db.delete_relation_by_converted(c["id"])
    settings_db.delete_settings(user_uuid)
    default_formats_db.delete_all(user_uuid)

    if not db.delete_user(user_uuid):
        raise HTTPException(status_code=404, detail=f"No user found with uuid {user_uuid}")
    return {"message": "User deleted successfully"}