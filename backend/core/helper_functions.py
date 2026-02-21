import os
import mimetypes
from fastapi import HTTPException
import magic

from pathlib import Path

from db.file_db import FileDB


def detect_media_type(file_path: Path) -> str:
    # Use extensions as the media_type
    _, extension = os.path.splitext(file_path)
    if not extension:
        # If no extension, try to detect using magic
        media_type = magic.from_file(str(file_path), mime=True)
        extension = mimetypes.guess_extension(media_type) or ""
    media_type = extension.lstrip('.').lower()
    return media_type

def sanitize_extension(extension: str) -> str:
    # Keep alphanumerics plus _, -, and ., normalize case.
    cleaned = extension.strip().lstrip(".")
    return "".join(ch for ch in cleaned if ch.isalnum() or ch in {"_", "-", "."}).lower()

def delete_file_and_metadata(file_id: str, file_db: FileDB, raise_if_not_found: bool = True):
    """Helper function to delete a file and its metadata from a file database."""
    metadata = file_db.get_file_metadata(file_id)
    if metadata is None:
        if raise_if_not_found:
            raise HTTPException(status_code=404, detail="File not found")
        else:
            return
    os.unlink(metadata['storage_path'])
    file_db.delete_file_metadata(file_id)