from fastapi import APIRouter, Depends, HTTPException
from db import SettingsDB
from db.settings_db import BUILTIN_THEME_KEYS
from api.deps import get_current_active_user, get_current_admin_user, get_settings_db
from api.schemas import (
    AppSettingsResponse,
    AppSettingsUpdate,
    CustomThemeCreateRequest,
    CustomThemeListResponse,
    CustomThemeResponse,
    CustomThemeUpdateRequest,
)

router = APIRouter(prefix="/settings", tags=["settings"])

_ADMIN_ONLY_FIELDS = {"cleanup_enabled", "cleanup_ttl_minutes"}


@router.get(
    "",
    summary="Get app settings",
    responses={
        200: {
            "model": AppSettingsResponse,
            "description": "Current app settings"
        }
    }
)
def get_app_settings(
    db: SettingsDB = Depends(get_settings_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Return the current user's application settings.

    Cleanup settings are always sourced from the first admin's row,
    since they are a system-wide concern managed by administrators.
    """
    settings = db.get_settings(current_user["uuid"])
    admin_cleanup = db.get_admin_cleanup_settings()
    settings["cleanup_enabled"] = admin_cleanup["cleanup_enabled"]
    settings["cleanup_ttl_minutes"] = admin_cleanup["cleanup_ttl_minutes"]
    return settings


@router.patch(
    "",
    summary="Update app settings",
    responses={
        200: {
            "model": AppSettingsResponse,
            "description": "Updated app settings"
        },
        400: {
            "description": "Invalid settings value"
        }
    }
)
def update_app_settings(
    updates: AppSettingsUpdate,
    db: SettingsDB = Depends(get_settings_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Partially update the current user's settings. Only provided fields are changed.

    Cleanup settings (cleanup_enabled, cleanup_ttl_minutes) are admin-only.
    """
    payload = updates.model_dump(exclude_none=True)

    # Reject non-admin users from changing cleanup settings
    if current_user["role"] != "admin" and _ADMIN_ONLY_FIELDS & payload.keys():
        raise HTTPException(status_code=403, detail="Cleanup settings can only be changed by an admin")

    try:
        return db.update_settings(current_user["uuid"], payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===== Custom themes =====


@router.get(
    "/themes",
    summary="List custom themes",
    responses={
        200: {
            "model": CustomThemeListResponse,
            "description": "All custom themes plus the built-in theme keys",
        }
    },
)
def list_custom_themes(
    db: SettingsDB = Depends(get_settings_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Return every custom theme registered in the database.

    Available to any authenticated user so the frontend can render the
    theme picker. The built-in keys are returned alongside so the client
    knows which entries are statically defined in CSS.
    """
    return {
        "themes": db.list_custom_themes(),
        "builtins": sorted(BUILTIN_THEME_KEYS),
    }


@router.post(
    "/themes",
    summary="Create a custom theme (admin only)",
    status_code=201,
    responses={
        201: {"model": CustomThemeResponse, "description": "Created theme"},
        400: {"description": "Invalid theme payload"},
        403: {"description": "Admin role required"},
    },
)
def create_custom_theme(
    payload: CustomThemeCreateRequest,
    db: SettingsDB = Depends(get_settings_db),
    current_user: dict = Depends(get_current_admin_user),
):
    """Admin-only endpoint to register a new theme available to every user."""
    try:
        return db.create_custom_theme(
            name=payload.name,
            colors=payload.colors.model_dump(),
            created_by=current_user["uuid"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/themes/{key}",
    summary="Update a custom theme (admin only)",
    responses={
        200: {"model": CustomThemeResponse, "description": "Updated theme"},
        400: {"description": "Invalid theme payload"},
        403: {"description": "Admin role required"},
        404: {"description": "Theme not found"},
    },
)
def update_custom_theme(
    key: str,
    payload: CustomThemeUpdateRequest,
    db: SettingsDB = Depends(get_settings_db),
    current_user: dict = Depends(get_current_admin_user),
):
    """Admin-only endpoint that replaces the display name and/or color tokens of an existing theme."""
    if db.get_custom_theme(key) is None:
        raise HTTPException(status_code=404, detail=f"Custom theme '{key}' not found")
    try:
        return db.update_custom_theme(
            key=key,
            name=payload.name,
            colors=payload.colors.model_dump() if payload.colors is not None else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/themes/{key}",
    summary="Delete a custom theme (admin only)",
    responses={
        204: {"description": "Theme deleted"},
        403: {"description": "Admin role required"},
        404: {"description": "Theme not found"},
    },
    status_code=204,
)
def delete_custom_theme(
    key: str,
    db: SettingsDB = Depends(get_settings_db),
    current_user: dict = Depends(get_current_admin_user),
):
    """Admin-only endpoint. Any user currently selecting this theme is reset to `rubedo`."""
    if not db.delete_custom_theme(key):
        raise HTTPException(status_code=404, detail=f"Custom theme '{key}' not found")
    return None
