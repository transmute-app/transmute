"""Background worker that processes queued conversion jobs.

The worker runs in a daemon thread, claims one job at a time from
``ConversionJobDB`` using an atomic ``BEGIN IMMEDIATE`` transaction, executes
it via ``services.run_conversion_job``, and records the terminal status.

Design notes:
- Single-process, single-worker by default. Concurrency higher than 1 is
    configurable in settings but not exercised in v1.
- Errors during conversion always mark the job ``failed``; they never
    crash the worker thread.
- On startup, ``recover_running_jobs`` is called to move any jobs left in
    ``running`` state back to ``queued`` so the worker retries them from
    scratch after an interrupted process restart.
"""
from __future__ import annotations

import logging
import threading
import time

from core import get_settings
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
# How long the manager sleeps between checks when deciding whether to spawn
# more workers.
MANAGER_POLL_SECONDS = 0.5


def _is_worker_alive(worker_ref: dict) -> bool:
    return bool(worker_ref["thread"].is_alive())


def _request_worker_stop(worker_ref: dict) -> None:
    worker_ref["stop_event"].set()


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
    """Move stale ``running`` jobs back to ``queued`` on startup.

    A job in ``running`` state at process boot means the previous worker
    was interrupted before it could record a terminal status. The work is
    not resumable in place, so we reset those jobs to a fresh queued state
    and let the worker retry them from scratch. Returns the number of
    recovered jobs.
    """
    job_db = ConversionJobDB()
    affected = job_db.requeue_running_jobs()
    if affected:
        logger.warning("Re-queued %d stale running job(s) on startup", affected)
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


def conversion_worker_manager_task(
    stop_event: threading.Event | None = None,
    worker_concurrency: int | None = None,
) -> None:
    """Spawn conversion workers lazily up to the configured concurrency.

    The manager itself is the only thread started eagerly at app boot. It
    watches for queued jobs and starts additional daemon workers only when the
    queue depth requires them.
    """
    settings = get_settings()
    max_workers = max(1, worker_concurrency or settings.conversion_worker_concurrency)
    job_db = ConversionJobDB()
    workers: list[dict] = []

    logger.info("Conversion queue manager started (max workers=%d)", max_workers)
    while True:
        if stop_event is not None and stop_event.is_set():
            for worker in workers:
                _request_worker_stop(worker)
            return

        workers = [worker for worker in workers if _is_worker_alive(worker)]

        try:
            queued_jobs = job_db.count_jobs(status="queued")
        except Exception:
            logger.exception("Failed to inspect queue depth; backing off")
            queued_jobs = 0

        desired_workers = min(max_workers, queued_jobs)

        if len(workers) > desired_workers:
            excess_workers = len(workers) - desired_workers
            for worker in workers[-excess_workers:]:
                _request_worker_stop(worker)

        additional_workers = max(0, desired_workers - len(workers))
        for _ in range(additional_workers):
            worker_stop_event = threading.Event()
            worker = get_conversion_worker_thread(stop_event=worker_stop_event)
            worker.start()
            workers.append({"thread": worker, "stop_event": worker_stop_event})

        slept = 0.0
        while slept < MANAGER_POLL_SECONDS:
            if stop_event is not None and stop_event.is_set():
                for worker in workers:
                    _request_worker_stop(worker)
                return
            time.sleep(0.1)
            slept += 0.1


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


def get_conversion_worker_manager_thread(
    stop_event: threading.Event | None = None,
    worker_concurrency: int | None = None,
) -> threading.Thread:
    """Return a daemon thread targeting ``conversion_worker_manager_task``."""
    thread = threading.Thread(
        target=conversion_worker_manager_task,
        args=(stop_event, worker_concurrency),
        name="conversion-queue-manager",
        daemon=True,
    )
    return thread
