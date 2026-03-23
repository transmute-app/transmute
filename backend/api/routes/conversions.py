from pathlib import Path
import uuid
from fastapi import APIRouter, Depends, HTTPException
from converters import ConverterInterface
from registry import registry
from core import get_settings, sanitize_extension, delete_file_and_metadata, validate_safe_path, compute_sha256_checksum, media_type_extensions
from db import ConversionDB, FileDB, ConversionRelationsDB, SettingsDB
from api.deps import get_current_active_user, get_file_db, get_conversion_db, get_conversion_relations_db, get_settings_db
from api.schemas import ConversionRequest, ConversionListResponse, FileMetadata, ErrorResponse, FileDeleteResponse


router = APIRouter(prefix="/conversions", tags=["conversions"])
settings = get_settings()
UPLOAD_DIR = settings.upload_dir
TEMP_DIR = settings.tmp_dir
CONVERTED_DIR = settings.output_dir


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
    current_user: dict = Depends(get_current_active_user),
):
    """Create a new conversion for a previously uploaded file."""
    og_id = conversion_request.id
    output_format = sanitize_extension(conversion_request.output_format)
    output_extension = f".{media_type_extensions.get(output_format, output_format)}"
    og_metadata = file_db.get_file_metadata(og_id)

    # Ensure the original file was uploaded and exists in the database
    if og_metadata is None:
        raise HTTPException(status_code=404, detail=f"No file found with id {og_id}")
    # Verify the file belongs to the current user
    if og_metadata.get("user_id") != current_user["uuid"]:
        raise HTTPException(status_code=404, detail=f"No file found with id {og_id}")
    
    # Validate the original file's storage path
    validate_safe_path(og_metadata['storage_path'], raise_exception=True)
    
    input_format = og_metadata['media_type']
    converted_id = str(uuid.uuid4())
    converted_metadata = dict(og_metadata)
    
    # Find the appropriate converter for this conversion
    converter_type = registry.get_converter_for_conversion(input_format, output_format)
    if converter_type is None:
        raise HTTPException(status_code=400, detail=f"No converter found for {input_format} to {output_format}")

    # Perform the conversion using the converter interface
    converter: ConverterInterface = converter_type(og_metadata['storage_path'], f'{TEMP_DIR}/', input_format, output_format)
    try:
        output_files = converter.convert()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Conversion failed: {str(e)}")
    moved_output_file = Path(output_files[0]).rename(f'{CONVERTED_DIR}/{converted_id}{output_extension}')

    # Store the converted file metadata in the conversion database and create a relation to the original file
    converted_metadata['id'] = converted_id
    converted_metadata['media_type'] = f"{output_format}"
    converted_metadata['extension'] = output_extension
    converted_metadata['storage_path'] = str(moved_output_file)
    converted_metadata['size_bytes'] = moved_output_file.stat().st_size
    converted_metadata['sha256_checksum'] = compute_sha256_checksum(moved_output_file)
    converted_metadata['user_id'] = current_user["uuid"]
    converted_metadata.pop('created_at', None)  # Remove created_at from original metadata if it exists
    conversion_db.insert_file_metadata(converted_metadata)
    # Store relation with denormalized original file metadata
    conversion_relations_db.insert_conversion_relation({
        'original_file_id': og_id,
        'converted_file_id': converted_id,
        'original_filename': og_metadata['original_filename'],
        'original_media_type': og_metadata['media_type'],
        'original_extension': og_metadata['extension'],
        'original_size_bytes': og_metadata['size_bytes'],
        'user_id': current_user["uuid"],
    })
    if settings_db.get_settings(current_user["uuid"]).get("keep_originals", True) is False:
        delete_file_and_metadata(file_id=og_id, file_db=file_db)
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