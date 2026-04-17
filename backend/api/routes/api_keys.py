import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_active_user, get_api_key_db
from api.schemas import (
    ApiKeyCreateRequest,
    ApiKeyCreatedResponse,
    ApiKeyDeleteResponse,
    ApiKeyListResponse,
    ErrorResponse,
)
from core.auth import get_password_hash_str
from db import ApiKeyDB

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get(
    "",
    summary="List API keys for the current user",
    responses={
        200: {"model": ApiKeyListResponse, "description": "List of API keys"},
    },
)
def list_api_keys(
    current_user: dict = Depends(get_current_active_user),
    db: ApiKeyDB = Depends(get_api_key_db),
):
    """Return all API keys belonging to the authenticated user (without hashes)."""
    keys = db.list_keys_for_user(current_user["uuid"])
    return {"api_keys": keys}


@router.post(
    "",
    status_code=201,
    summary="Create an API key",
    responses={
        201: {"model": ApiKeyCreatedResponse, "description": "API key created (raw key shown once)"},
    },
)
def create_api_key(
    payload: ApiKeyCreateRequest,
    current_user: dict = Depends(get_current_active_user),
    db: ApiKeyDB = Depends(get_api_key_db),
):
    """Generate a new API key for the authenticated user.

    The raw key is returned exactly once in this response and is never stored.
    """
    MAX_KEYS_PER_USER = 25
    existing_keys = db.list_keys_for_user(current_user["uuid"])
    if len(existing_keys) >= MAX_KEYS_PER_USER:
        raise HTTPException(status_code=400, detail=f"Maximum of {MAX_KEYS_PER_USER} API keys per user reached")

    raw_key = secrets.token_urlsafe(48)
    key_id = str(uuid.uuid4())

    record = db.insert_api_key({
        "id": key_id,
        "user_uuid": current_user["uuid"],
        "name": payload.name,
        "key_hash": get_password_hash_str(raw_key),
        "prefix": raw_key[:8],
    })

    # Fetch the full row to get the DB-generated created_at timestamp
    full_record = db.get_key(key_id)
    return {
        **record,
        "raw_key": raw_key,
        "created_at": full_record["created_at"] if full_record else None,
    }


@router.delete(
    "/{key_id}",
    summary="Delete an API key",
    responses={
        200: {"model": ApiKeyDeleteResponse, "description": "API key deleted"},
        404: {"model": ErrorResponse, "description": "API key not found"},
    },
)
def delete_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: ApiKeyDB = Depends(get_api_key_db),
):
    """Delete one of the authenticated user's API keys."""
    if not db.delete_key(key_id, current_user["uuid"]):
        raise HTTPException(status_code=404, detail="API key not found")
    return {"message": "API key deleted successfully"}
