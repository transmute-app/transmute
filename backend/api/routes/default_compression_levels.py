from fastapi import APIRouter, Depends, HTTPException
from core import media_type_aliases
from db import DefaultCompressionLevelsDB
from api.deps import get_current_active_user, get_default_compression_levels_db
from api.schemas import DefaultCompressionLevelMapping, DefaultCompressionLevelListResponse


def _normalize_format(media_format: str) -> str:
    """Map an alias (e.g. ``jpg``) to its canonical format (e.g. ``jpeg``)."""
    lower = media_format.lower()
    return media_type_aliases.get(lower, lower)

router = APIRouter(prefix="/default-compression-levels", tags=["default-compression-levels"])

@router.get(
    "",
    summary="Get all default compression-level mappings",
    responses={
        200: {
            "model": DefaultCompressionLevelListResponse,
            "description": "List of default compression-level mappings"
        }
    }
)
def get_default_compression_levels(
    db: DefaultCompressionLevelsDB = Depends(get_default_compression_levels_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Return all user-configured default compression-level mappings."""
    return {"defaults": db.get_all(current_user["uuid"])}

@router.put(
    "",
    summary="Set a default compression-level mapping",
    responses={
        200: {
            "model": DefaultCompressionLevelMapping,
            "description": "The created or updated mapping"
        }
    }
)
def upsert_default_compression_level(
    mapping: DefaultCompressionLevelMapping,
    db: DefaultCompressionLevelsDB = Depends(get_default_compression_levels_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Create or update a default compression level for a given media format."""
    return db.upsert(current_user["uuid"], _normalize_format(mapping.media_format), mapping.compression_level)

@router.delete(
    "/{media_format}",
    summary="Delete a default compression-level mapping",
    responses={
        200: {"description": "Mapping deleted"},
        404: {"description": "Mapping not found"}
    }
)
def delete_default_compression_level(
    media_format: str,
    db: DefaultCompressionLevelsDB = Depends(get_default_compression_levels_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Remove a default compression-level mapping for the given media format."""
    normalized_format = _normalize_format(media_format)
    if not db.delete(current_user["uuid"], normalized_format):
        raise HTTPException(status_code=404, detail=f"No default compression level for '{media_format}'")
    return {"message": f"Default compression level for '{media_format}' deleted"}
