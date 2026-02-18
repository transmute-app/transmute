from db import FileDB
from fastapi import UploadFile
from pathlib import Path
import os
import uuid
import hashlib
import mimetypes
import magic
import shutil

mimetypes.add_type('application/yaml', '.yaml')
mimetypes.add_type('application/yaml', '.yml')

class FileSave:
  STORAGE_DIR = "data/uploads"

  def __init__(self, file: UploadFile):
    self.db = FileDB()
    self.file = file
    self.uuid_str = str(uuid.uuid4())
    self.original_filename = file.filename
    self.file_extension = Path(self.original_filename).suffix
    self.unique_filename = f"{self.uuid_str}{self.file_extension}"
    os.makedirs(self.STORAGE_DIR, exist_ok=True)

  def __compute_metadata(self, file_path: Path) -> dict:
    """
    Computes metadata for a given file path.

    Args:
        file_path: Path to the file for which to compute metadata.
    Returns:
        metadata: dictionary containing file metadata.
    """
    file_size = file_path.stat().st_size
    sha256_checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
    
    # Determine filetype based on the extension first
    media_type, _ = mimetypes.guess_type(self.original_filename)

    # Fallback to using python-magic to detect media type based on file content 
    # if mimetypes fails to determine the media type
    undesirable_types = [None, "application/octet-stream"]
    if media_type in undesirable_types:
      # Use python-magic to detect media type based on file content
      media_type = magic.from_file(str(file_path), mime=True)
      if media_type is None:
        media_type = "application/octet-stream"
    
    metadata = {
      "id": self.uuid_str,
      "storage_path": str(file_path),
      "original_filename": self.original_filename,
      "media_type": media_type,
      "extension": self.file_extension,
      "size_bytes": file_size,
      "sha256_checksum": sha256_checksum,
      "stored_as": self.unique_filename
    }
    return metadata

  def save_file(self) -> dict:
    """
    Saves the uploaded file to disk, computes metadata, and stores metadata in the database. 

    Returns:
        metadata: metadata dictionary.
    """
    # Save uploaded file
    file_path = Path(self.STORAGE_DIR) / self.unique_filename
    with file_path.open("wb") as buffer:
      shutil.copyfileobj(self.file.file, buffer)
    
    # Compute & save file metadata
    metadata = self.__compute_metadata(file_path)
    self.db.insert_file_metadata(metadata)

    # Return metadata for response to user
    return metadata
