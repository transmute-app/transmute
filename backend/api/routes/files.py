import os
import uuid
import shutil
import hashlib
import mimetypes
import logging

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import FileResponse
from zipfile import ZipFile
from pathlib import Path
from core import get_settings, detect_media_type, sanitize_extension, sanitize_filename, delete_file_and_metadata, validate_safe_path, get_file_extension
from db import FileDB, ConversionDB, CompressionDB
from registry import registry as converter_registry
from api.deps import get_current_active_user, get_file_db, get_conversion_db, get_compression_db
from api.schemas import (
    FileListResponse, FileUploadResponse, FileUrlUploadResponse, FileDeleteResponse,
    ErrorResponse, BatchDownloadRequest, UrlUploadRequest,
    ChunkedUploadInitRequest, ChunkedUploadInitResponse, ChunkedUploadChunkResponse,
    ChunkedUploadCompleteRequest, UploadConfigResponse,
)
from registry import downloader_registry
from downloaders import DownloadError, YtDlpDownloader
from converters.ffmpeg_convert import FFmpegConverter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

UNSUPPORTED_UPLOAD_DETAIL = "File has no supported conversions for the detected media type"

# Define upload directory
settings = get_settings()
UPLOAD_DIR = settings.upload_dir
CONVERTED_DIR = settings.output_dir
TMP_DIR = settings.tmp_dir
CHUNKS_DIR = settings.chunks_dir


def resolve_downloaded_media_type(downloader: object, detected_media_type: str) -> str:
    """Map downloader-specific sources to the stored input media type.

    yt-dlp can produce either a video or an audio-only file (e.g. YouTube
    Music, SoundCloud, Bandcamp). We alias to ``webvideo`` or ``webaudio``
    accordingly so the converter registry offers only the conversions that
    are actually valid for the media the user ended up with.
    """
    if isinstance(downloader, YtDlpDownloader):
        if detected_media_type in FFmpegConverter.audio_formats:
            return "webaudio"
        return "webvideo"
    return detected_media_type


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

    compatible_formats = converter_registry.get_compatible_formats_and_qualities(media_type)
    if not compatible_formats:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=UNSUPPORTED_UPLOAD_DETAIL)

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
    metadata["compatible_formats"] = compatible_formats
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
        file["compatible_formats"] = converter_registry.get_compatible_formats_and_qualities(file["media_type"])
    return {"files": files}


@router.post(
    "",
    summary="Upload a file",
    responses={
        200: {
            "model": FileUploadResponse,
            "description": "File uploaded successfully"
        },
        422: {
            "model": ErrorResponse,
            "description": "File has no supported conversions"
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        await file.close()


async def save_files_from_url(url: str, db: FileDB, user_id: str) -> list[dict]:
    """Download one or more files from a URL and store them like regular uploads.

    A URL may resolve to multiple files (e.g. a yt-dlp playlist); each is
    persisted separately and returned as its own metadata dict.
    """
    uuid_str = str(uuid.uuid4())
    downloader = downloader_registry.get_downloader_for_url(url)

    try:
        results = await downloader.download(url, Path(UPLOAD_DIR), uuid_str)
    except DownloadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    metadatas: list[dict] = []
    for result in results:
        file_extension = get_file_extension(result.original_filename)
        media_type = resolve_downloaded_media_type(downloader, detect_media_type(result.file_path))

        compatible_formats = converter_registry.get_compatible_formats_and_qualities(media_type)
        if not compatible_formats:
            result.file_path.unlink(missing_ok=True)
            continue

        metadata = {
            "id": result.id,
            "storage_path": str(result.file_path),
            "original_filename": result.original_filename,
            "media_type": media_type,
            "extension": file_extension,
            "size_bytes": result.size_bytes,
            "sha256_checksum": result.sha256_checksum,
            "user_id": user_id,
        }
        db.insert_file_metadata(metadata)
        metadata["compatible_formats"] = compatible_formats
        metadatas.append(metadata)

    if not metadatas:
        raise HTTPException(status_code=422, detail=UNSUPPORTED_UPLOAD_DETAIL)

    return metadatas


@router.post(
    "/url",
    summary="Upload one or more files from a URL",
    responses={
        200: {
            "model": FileUrlUploadResponse,
            "description": "File(s) downloaded and uploaded successfully",
        },
        422: {
            "model": ErrorResponse,
            "description": "URL download failed or file has no supported conversions",
        },
        500: {
            "model": ErrorResponse,
            "description": "Upload failed",
        },
    },
)
async def upload_file_from_url(
    request: UrlUploadRequest,
    file_db: FileDB = Depends(get_file_db),
    current_user: dict = Depends(get_current_active_user),
):
    try:
        metadatas = await save_files_from_url(request.url, file_db, current_user["uuid"])
        message = (
            "File uploaded successfully"
            if len(metadatas) == 1
            else f"{len(metadatas)} files uploaded successfully"
        )
        return {"message": message, "files": metadatas}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.api_route(
    "/{file_id}",
    methods=["GET", "HEAD"],
    summary="Download a file (either converted or original) based on file ID",
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
    comp_db: CompressionDB = Depends(get_compression_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Download a file"""
    # First check if file_id corresponds to an original uploaded file
    for db in [file_db, conv_db, comp_db]:
        metadata = db.get_file_metadata(file_id)
        if metadata is not None:
            # Verify the file belongs to the current user
            if metadata.get("user_id") != current_user["uuid"]:
                raise HTTPException(status_code=404, detail="File not found")
            file_path = Path(metadata['storage_path'])
            # Validate path before serving
            validate_safe_path(file_path, raise_exception=True)
            # Use the stored extension when present so synthetic input types
            # like webvideo still download with the correct MIME type.
            ext = sanitize_extension(metadata.get('extension') or metadata['media_type'])
            mime_type = mimetypes.guess_type(f"file.{ext}")[0] or "application/octet-stream"
            return FileResponse(
                path=file_path,
                filename=build_zip_entry_name(metadata, db is not file_db),
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
    comp_db: CompressionDB = Depends(get_compression_db),
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
            # Check original, converted, and compressed file databases for the file ID
            for db in [file_db, conv_db, comp_db]:
                file_metadata = db.get_file_metadata(file_id)
                if file_metadata is not None:
                    # Verify the file belongs to the current user
                    if file_metadata.get("user_id") != current_user["uuid"]:
                        file_metadata = None
                        continue
                    found_file_in_db = True
                    is_converted_file = db is not file_db
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


@router.get(
    "/config/upload",
    summary="Get upload configuration",
    responses={
        200: {
            "model": UploadConfigResponse,
            "description": "Upload configuration including maximum chunk size",
        }
    },
)
def get_upload_config():
    """Return upload-related configuration values."""
    return {"max_chunk_size": settings.max_chunk_size}


def _chunk_upload_dir(upload_id: str) -> Path:
    """Return the per-session directory for chunked upload chunks."""
    return CHUNKS_DIR / upload_id


@router.post(
    "/upload/init",
    summary="Initialize a chunked upload session",
    responses={
        200: {
            "model": ChunkedUploadInitResponse,
            "description": "Chunked upload session initialized",
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid parameters",
        },
    },
)
def init_chunked_upload(
    request: ChunkedUploadInitRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """Create a new chunked upload session and return an upload ID."""
    if request.total_size <= 0:
        raise HTTPException(status_code=400, detail="total_size must be positive")
    if request.total_chunks <= 0:
        raise HTTPException(status_code=400, detail="total_chunks must be positive")

    upload_id = str(uuid.uuid4())
    session_dir = _chunk_upload_dir(upload_id)
    os.makedirs(session_dir, exist_ok=True)

    meta_path = session_dir / "meta.json"
    import json
    with meta_path.open("w") as f:
        json.dump({
            "upload_id": upload_id,
            "filename": request.filename,
            "total_size": request.total_size,
            "total_chunks": request.total_chunks,
            "user_id": current_user["uuid"],
        }, f)

    return {"upload_id": upload_id}


@router.post(
    "/upload/chunk",
    summary="Upload a single chunk",
    responses={
        200: {
            "model": ChunkedUploadChunkResponse,
            "description": "Chunk received",
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid chunk index or body",
        },
        404: {
            "model": ErrorResponse,
            "description": "Upload session not found",
        },
    },
)
async def upload_chunk(
    request: Request,
    upload_id: str,
    chunk_index: int,
    current_user: dict = Depends(get_current_active_user),
):
    """Receive and store a single chunk for a chunked upload session."""
    session_dir = _chunk_upload_dir(upload_id)
    if not session_dir.is_dir():
        raise HTTPException(status_code=404, detail="Upload session not found")

    import json
    meta_path = session_dir / "meta.json"
    with meta_path.open("r") as f:
        meta = json.load(f)

    if meta.get("user_id") != current_user["uuid"]:
        raise HTTPException(status_code=404, detail="Upload session not found")

    if chunk_index < 0 or chunk_index >= meta["total_chunks"]:
        raise HTTPException(status_code=400, detail=f"chunk_index must be 0..{meta['total_chunks'] - 1}")

    chunk_path = session_dir / f"{chunk_index}.part"
    max_bytes = settings.max_chunk_size + 1024
    written = 0
    with chunk_path.open("wb") as buffer:
        async for chunk in request.stream():
            written += len(chunk)
            if written > max_bytes:
                chunk_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Chunk exceeds max_chunk_size")
            buffer.write(chunk)

    return {"upload_id": upload_id, "chunk_index": chunk_index}


@router.post(
    "/upload/complete",
    summary="Finalize a chunked upload",
    responses={
        200: {
            "model": FileUploadResponse,
            "description": "File assembled and uploaded successfully",
        },
        400: {
            "model": ErrorResponse,
            "description": "Missing chunks or invalid session",
        },
        404: {
            "model": ErrorResponse,
            "description": "Upload session not found",
        },
        422: {
            "model": ErrorResponse,
            "description": "File has no supported conversions",
        },
        500: {
            "model": ErrorResponse,
            "description": "Upload finalization failed",
        },
    },
)
def complete_chunked_upload(
    request: ChunkedUploadCompleteRequest,
    file_db: FileDB = Depends(get_file_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Assemble all chunks into the final file, validate, and store metadata."""
    import json

    session_dir = _chunk_upload_dir(request.upload_id)
    if not session_dir.is_dir():
        raise HTTPException(status_code=404, detail="Upload session not found")

    meta_path = session_dir / "meta.json"
    try:
        with meta_path.open("r") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid session metadata")

    if meta.get("user_id") != current_user["uuid"]:
        raise HTTPException(status_code=404, detail="Upload session not found")

    total_chunks = meta["total_chunks"]
    original_filename = meta["filename"]

    for i in range(total_chunks):
        if not (session_dir / f"{i}.part").exists():
            raise HTTPException(status_code=400, detail=f"Missing chunk {i}")

    file_path = None
    try:
        uuid_str = str(uuid.uuid4())
        file_extension = get_file_extension(original_filename)
        unique_filename = f"{uuid_str}"
        if file_extension:
            unique_filename += f".{file_extension}"
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        file_path = Path(UPLOAD_DIR) / unique_filename
        hasher = hashlib.sha256()
        size_bytes = 0

        with file_path.open("wb") as out:
            for i in range(total_chunks):
                chunk_path = session_dir / f"{i}.part"
                with chunk_path.open("rb") as cf:
                    while True:
                        data = cf.read(1024 * 1024)
                        if not data:
                            break
                        out.write(data)
                        hasher.update(data)
                        size_bytes += len(data)

        shutil.rmtree(session_dir, ignore_errors=True)

        media_type = detect_media_type(file_path)
        compatible_formats = converter_registry.get_compatible_formats_and_qualities(media_type)
        if not compatible_formats:
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=UNSUPPORTED_UPLOAD_DETAIL)

        metadata = {
            "id": uuid_str,
            "storage_path": str(file_path),
            "original_filename": original_filename,
            "media_type": media_type,
            "extension": file_extension,
            "size_bytes": size_bytes,
            "sha256_checksum": hasher.hexdigest(),
            "user_id": current_user["uuid"],
        }
        file_db.insert_file_metadata(metadata)
        metadata["compatible_formats"] = compatible_formats
        return {"message": "File uploaded successfully", "metadata": metadata}
    except HTTPException:
        raise
    except Exception as e:
        if file_path is not None:
            file_path.unlink(missing_ok=True)
        shutil.rmtree(session_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Upload finalization failed: {str(e)}")