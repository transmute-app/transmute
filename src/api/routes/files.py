from fastapi import APIRouter, File, UploadFile, HTTPException, Request
from pathlib import Path
import shutil
from typing import Optional
import uuid

router = APIRouter(prefix="/files", tags=["files"])

# Define upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/")
def list_files():
    """List all uploaded files"""
    files = [f.name for f in UPLOAD_DIR.iterdir() if f.is_file()]
    return {"files": files}


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file for conversion"""

    # File metadata from multipart request
    file_name = file.filename
    file_mime_type = file.content_type
    
    try:
        # Generate unique filename to avoid conflicts
        file_id = str(uuid.uuid4())
        file_extension = Path(file_name).suffix
        unique_filename = f"{file_id}{file_extension}"
        file_path = UPLOAD_DIR / unique_filename
        
        # Save uploaded file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "message": "File uploaded successfully",
            "file_id": file_id,
            "filename": file_name,
            "content_type": file_mime_type,
            "stored_as": unique_filename,
            "size": file_path.stat().st_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        await file.close()


@router.delete("/{file_id}")
def delete_file(file_id: str):
    """Delete an uploaded file"""
    # Find file with matching ID
    for file_path in UPLOAD_DIR.iterdir():
        if file_path.stem == file_id:
            file_path.unlink()
            return {"message": "File deleted successfully"}
    
    raise HTTPException(status_code=404, detail="File not found")
