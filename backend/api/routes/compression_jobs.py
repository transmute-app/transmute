"""Compression job queue endpoints.

These endpoints persist compression requests as durable jobs that a background
worker processes asynchronously, in contrast with the synchronous
``POST /api/compressions`` endpoint which runs the compression inline.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import (
    get_compression_job_db,
    get_current_active_user,
    get_file_db,
)
from api.schemas import (
    CompressionJobCreateRequest,
    CompressionJobListResponse,
    CompressionJobResponse,
    ErrorResponse,
)
from core import validate_safe_path
from db import CompressionJobDB, FileDB
from registry import compressor_registry


router = APIRouter(prefix="/compression-jobs", tags=["compression-jobs"])


def _serialize_job(job: dict) -> dict:
    """Convert a DB row into the API shape expected by ``CompressionJobResponse``."""
    serialized = {
        "id": job["id"],
        "user_id": job["user_id"],
        "source_file_id": job["source_file_id"],
        "compression_level": job.get("compression_level"),
        "status": job["status"],
        "progress": job.get("progress"),
        "error_message": job.get("error_message"),
        "output_file_id": job.get("output_file_id"),
        "compressor_name": job.get("compressor_name"),
        "source_filename": job.get("source_filename"),
        "source_media_type": job.get("source_media_type"),
        "source_extension": job.get("source_extension"),
        "source_size_bytes": job.get("source_size_bytes"),
    }
    for ts_field in ("created_at", "started_at", "completed_at", "updated_at"):
        value = job.get(ts_field)
        serialized[ts_field] = str(value) if value is not None else None
    return serialized


@router.get(
    "",
    summary="List compression jobs for the current user",
    responses={
        200: {
            "model": CompressionJobListResponse,
            "description": "List of compression jobs newest-first",
        }
    },
)
def list_jobs(
    status_filter: str | None = None,
    job_db: CompressionJobDB = Depends(get_compression_job_db),
    current_user: dict = Depends(get_current_active_user),
):
    """List the current user's compression jobs, newest-first.

    Optional ``status_filter`` query parameter narrows the result to one of:
    ``queued``, ``running``, ``completed``, ``failed``, ``cancelled``.
    """
    rows = job_db.list_jobs(user_id=current_user["uuid"], status=status_filter)
    return {"jobs": [_serialize_job(row) for row in rows]}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new compression job",
    responses={
        201: {"model": CompressionJobResponse, "description": "Job queued"},
        400: {"model": ErrorResponse, "description": "Unsupported compression"},
        404: {"model": ErrorResponse, "description": "Source file not found"},
    },
)
def create_job(
    request: CompressionJobCreateRequest,
    file_db: FileDB = Depends(get_file_db),
    job_db: CompressionJobDB = Depends(get_compression_job_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Validate the request and enqueue a new compression job."""
    source_id = request.id

    source = file_db.get_file_metadata(source_id)
    # Owner check returns 404 (not 403) so we don't leak existence of other
    # users' files - matches the pattern used elsewhere in the API.
    if source is None or source.get("user_id") != current_user["uuid"]:
        raise HTTPException(status_code=404, detail=f"No file found with id {source_id}")

    validate_safe_path(source["storage_path"], raise_exception=True)

    media_format = source["media_type"]
    compressor_type = compressor_registry.get_compressor_for_format(media_format)
    if compressor_type is None:
        raise HTTPException(
            status_code=400,
            detail=f"No compressor found for {media_format}",
        )

    job = job_db.insert_job({
        "user_id": current_user["uuid"],
        "source_file_id": source_id,
        "compression_level": request.compression_level,
        "compressor_name": compressor_type.__name__,
        "source_filename": source.get("original_filename"),
        "source_media_type": media_format,
        "source_extension": source.get("extension"),
        "source_size_bytes": source.get("size_bytes"),
    })
    return _serialize_job(job)


@router.get(
    "/{job_id}",
    summary="Get a single compression job",
    responses={
        200: {"model": CompressionJobResponse, "description": "The requested job"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
def get_job(
    job_id: str,
    job_db: CompressionJobDB = Depends(get_compression_job_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get one of the current user's jobs by ID."""
    job = job_db.get_job(job_id, user_id=current_user["uuid"])
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _serialize_job(job)


@router.post(
    "/{job_id}/cancel",
    summary="Cancel a queued compression job",
    responses={
        200: {"model": CompressionJobResponse, "description": "Job cancelled"},
        404: {"model": ErrorResponse, "description": "Job not found"},
        409: {"model": ErrorResponse, "description": "Job is no longer cancellable"},
    },
)
def cancel_job(
    job_id: str,
    job_db: CompressionJobDB = Depends(get_compression_job_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Cancel a job that has not yet started running.

    Only ``queued -> cancelled`` is supported in this version. Cancelling a
    running job is intentionally deferred; callers must wait for it to
    complete or fail.
    """
    job = job_db.get_job(job_id, user_id=current_user["uuid"])
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "queued":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel job with status '{job['status']}'",
        )
    if not job_db.cancel_queued_job(job_id, current_user["uuid"]):
        # The worker raced us and claimed the job between the read and the
        # write; report the same conflict the user would otherwise have seen.
        raise HTTPException(status_code=409, detail="Job is no longer cancellable")
    updated = job_db.get_job(job_id, user_id=current_user["uuid"])
    return _serialize_job(updated)


@router.post(
    "/{job_id}/retry",
    summary="Retry a failed or cancelled compression job",
    responses={
        200: {"model": CompressionJobResponse, "description": "Job re-queued"},
        404: {"model": ErrorResponse, "description": "Job or source file not found"},
        409: {"model": ErrorResponse, "description": "Job is not in a retryable state"},
    },
)
def retry_job(
    job_id: str,
    file_db: FileDB = Depends(get_file_db),
    job_db: CompressionJobDB = Depends(get_compression_job_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Re-queue a job that previously ended in ``failed`` or ``cancelled``.

    The source file must still exist and be owned by the caller — if the
    original was deleted (e.g. ``keep_originals=false``) the retry is rejected
    with a 404 so the user can re-upload before trying again.
    """
    job = job_db.get_job(job_id, user_id=current_user["uuid"])
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("failed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry job with status '{job['status']}'",
        )

    source = file_db.get_file_metadata(job["source_file_id"])
    if source is None or source.get("user_id") != current_user["uuid"]:
        raise HTTPException(
            status_code=404,
            detail="Source file no longer exists; re-upload before retrying",
        )

    if not job_db.retry_terminal_job(job_id, current_user["uuid"]):
        raise HTTPException(status_code=409, detail="Job is no longer retryable")
    updated = job_db.get_job(job_id, user_id=current_user["uuid"])
    return _serialize_job(updated)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a terminal compression job",
    responses={
        204: {"description": "Job deleted"},
        404: {"model": ErrorResponse, "description": "Job not found"},
        409: {"model": ErrorResponse, "description": "Job is still active"},
    },
)
def delete_job(
    job_id: str,
    job_db: CompressionJobDB = Depends(get_compression_job_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Delete a job that has reached a terminal state.

    Only ``failed`` and ``cancelled`` jobs may be removed via this endpoint.
    Completed jobs are represented in the compressions list and removed via
    ``DELETE /api/compressions/{id}``; queued/running jobs must be cancelled
    first.
    """
    job = job_db.get_job(job_id, user_id=current_user["uuid"])
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("failed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete job with status '{job['status']}'",
        )
    job_db.delete_job(job_id, user_id=current_user["uuid"])
    return None
