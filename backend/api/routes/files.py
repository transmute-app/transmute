import os
import uuid
import hashlib
import mimetypes

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from zipfile import ZipFile
from pathlib import Path
from core import get_settings, detect_media_type, sanitize_extension, sanitize_filename, delete_file_and_metadata, validate_safe_path, get_file_extension
from db import FileDB, ConversionDB
from registry import registry as converter_registry
from api.deps import get_current_active_user, get_file_db, get_conversion_db
from api.schemas import FileListResponse, FileUploadResponse, FileDeleteResponse, ErrorResponse, BatchDownloadRequest

router = APIRouter(prefix="/files", tags=["files"])

# Define upload directory
settings = get_settings()
UPLOAD_DIR = settings.upload_dir
CONVERTED_DIR = settings.output_dir
TMP_DIR = settings.tmp_dir


def build_zip_entry_name(file_metadata: dict, is_converted_file: bool) -> str:
    """Build a safe ZIP entry name, preserving converted output extensions."""
    original_name = file_metadata.get("original_filename", "download")
    original_extension = get_file_extension(original_name)

    if not is_converted_file:
        return sanitize_filename(original_name)

    output_extension = sanitize_extension(
        file_metadata.get("extension") or get_file_extension(file_metadata.get("storage_path", ""))
    )
    base_name = original_name.removesuffix(f".{original_extension}") if original_extension else original_name
    converted_name = f"{base_name}.{output_extension}" if output_extension else base_name
    return sanitize_filename(converted_name)


async def save_file(file: UploadFile, db: FileDB, user_id: str) -> dict:
    """Save an uploaded file to disk and store its metadata in the database."""
    uuid_str = str(uuid.uuid4())
    original_filename = file.filename or "upload"
    file_extension = get_file_extension(original_filename)
    unique_filename = f"{uuid_str}"
    if file_extension:
        unique_filename += f".{file_extension}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file_path = Path(UPLOAD_DIR) / unique_filename
    hasher = hashlib.sha256()
    size_bytes = 0
    # Stream upload to disk and compute hash in one pass
    with file_path.open("wb") as buffer:
        while True:
            chunk = await file.read(1024 * 1024)  # Read in 1MB chunks
            if not chunk:
                break
            buffer.write(chunk)
            hasher.update(chunk)
            size_bytes += len(chunk)
    
    media_type = detect_media_type(file_path)

    metadata = {
        "id": uuid_str,
        "storage_path": str(file_path),
        "original_filename": original_filename,
        "media_type": media_type,
        "extension": file_extension,
        "size_bytes": size_bytes,
        "sha256_checksum": hasher.hexdigest(),
        "user_id": user_id,
    }
    db.insert_file_metadata(metadata)
    metadata["compatible_formats"] = converter_registry.get_compatible_formats(media_type)
    return metadata


@router.get(
    "",
    summary="List all uploaded files",
    responses={
        200: {
            "model": FileListResponse,
            "description": "List of all uploaded files"
        }
    }
)
def list_files(
    file_db: FileDB = Depends(get_file_db),
    current_user: dict = Depends(get_current_active_user),
):
    """List all uploaded files for the current user"""
    files = file_db.list_files(user_id=current_user["uuid"])
    for file in files:
        file["compatible_formats"] = converter_registry.get_compatible_formats(file["media_type"])
    return {"files": files}


@router.post(
    "",
    summary="Upload a file",
    responses={
        200: {
            "model": FileUploadResponse,
            "description": "File uploaded successfully"
        },
        500: {
            "model": ErrorResponse,
            "description": "Upload failed"
        }
    }
)
async def upload_file(
    file: UploadFile = File(...),
    file_db: FileDB = Depends(get_file_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Upload a file and save it to the server"""
    try:
        metadata = await save_file(file, file_db, current_user["uuid"])
        return {"message": "File uploaded successfully", "metadata": metadata}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        await file.close()

@router.get(
    "/{file_id}",
    summary="Download a converted file",
    response_class=FileResponse,
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "File content as binary"
        },
        404: {
            "model": ErrorResponse,
            "description": "File not found"
        }
    }
)
def get_file(
    file_id: str,
    file_db: FileDB = Depends(get_file_db),
    conv_db: ConversionDB = Depends(get_conversion_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Download a file"""
    # First check if file_id corresponds to an original uploaded file
    for db in [file_db, conv_db]:
        metadata = db.get_file_metadata(file_id)
        if metadata is not None:
            # Verify the file belongs to the current user
            if metadata.get("user_id") != current_user["uuid"]:
                raise HTTPException(status_code=404, detail="File not found")
            file_path = Path(metadata['storage_path'])
            # Validate path before serving
            validate_safe_path(file_path, raise_exception=True)
            # media_type in DB is an extension (e.g. "svg"), convert to MIME
            ext = metadata['media_type']
            mime_type = mimetypes.guess_type(f"file.{ext}")[0] or "application/octet-stream"
            return FileResponse(
                path=file_path,
                filename=build_zip_entry_name(metadata, db is conv_db),
                media_type=mime_type
            )
    raise HTTPException(status_code=404, detail="File not found")

@router.post(
        "/batch",
        summary="Batch download converted files",
        response_class=FileResponse,
        responses={
            200: {
                "content": {"application/zip": {}},
                "description": "ZIP file containing all converted files"
            },
            404: {
                "model": ErrorResponse,
                "description": "One or more converted files not found"
            }
        }
)
def batch_download_files(
    request: BatchDownloadRequest,
    background_tasks: BackgroundTasks,
    file_db: FileDB = Depends(get_file_db),
    conv_db: ConversionDB = Depends(get_conversion_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Batch download converted files as a ZIP archive"""
    # Create temporary ZIP file
    zip_id = str(uuid.uuid4())
    zip_path = TMP_DIR / f"{zip_id}.zip"
    
    seen_names: dict[str, int] = {}

    with ZipFile(zip_path, "w") as zip_file:
        for file_id in request.file_ids:
            found_file_in_db = False
            is_converted_file = False
            # Check both original and converted file databases for the file ID
            for db in [file_db, conv_db]:
                file_metadata = db.get_file_metadata(file_id)
                if file_metadata is not None:
                    # Verify the file belongs to the current user
                    if file_metadata.get("user_id") != current_user["uuid"]:
                        file_metadata = None
                        continue
                    found_file_in_db = True
                    is_converted_file = db is conv_db
                    break
            
            if not found_file_in_db:
                # Clean up temp file before raising error
                if zip_path.exists():
                    os.unlink(zip_path)
                raise HTTPException(status_code=404, detail=f"File with id {file_id} not found")
            
            file_path = Path(file_metadata['storage_path'])
            # Validate path before adding to ZIP
            validate_safe_path(file_path, raise_exception=True)
            
            if not file_path.exists():
                # Clean up temp file before raising error
                if zip_path.exists():
                    os.unlink(zip_path)
                raise HTTPException(status_code=404, detail=f"File with id {file_id} not found on disk")
            
            arcname = build_zip_entry_name(file_metadata, is_converted_file)
            # Deduplicate names when multiple files share the same original filename
            if arcname in seen_names:
                seen_names[arcname] += 1
                stem, _, ext = arcname.rpartition(".")
                if ext and stem:
                    arcname = f"{stem} ({seen_names[arcname]}).{ext}"
                else:
                    arcname = f"{arcname} ({seen_names[arcname]})"
            else:
                seen_names[arcname] = 0

            zip_file.write(file_path, arcname=arcname)
    
    # Schedule cleanup of temp ZIP file after response is sent
    background_tasks.add_task(os.unlink, zip_path)
    
    return FileResponse(
        path=zip_path,
        filename="transmute_batch_conversion.zip",
        media_type="application/zip"
    )

@router.delete(
    "/all",
    summary="Delete all uploaded files",
    responses={
        200: {
            "model": FileDeleteResponse,
            "description": "All files deleted successfully"
        }
    }
)
def delete_all_files(
    file_db: FileDB = Depends(get_file_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Delete all uploaded files for the current user"""
    uploaded_files = file_db.list_files(user_id=current_user["uuid"])
    for file in uploaded_files:
        delete_file_and_metadata(file['id'], file_db)
    return {"message": "All files deleted successfully"}

@router.delete(
    "/{file_id}",
    summary="Delete an uploaded file",
    responses={
        200: {
            "model": FileDeleteResponse,
            "description": "File deleted successfully"
        },
        404: {
            "model": ErrorResponse,
            "description": "File not found"
        }
    }
)
def delete_file(
    file_id: str,
    file_db: FileDB = Depends(get_file_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Delete an uploaded file"""
    # Verify the file belongs to the current user
    metadata = file_db.get_file_metadata(file_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="File not found")
    if metadata.get("user_id") != current_user["uuid"]:
        raise HTTPException(status_code=404, detail="File not found")
    delete_file_and_metadata(file_id, file_db)
    return {"message": "File deleted successfully"}