"""Background worker that processes queued conversion jobs.

The worker runs in a daemon thread, claims one job at a time from
``ConversionJobDB`` using an atomic ``BEGIN IMMEDIATE`` transaction, executes
it via ``services.run_conversion_job``, and records the terminal status.

Design notes:
- Single-process, single-worker by default. Concurrency higher than 1 is
  configurable in settings but not exercised in v1.
- Errors during conversion always mark the job ``failed``; they never
  crash the worker thread.
- On startup, ``recover_running_jobs`` is called to mark any jobs left in
  ``running`` state as ``failed`` (the previous process was interrupted
  mid-job and cannot resume it cleanly).
"""
from __future__ import annotations

import logging
import threading
import time

from db import (
    ConversionDB,
    ConversionJobDB,
    ConversionRelationsDB,
    DefaultQualitiesDB,
    FileDB,
    SettingsDB,
)
from registry import registry
from services import ConversionFailedError, run_conversion_job


logger = logging.getLogger(__name__)


# How long the worker sleeps between polls when the queue is empty.
IDLE_POLL_SECONDS = 2.0


def _process_job(
    job: dict,
    *,
    file_db: FileDB,
    conversion_db: ConversionDB,
    conversion_relations_db: ConversionRelationsDB,
    settings_db: SettingsDB,
    default_qualities_db: DefaultQualitiesDB,
    job_db: ConversionJobDB,
) -> None:
    """Run a single claimed job and record its outcome.

    The job has already been transitioned to ``running`` by
    ``claim_next_queued_job``; this function only writes a terminal status.
    """
    job_id = job["id"]
    user_id = job["user_id"]
    source_id = job["source_file_id"]
    output_format = job["output_format"]

    source_metadata = file_db.get_file_metadata(source_id)
    if source_metadata is None or source_metadata.get("user_id") != user_id:
        # Source disappeared (deleted, expired by cleanup, or never existed
        # for this user) between submit and execution. Fail the job.
        job_db.mark_failed(job_id, "Source file no longer exists")
        return

    input_format = source_metadata["media_type"]
    converter_type = registry.get_converter_for_conversion(input_format, output_format)
    if converter_type is None:
        job_db.mark_failed(
            job_id,
            f"No converter found for {input_format} to {output_format}",
        )
        return

    try:
        converted_metadata = run_conversion_job(
            source_metadata=source_metadata,
            output_format=output_format,
            quality=job.get("quality"),
            converter_type=converter_type,
            user_id=user_id,
            file_db=file_db,
            conversion_db=conversion_db,
            conversion_relations_db=conversion_relations_db,
            settings_db=settings_db,
            default_qualities_db=default_qualities_db,
        )
    except ConversionFailedError as exc:
        logger.warning("Job %s failed: %s", job_id, exc)
        job_db.mark_failed(job_id, str(exc))
        return
    except Exception as exc:  # noqa: BLE001 - defensive last-resort guard
        logger.exception("Unexpected error processing job %s", job_id)
        job_db.mark_failed(job_id, f"Internal error: {exc}")
        return

    job_db.mark_completed(job_id, output_file_id=converted_metadata["id"])
    logger.info(
        "Job %s completed: %s -> %s (output %s)",
        job_id, input_format, output_format, converted_metadata["id"],
    )


def recover_running_jobs() -> int:
    """Mark stale ``running`` jobs as ``failed`` on startup.

    A job in ``running`` state at process boot means the previous worker
    was interrupted before it could record a terminal status; the work is
    not resumable, so we move those jobs to ``failed`` with a clear
    message. Returns the number of recovered jobs.
    """
    job_db = ConversionJobDB()
    affected = job_db.fail_running_jobs(
        "Job interrupted by application restart"
    )
    if affected:
        logger.warning("Recovered %d stale running job(s) on startup", affected)
    return affected


def conversion_worker_task(stop_event: threading.Event | None = None) -> None:
    """Main worker loop. Claims and processes jobs until ``stop_event`` is set.

    Each thread gets its own DB handles because ``sqlite3`` connections
    are not safe to share across threads. The worker keeps these handles
    for its lifetime.
    """
    file_db = FileDB()
    conversion_db = ConversionDB()
    conversion_relations_db = ConversionRelationsDB()
    settings_db = SettingsDB()
    default_qualities_db = DefaultQualitiesDB()
    job_db = ConversionJobDB()

    logger.info("Conversion queue worker started")
    while True:
        if stop_event is not None and stop_event.is_set():
            break

        try:
            job = job_db.claim_next_queued_job()
        except Exception:
            logger.exception("Failed to claim next job; backing off")
            job = None

        if job is None:
            # Sleep in small chunks so a stop_event is observed promptly.
            slept = 0.0
            while slept < IDLE_POLL_SECONDS:
                if stop_event is not None and stop_event.is_set():
                    return
                time.sleep(0.1)
                slept += 0.1
            continue

        try:
            _process_job(
                job,
                file_db=file_db,
                conversion_db=conversion_db,
                conversion_relations_db=conversion_relations_db,
                settings_db=settings_db,
                default_qualities_db=default_qualities_db,
                job_db=job_db,
            )
        except Exception:
            logger.exception("Worker loop caught unexpected error for job %s", job.get("id"))
            try:
                job_db.mark_failed(job["id"], "Internal worker error")
            except Exception:
                logger.exception("Also failed to mark job %s as failed", job.get("id"))


def get_conversion_worker_thread(stop_event: threading.Event | None = None) -> threading.Thread:
    """Return a daemon thread targeting ``conversion_worker_task``.

    The caller is responsible for starting the thread. The thread is a
    daemon so the application can exit cleanly even if the worker is
    blocked waiting on a long-running converter.
    """
    thread = threading.Thread(
        target=conversion_worker_task,
        args=(stop_event,),
        name="conversion-queue-worker",
        daemon=True,
    )
    return thread
