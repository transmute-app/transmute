from db import FileDB
from fastapi import UploadFile
from pathlib import Path
from core import get_settings
import os, uuid, hashlib, mimetypes
import magic

mimetypes.add_type("application/yaml", ".yaml")
mimetypes.add_type("application/yaml", ".yml")

class FileSave:
    STORAGE_DIR = get_settings().upload_dir
    CHUNK_SIZE = 1024 * 1024  # 1MB

    def __init__(self, file: UploadFile):
        self.db = FileDB()
        self.file = file
        self.uuid_str = str(uuid.uuid4())
        self.original_filename = file.filename or "upload"
        self.file_extension = Path(self.original_filename).suffix.lower()
        self.unique_filename = f"{self.uuid_str}{self.file_extension}"
        os.makedirs(self.STORAGE_DIR, exist_ok=True)

    def __detect_media_type(self, file_path: Path) -> str:
        media_type, _ = mimetypes.guess_type(self.original_filename)
        if media_type in (None, "application/octet-stream"):
            try:
                media_type = magic.from_file(str(file_path), mime=True) or "application/octet-stream"
            except Exception:
                media_type = "application/octet-stream"
        return media_type

    async def save_file(self) -> dict:
        file_path = Path(self.STORAGE_DIR) / self.unique_filename

        hasher = hashlib.sha256()
        size_bytes = 0

        # Stream upload to disk and compute hash in one pass
        with file_path.open("wb") as buffer:
            while True:
                chunk = await self.file.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                buffer.write(chunk)
                hasher.update(chunk)
                size_bytes += len(chunk)

        media_type = self.__detect_media_type(file_path)

        metadata = {
            "id": self.uuid_str,
            "storage_path": str(file_path),
            "original_filename": self.original_filename,
            "media_type": media_type,
            "extension": self.file_extension,
            "size_bytes": size_bytes,
            "sha256_checksum": hasher.hexdigest(),
        }
        self.db.insert_file_metadata(metadata)
        return metadata
