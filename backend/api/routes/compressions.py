from fastapi import APIRouter, Depends, HTTPException
from registry import compressor_registry
from core import get_settings, delete_file_and_metadata
from db import CompressionDB, FileDB, CompressionRelationsDB, SettingsDB, DefaultCompressionLevelsDB
from services import CompressionFailedError, run_compression_job
from api.deps import (
    get_current_active_user,
    get_file_db,
    get_compression_db,
    get_compression_relations_db,
    get_settings_db,
    get_default_compression_levels_db,
)
from api.schemas import CompressionRequest, CompressionListResponse, FileMetadata, ErrorResponse, FileDeleteResponse


router = APIRouter(prefix="/compressions", tags=["compressions"])
settings = get_settings()
UPLOAD_DIR = settings.upload_dir
TEMP_DIR = settings.tmp_dir
COMPRESSED_DIR = settings.output_dir


@router.get(
        "/complete",
        summary="List completed compressions",
        responses={
            200: {
                "model": CompressionListResponse,
                "description": "List of completed compressions with original and compressed file metadata"
            }
        }
)
def list_compressions(
    comp_db: CompressionDB = Depends(get_compression_db),
    comp_rel_db: CompressionRelationsDB = Depends(get_compression_relations_db),
    current_user: dict = Depends(get_current_active_user),
):
    """List all completed compressions for the current user."""
    compressed_files = comp_db.list_files(user_id=current_user["uuid"])
    compressed_files_dict = {f['id']: f for f in compressed_files}

    relations = comp_rel_db.list_relations(user_id=current_user["uuid"])
    # For each relation, create a compression-centric record with original file metadata from the relation.
    # This uses denormalized data so original files can be deleted without breaking history.
    compression_records = []
    for rel in relations:
        comp_id = rel['compressed_file_id']
        if comp_id in compressed_files_dict:
            record = dict(compressed_files_dict[comp_id])
            # Build original_file metadata from denormalized relation data
            record['original_file'] = {
                'id': rel['original_file_id'],
                'original_filename': rel['original_filename'],
                'media_type': rel['original_media_type'],
                'extension': rel['original_extension'],
                'size_bytes': rel['original_size_bytes']
            }
            compression_records.append(record)

    return {"compressions": compression_records}


@router.post(
        "",
        summary="Create a new compression",
        responses={
            200: {
                "model": FileMetadata,
                "description": "Successful compression - returns metadata of the compressed file"
            },
            400: {
                "model": ErrorResponse,
                "description": "Invalid input or compression error (no compressor found)"
            },
            404: {
                "model": ErrorResponse,
                "description": "File not found"
            }
        }
)
def create_compression(
    compression_request: CompressionRequest,
    file_db: FileDB = Depends(get_file_db),
    compression_db: CompressionDB = Depends(get_compression_db),
    compression_relations_db: CompressionRelationsDB = Depends(get_compression_relations_db),
    settings_db: SettingsDB = Depends(get_settings_db),
    default_compression_levels_db: DefaultCompressionLevelsDB = Depends(get_default_compression_levels_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Create a new compression for a previously uploaded file."""
    og_id = compression_request.id
    og_metadata = file_db.get_file_metadata(og_id)

    # Ensure the original file was uploaded and exists in the database
    if og_metadata is None:
        raise HTTPException(status_code=404, detail=f"No file found with id {og_id}")
    # Verify the file belongs to the current user
    if og_metadata.get("user_id") != current_user["uuid"]:
        raise HTTPException(status_code=404, detail=f"No file found with id {og_id}")

    media_format = og_metadata['media_type']

    # Find the appropriate compressor for this media format
    compressor_type = compressor_registry.get_compressor_for_format(media_format)
    if compressor_type is None:
        raise HTTPException(status_code=400, detail=f"No compressor found for {media_format}")

    try:
        compressed_metadata = run_compression_job(
            source_metadata=og_metadata,
            compression_level=compression_request.compression_level,
            compressor_type=compressor_type,
            user_id=current_user["uuid"],
            file_db=file_db,
            compression_db=compression_db,
            compression_relations_db=compression_relations_db,
            settings_db=settings_db,
            default_compression_levels_db=default_compression_levels_db,
        )
    except CompressionFailedError as exc:
        raise HTTPException(status_code=400, detail=f"Compression failed: {exc}")

    return compressed_metadata


@router.delete(
    "/all",
    summary="Delete all compressed files and their relations to the original files",
    responses={
        200: {
            "model": FileDeleteResponse,
            "description": "Compression history deleted successfully"
        }
    }
)
def delete_all_compressions(
    compression_db: CompressionDB = Depends(get_compression_db),
    compression_relations_db: CompressionRelationsDB = Depends(get_compression_relations_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Delete all compressed files and their relations for the current user"""
    compressed_files = compression_db.list_files(user_id=current_user["uuid"])
    for file in compressed_files:
        delete_file_and_metadata(file['id'], compression_db)
        compression_relations_db.delete_relation_by_compressed(file['id'])
    return {"message": "All compression history deleted successfully"}


@router.delete(
    "/{compression_id}",
    summary="Delete a compressed file and its relation to the original file",
    responses={
        200: {
            "model": FileDeleteResponse,
            "description": "Compression history deleted successfully"
        },
        404: {
            "model": ErrorResponse,
            "description": "Compression history not found"
        }
    }
)
def delete_compression(
    compression_id: str,
    compression_db: CompressionDB = Depends(get_compression_db),
    compression_relations_db: CompressionRelationsDB = Depends(get_compression_relations_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Delete a compressed file and its relation"""
    # Verify the compression belongs to the current user
    metadata = compression_db.get_file_metadata(compression_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Compression not found")
    if metadata.get("user_id") != current_user["uuid"]:
        raise HTTPException(status_code=404, detail="Compression not found")
    delete_file_and_metadata(compression_id, compression_db)
    compression_relations_db.delete_relation_by_compressed(compression_id)
    return {"message": "Compression history deleted successfully"}
