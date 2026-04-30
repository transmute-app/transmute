from pathlib import Path
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException
from registry import registry
from core import get_settings, sanitize_extension, delete_file_and_metadata
from db import ConversionDB, FileDB, ConversionRelationsDB, SettingsDB, DefaultQualitiesDB
from services import ConversionFailedError, run_conversion_job
from api.deps import get_current_active_user, get_file_db, get_conversion_db, get_conversion_relations_db, get_settings_db, get_default_qualities_db
from api.schemas import ConversionRequest, ConversionListResponse, FileMetadata, ErrorResponse, FileDeleteResponse


router = APIRouter(prefix="/conversions", tags=["conversions"])
settings = get_settings()
UPLOAD_DIR = settings.upload_dir
TEMP_DIR = settings.tmp_dir
CONVERTED_DIR = settings.output_dir


def copy_web_alias_to_base(input_path: str, temp_dir: Path, converted_id: str, output_format: str) -> list[str]:
    """Copy a downloader-backed web alias file to its base format without re-encoding."""
    output_path = temp_dir / f"{converted_id}.{output_format}"
    shutil.copy2(input_path, output_path)
    return [str(output_path)]


def copy_webvideo_to_mp4(input_path: str, temp_dir: Path, converted_id: str) -> list[str]:
    """Copy a yt-dlp-backed webvideo to an mp4 output without re-encoding.

    Kept for backwards compatibility with tests and external callers.
    """
    return copy_web_alias_to_base(input_path, temp_dir, converted_id, "mp4")


@router.get(
        "/complete",
        summary="List completed conversions",
        responses={
            200: {
                "model": ConversionListResponse,
                "description": "List of completed conversions with original and converted file metadata"
            }
        }
)
def list_conversions(
    conv_db: ConversionDB = Depends(get_conversion_db),
    conv_rel_db: ConversionRelationsDB = Depends(get_conversion_relations_db),
    current_user: dict = Depends(get_current_active_user),
):
    """List all completed conversions for the current user."""
    converted_files = conv_db.list_files(user_id=current_user["uuid"])
    converted_files_dict = {f['id']: f for f in converted_files}

    relations = conv_rel_db.list_relations(user_id=current_user["uuid"])
    # For each relation, create a conversion-centric record with original file metadata from the relation
    # This uses denormalized data so original files can be deleted without breaking history
    conversion_records = []
    for rel in relations:
        conv_id = rel['converted_file_id']
        if conv_id in converted_files_dict:
            record = dict(converted_files_dict[conv_id])
            # Build original_file metadata from denormalized relation data
            record['original_file'] = {
                'id': rel['original_file_id'],
                'original_filename': rel['original_filename'],
                'media_type': rel['original_media_type'],
                'extension': rel['original_extension'],
                'size_bytes': rel['original_size_bytes']
            }
            conversion_records.append(record)
    
    return {"conversions": conversion_records}


@router.post(
        "",
        summary="Create a new conversion",
        responses={
            200: {
                "model": FileMetadata,
                "description": "Successful conversion - returns metadata of the converted file"
            },
            400: {
                "model": ErrorResponse,
                "description": "Invalid input or conversion error (no converter found)"
            },
            404: {
                "model": ErrorResponse,
                "description": "File not found"
            }
        }
)
def create_conversion(
    conversion_request: ConversionRequest,
    file_db: FileDB = Depends(get_file_db),
    conversion_db: ConversionDB = Depends(get_conversion_db),
    conversion_relations_db: ConversionRelationsDB = Depends(get_conversion_relations_db),
    settings_db: SettingsDB = Depends(get_settings_db),
    default_qualities_db: DefaultQualitiesDB = Depends(get_default_qualities_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Create a new conversion for a previously uploaded file."""
    og_id = conversion_request.id
    output_format = sanitize_extension(conversion_request.output_format)
    og_metadata = file_db.get_file_metadata(og_id)

    # Ensure the original file was uploaded and exists in the database
    if og_metadata is None:
        raise HTTPException(status_code=404, detail=f"No file found with id {og_id}")
    # Verify the file belongs to the current user
    if og_metadata.get("user_id") != current_user["uuid"]:
        raise HTTPException(status_code=404, detail=f"No file found with id {og_id}")

    input_format = og_metadata['media_type']

    # Find the appropriate converter for this conversion
    converter_type = registry.get_converter_for_conversion(input_format, output_format)
    if converter_type is None:
        raise HTTPException(status_code=400, detail=f"No converter found for {input_format} to {output_format}")

    try:
        converted_metadata = run_conversion_job(
            source_metadata=og_metadata,
            output_format=output_format,
            quality=conversion_request.quality,
            converter_type=converter_type,
            user_id=current_user["uuid"],
            file_db=file_db,
            conversion_db=conversion_db,
            conversion_relations_db=conversion_relations_db,
            settings_db=settings_db,
            default_qualities_db=default_qualities_db,
        )
    except ConversionFailedError as exc:
        raise HTTPException(status_code=400, detail=f"Conversion failed: {exc}")

    return converted_metadata

@router.delete(
    "/all",
    summary="Delete all converted files and their relations to the original files",
    responses={
        200: {
            "model": FileDeleteResponse,
            "description": "Conversion history deleted successfully"
        }
    }
)
def delete_all_conversions(
    conversion_db: ConversionDB = Depends(get_conversion_db),
    conversion_relations_db: ConversionRelationsDB = Depends(get_conversion_relations_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Delete all converted files and their relations for the current user"""
    converted_files = conversion_db.list_files(user_id=current_user["uuid"])
    for file in converted_files:
        delete_file_and_metadata(file['id'], conversion_db)
        conversion_relations_db.delete_relation_by_converted(file['id'])
    return {"message": "All conversion history deleted successfully"}

@router.delete(
    "/{conversion_id}",
    summary="Delete a converted file and its relation to the original file",
    responses={
        200: {
            "model": FileDeleteResponse,
            "description": "Conversion history deleted successfully"
        },
        404: {
            "model": ErrorResponse,
            "description": "Conversion history not found"
        }
    }
)
def delete_conversion(
    conversion_id: str,
    conversion_db: ConversionDB = Depends(get_conversion_db),
    conversion_relations_db: ConversionRelationsDB = Depends(get_conversion_relations_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Delete a converted file and its relation"""
    # Verify the conversion belongs to the current user
    metadata = conversion_db.get_file_metadata(conversion_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Conversion not found")
    if metadata.get("user_id") != current_user["uuid"]:
        raise HTTPException(status_code=404, detail="Conversion not found")
    delete_file_and_metadata(conversion_id, conversion_db)
    conversion_relations_db.delete_relation_by_converted(conversion_id)
    return {"message": "Conversion history deleted successfully"}