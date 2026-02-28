import os
import re
import mimetypes
import magic

from typing import TYPE_CHECKING
from fastapi import HTTPException
from pathlib import Path

if TYPE_CHECKING:
    from db import FileDB
    
from core.settings import get_settings


def validate_sql_identifier(identifier: str) -> str:
    """
    Validate and return a SQL identifier (table/column name) to prevent SQL injection.
    
    Args:
        identifier: The identifier to validate
        
    Returns:
        The validated identifier
        
    Raises:
        ValueError: If the identifier contains invalid characters
    """
    if not identifier:
        raise ValueError("SQL identifier cannot be empty")
    
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
        raise ValueError(
            f"Invalid SQL identifier '{identifier}'. "
            "Must start with a letter or underscore and contain only alphanumeric characters and underscores."
        )
    
    if len(identifier) > 64:
        raise ValueError(f"SQL identifier '{identifier}' is too long (max 64 characters)")
    
    return identifier


def detect_media_type(file_path: Path) -> str:
    """
    Detect the media type of a file based on its extension.

    Falls back to libmagic content-based detection when the file has no
    extension, then maps the resulting MIME type back to an extension string.

    Args:
        file_path: Path to the file whose media type should be detected

    Returns:
        A lowercase extension string without a leading dot (e.g. "png", "pdf")
    """
    # Use extensions as the media_type
    _, extension = os.path.splitext(file_path)
    if not extension:
        # If no extension, try to detect using magic
        media_type = magic.from_file(str(file_path), mime=True)
        extension = mimetypes.guess_extension(media_type) or ""
    media_type = extension.lstrip('.').lower()
    return media_type

def sanitize_extension(extension: str) -> str:
    """
    Sanitize a file extension string for safe storage and comparison.

    Strips surrounding whitespace and a leading dot, removes characters that
    are not alphanumeric, underscore, hyphen, or dot, and normalizes to
    lowercase.

    Args:
        extension: The raw extension string to sanitize (may include a
            leading dot)

    Returns:
        A cleaned, lowercase extension string without a leading dot
    """
    # Keep alphanumerics plus _, -, and ., normalize case.
    cleaned = extension.strip().lstrip(".")
    return "".join(ch for ch in cleaned if ch.isalnum() or ch in {"_", "-", "."}).lower()


def validate_hexadecimal_filename(filename: str) -> bool:
    """
    Validate that a filename (without extension) is hexadecimal.
    This is used to ensure files follow the UUID naming pattern.
    
    Args:
        filename: The filename to validate (can include extension)
        
    Returns:
        True if the filename stem is valid hexadecimal, False otherwise
    """
    # Get filename without extension
    path = Path(filename)
    stem = path.stem
    
    # Check if stem is non-empty and contains only hex characters
    if not stem:
        return False
    
    # Validate hexadecimal (UUIDs are hex with optional hyphens)
    # Allow both "abc123" and "abc-123-def" formats
    hex_pattern = re.compile(r'^[0-9a-fA-F-]+$')
    return bool(hex_pattern.match(stem))


def validate_safe_path(file_path: str | Path, raise_exception: bool = True) -> bool:
    """
    Validate that a file path is safe and within allowed directories.
    
    Security checks:
    - Resolves path to absolute canonical form
    - Ensures path is within allowed directories (data/uploads, data/tmp, data/outputs)
    - Validates filename is hexadecimal (UUID pattern)
    - Prevents path traversal attacks
    
    Args:
        file_path: The file path to validate
        raise_exception: If True, raise HTTPException on validation failure
        
    Returns:
        True if path is safe, False otherwise
        
    Raises:
        HTTPException: If raise_exception is True and validation fails
    """
    settings = get_settings()
    
    # Convert to Path object and resolve to absolute canonical path
    # This automatically handles .., symlinks, etc.
    try:
        absolute_path = Path(file_path).resolve(strict=False)
    except (ValueError, RuntimeError) as e:
        if raise_exception:
            raise HTTPException(status_code=400, detail=f"Invalid file path: {e}")
        return False
    
    # Define allowed directories
    allowed_dirs = [
        settings.upload_dir.resolve(),
        settings.tmp_dir.resolve(),
        settings.output_dir.resolve()
    ]
    
    # Check if path is within any allowed directory
    is_within_allowed = any(
        str(absolute_path).startswith(str(allowed_dir)) 
        for allowed_dir in allowed_dirs
    )
    
    if not is_within_allowed:
        if raise_exception:
            raise HTTPException(
                status_code=403, 
                detail="Access denied: File path is outside allowed directories"
            )
        return False
    
    # Validate filename is hexadecimal
    if not validate_hexadecimal_filename(absolute_path.name):
        if raise_exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid filename: Must be hexadecimal (UUID format) with optional extension"
            )
        return False
    
    return True


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent security issues like directory traversal.
    
    This implementation:
    - Removes all path separators (/, \\)
    - Strips control characters and null bytes
    - Removes leading/trailing dots and spaces
    - Prevents reserved Windows filenames
    - Uses a whitelist approach for allowed characters
    - Limits filename length
    """
    if not filename:
        return "unnamed"
    
    # Remove any path separators and null bytes
    cleaned = filename.replace("/", "").replace("\\", "").replace("\0", "")
    
    # Remove control characters (ASCII 0-31 and 127)
    cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32 and ord(ch) != 127)
    
    # Whitelist: only alphanumerics, underscore, hyphen, period, and space
    cleaned = "".join(ch for ch in cleaned if ch.isalnum() or ch in {"_", "-", ".", " "})
    
    # Strip leading/trailing dots, spaces, and whitespace
    cleaned = cleaned.strip(". ")
    
    # Check for Windows reserved names (case-insensitive)
    reserved_names = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
    }
    name_without_ext = cleaned.split(".")[0].upper()
    if name_without_ext in reserved_names:
        cleaned = f"_{cleaned}"
    
    # Limit length (255 is typical max for most filesystems, use 200 to be safe)
    if len(cleaned) > 200:
        # Try to preserve extension
        parts = cleaned.rsplit(".", 1)
        if len(parts) == 2:
            name, ext = parts
            max_name_len = 200 - len(ext) - 1
            cleaned = f"{name[:max_name_len]}.{ext}"
        else:
            cleaned = cleaned[:200]
    
    # If we ended up with nothing, use a default
    if not cleaned:
        return "unnamed"
    
    return cleaned

def delete_file_and_metadata(file_id: str, file_db: "FileDB", raise_if_not_found: bool = True):
    """
    Delete a file from disk and remove its metadata from the database.

    Looks up the file's metadata by ID, validates that the storage path is
    within an allowed directory, unlinks the file, and then deletes the
    metadata record.

    Args:
        file_id: Unique identifier of the file to delete
        file_db: Database instance used to look up and delete file metadata
        raise_if_not_found: If True, raise an HTTPException when the file ID
            does not exist; if False, return silently

    Raises:
        HTTPException: If the file is not found (when raise_if_not_found is
            True) or if the storage path fails validation
    """
    metadata = file_db.get_file_metadata(file_id)
    if metadata is None:
        if raise_if_not_found:
            raise HTTPException(status_code=404, detail="File not found")
        else:
            return
    
    # Validate the storage path before deleting
    storage_path = metadata['storage_path']
    validate_safe_path(storage_path, raise_exception=True)
    
    os.unlink(storage_path)
    file_db.delete_file_metadata(file_id)