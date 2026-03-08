from fastapi import APIRouter, Depends, HTTPException
from db import SettingsDB
from api.deps import get_current_active_user, get_settings_db
from api.schemas import AppSettingsResponse, AppSettingsUpdate

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
