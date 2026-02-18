from fastapi import APIRouter, File, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path
from file_handling import FileSave
from core import get_settings

router = APIRouter(prefix="/files", tags=["files"])

# Define upload directory
settings = get_settings()
UPLOAD_DIR = settings.upload_dir
CONVERTED_DIR = settings.output_dir

@router.get("/")
def list_files():
    """List all uploaded files"""
    files = [f.name for f in UPLOAD_DIR.iterdir() if f.is_file()]
    return {"files": files}


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and save it to the server"""
    file_save = FileSave(file)
    try:
        metadata = await file_save.save_file()
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
