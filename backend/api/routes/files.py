import os
import uuid
import hashlib

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from zipfile import ZipFile
from pathlib import Path
from core import get_settings, detect_media_type, sanitize_extension, delete_file_and_metadata, validate_safe_path
from db import FileDB, ConversionDB, ConversionRelationsDB
from registry import registry as converter_registry
from api.deps import get_file_db, get_conversion_db, get_conversion_relations_db
from api.schemas import FileListResponse, FileUploadResponse, FileDeleteResponse, ErrorResponse, BatchDownloadRequest

router = APIRouter(prefix="/files", tags=["files"])

# Define upload directory
settings = get_settings()
UPLOAD_DIR = settings.upload_dir
CONVERTED_DIR = settings.output_dir
TMP_DIR = settings.tmp_dir


async def save_file(file: UploadFile, db: FileDB) -> dict:
    """Save an uploaded file to disk and store its metadata in the database."""
    uuid_str = str(uuid.uuid4())
    original_filename = file.filename or "upload"
    file_extension = sanitize_extension(Path(original_filename).suffix.lower())
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
def list_files(file_db: FileDB = Depends(get_file_db)):
    """List all uploaded files"""
    files = file_db.list_files()
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
    file_db: FileDB = Depends(get_file_db)
):
    """Upload a file and save it to the server"""
    try:
        metadata = await save_file(file, file_db)
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
def get_file(file_id: str, file_db: FileDB = Depends(get_file_db), conv_db: ConversionDB = Depends(get_conversion_db)):
    """Download a file"""
    # First check if file_id corresponds to an original uploaded file
    for db in [file_db, conv_db]:
        metadata = db.get_file_metadata(file_id)
        if metadata is not None:
            file_path = Path(metadata['storage_path'])
            # Validate path before serving
            validate_safe_path(file_path, raise_exception=True)
            return FileResponse(
                path=file_path,
                filename=metadata['original_filename'],
                media_type=metadata['media_type']
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
    conv_db: ConversionDB = Depends(get_conversion_db)
):
    """Batch download converted files as a ZIP archive"""
    # Create temporary ZIP file
    zip_id = str(uuid.uuid4())
    zip_path = TMP_DIR / f"{zip_id}.zip"
    
    with ZipFile(zip_path, "w") as zip_file:
        for file_id in request.file_ids:
            found_file_in_db = False
            # Check both original and converted file databases for the file ID
            for db in [file_db, conv_db]:
                file_metadata = db.get_file_metadata(file_id)
                if file_metadata is not None:
                    found_file_in_db = True
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
            
            zip_file.write(file_path, arcname=file_path.name)
    
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
    file_db: FileDB = Depends(get_file_db)
):
    """Delete all uploaded files"""
    # Find all uploaded file IDs
    uploaded_files = file_db.list_files()
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
    file_db: FileDB = Depends(get_file_db)
):
    """Delete an uploaded file"""
    # Find converted file ID related to this original file ID, if it exists
    delete_file_and_metadata(file_id, file_db)
    return {"message": "File deleted successfully"}