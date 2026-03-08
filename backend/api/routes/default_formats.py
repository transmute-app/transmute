from fastapi import APIRouter, Depends, HTTPException
from db import DefaultFormatsDB
from api.deps import get_current_active_user, get_default_formats_db
from api.schemas import DefaultFormatMapping, DefaultFormatListResponse
from core import media_type_aliases

router = APIRouter(prefix="/default-formats", tags=["default-formats"])


@router.get(
    "",
    summary="Get all default format mappings",
    responses={
        200: {
            "model": DefaultFormatListResponse,
            "description": "List of default format mappings"
        }
    }
)
def get_default_formats(
    db: DefaultFormatsDB = Depends(get_default_formats_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Return all user-configured default format mappings."""
    return {"defaults": db.get_all(current_user["uuid"]), "aliases": media_type_aliases}


@router.put(
    "",
    summary="Set a default format mapping",
    responses={
        200: {
            "model": DefaultFormatMapping,
            "description": "The created or updated mapping"
        }
    }
)
def upsert_default_format(
    mapping: DefaultFormatMapping,
    db: DefaultFormatsDB = Depends(get_default_formats_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Create or update a default output format for a given input format."""
    return db.upsert(current_user["uuid"], mapping.input_format, mapping.output_format)


@router.delete(
    "/{input_format}",
    summary="Delete a default format mapping",
    responses={
        200: {"description": "Mapping deleted"},
        404: {"description": "Mapping not found"}
    }
)
def delete_default_format(
    input_format: str,
    db: DefaultFormatsDB = Depends(get_default_formats_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Remove a default format mapping for the given input format."""
    if not db.delete(current_user["uuid"], input_format):
        raise HTTPException(status_code=404, detail=f"No default mapping for '{input_format}'")
    return {"message": f"Default mapping for '{input_format}' deleted"}
