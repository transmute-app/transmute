from fastapi import APIRouter, Depends, HTTPException
from db import SettingsDB
from api.deps import get_settings_db
from api.schemas import AppSettingsResponse, AppSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


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
def get_app_settings(db: SettingsDB = Depends(get_settings_db)):
    """Return the current application settings."""
    return db.get_settings()


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
    db: SettingsDB = Depends(get_settings_db)
):
    """Partially update application settings. Only provided fields are changed."""
    try:
        return db.update_settings(updates.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
