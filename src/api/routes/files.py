import os
import uuid
import hashlib

from fastapi import APIRouter, File, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path
from core import get_settings, detect_media_type
from db.file_db import FileDB

router = APIRouter(prefix="/files", tags=["files"])

# Define upload directory
settings = get_settings()
UPLOAD_DIR = settings.upload_dir
CONVERTED_DIR = settings.output_dir

async def save_file(file: UploadFile) -> dict:
    db = FileDB()
    uuid_str = str(uuid.uuid4())
    original_filename = file.filename or "upload"
    file_extension = Path(original_filename).suffix.lower()
    unique_filename = f"{uuid_str}{file_extension}"
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
    return metadata

@router.get("/")
def list_files():
    """List all uploaded files"""
    files = [f.name for f in UPLOAD_DIR.iterdir() if f.is_file()]
    return {"files": files}


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and save it to the server"""
    try:
        metadata = await save_file(file)
        return {"message": "File uploaded successfully", "metadata": metadata}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        await file.close()

@router.get("/{file_id}")
def get_file(file_id: str):
    """Download a converted file"""
    # Find file with matching ID
    for file_path in CONVERTED_DIR.iterdir():
        if file_path.stem == file_id:
            return FileResponse(
                path=file_path,
                filename=file_path.name,
                media_type="application/octet-stream"
            )
    raise HTTPException(status_code=404, detail="File not found")


@router.delete("/{file_id}")
def delete_file(file_id: str):
    """Delete an uploaded file"""
    # Find file with matching ID
    for file_path in UPLOAD_DIR.iterdir():
        if file_path.stem == file_id:
            file_path.unlink()
            return {"message": "File deleted successfully"}
    
    raise HTTPException(status_code=404, detail="File not found")
