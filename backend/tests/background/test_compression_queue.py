import threading
from unittest.mock import MagicMock, patch

from background.compression_queue import (
    _process_compression_job,
    compression_worker_manager_task,
    compression_worker_task,
    get_compression_worker_manager_thread,
    get_compression_worker_thread,
    recover_compression_jobs,
)
from services import CompressionFailedError


# ── _process_compression_job ────────────────────────────────────────

def _job(**overrides):
    base = {
        "id": "job-1",
        "user_id": "user-a",
        "source_file_id": "file-1",
        "compression_level": None,
    }
    base.update(overrides)
    return base


def _source(**overrides):
    base = {
        "id": "file-1",
        "user_id": "user-a",
        "media_type": "jpg",
        "extension": ".jpg",
        "size_bytes": 100,
        "original_filename": "x.jpg",
        "storage_path": "data/uploads/file-1.jpg",
    }
    base.update(overrides)
    return base


@patch("background.compression_queue.run_compression_job")
@patch("background.compression_queue.compressor_registry")
def test_process_job_marks_completed_on_success(mock_registry, mock_run):
    mock_registry.get_compressor_for_format.return_value = MagicMock(__name__="FakeCompressor")
    mock_run.return_value = {"id": "out-1"}

    file_db = MagicMock()
    file_db.get_file_metadata.return_value = _source()
    job_db = MagicMock()

    _process_compression_job(
        _job(),
        file_db=file_db,
        compression_db=MagicMock(),
        compression_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_compression_levels_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_completed.assert_called_once_with("job-1", output_file_id="out-1")
    job_db.mark_failed.assert_not_called()


@patch("background.compression_queue.compressor_registry")
def test_process_job_fails_when_source_missing(mock_registry):
    file_db = MagicMock()
    file_db.get_file_metadata.return_value = None
    job_db = MagicMock()

    _process_compression_job(
        _job(),
        file_db=file_db,
        compression_db=MagicMock(),
        compression_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_compression_levels_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_failed.assert_called_once()
    args, _ = job_db.mark_failed.call_args
    assert args[0] == "job-1"
    assert "no longer exists" in args[1].lower()
    job_db.mark_completed.assert_not_called()
    mock_registry.get_compressor_for_format.assert_not_called()


@patch("background.compression_queue.compressor_registry")
def test_process_job_fails_when_source_belongs_to_different_user(mock_registry):
    file_db = MagicMock()
    file_db.get_file_metadata.return_value = _source(user_id="other-user")
    job_db = MagicMock()

    _process_compression_job(
        _job(user_id="user-a"),
        file_db=file_db,
        compression_db=MagicMock(),
        compression_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_compression_levels_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_failed.assert_called_once()
    job_db.mark_completed.assert_not_called()
    mock_registry.get_compressor_for_format.assert_not_called()


@patch("background.compression_queue.compressor_registry")
def test_process_job_fails_when_no_compressor_available(mock_registry):
    mock_registry.get_compressor_for_format.return_value = None

    file_db = MagicMock()
    file_db.get_file_metadata.return_value = _source(media_type="exotic")
    job_db = MagicMock()

    _process_compression_job(
        _job(),
        file_db=file_db,
        compression_db=MagicMock(),
        compression_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_compression_levels_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_failed.assert_called_once()
    args, _ = job_db.mark_failed.call_args
    assert "No compressor found" in args[1]


@patch("background.compression_queue.run_compression_job", side_effect=CompressionFailedError("boom"))
@patch("background.compression_queue.compressor_registry")
def test_process_job_marks_failed_on_compression_error(mock_registry, mock_run):
    mock_registry.get_compressor_for_format.return_value = MagicMock()
    file_db = MagicMock()
    file_db.get_file_metadata.return_value = _source()
    job_db = MagicMock()

    _process_compression_job(
        _job(),
        file_db=file_db,
        compression_db=MagicMock(),
        compression_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_compression_levels_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_failed.assert_called_once_with("job-1", "boom")
    job_db.mark_completed.assert_not_called()


@patch("background.compression_queue.run_compression_job", side_effect=RuntimeError("unexpected"))
@patch("background.compression_queue.compressor_registry")
def test_process_job_marks_failed_on_unexpected_error(mock_registry, mock_run):
    mock_registry.get_compressor_for_format.return_value = MagicMock()
    file_db = MagicMock()
    file_db.get_file_metadata.return_value = _source()
    job_db = MagicMock()

    _process_compression_job(
        _job(),
        file_db=file_db,
        compression_db=MagicMock(),
        compression_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_compression_levels_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_failed.assert_called_once()
    args, _ = job_db.mark_failed.call_args
    assert "Internal error" in args[1]


# ── recover_compression_jobs ────────────────────────────────────────

@patch("background.compression_queue.CompressionJobDB")
def test_recover_compression_jobs_calls_requeue_running(mock_cls):
    mock_cls.return_value.requeue_running_jobs.return_value = 3

    affected = recover_compression_jobs()

    assert affected == 3
    mock_cls.return_value.requeue_running_jobs.assert_called_once_with()


# ── compression_worker_task ─────────────────────────────────────────

@patch("background.compression_queue.DefaultCompressionLevelsDB")
@patch("background.compression_queue.SettingsDB")
@patch("background.compression_queue.CompressionRelationsDB")
@patch("background.compression_queue.CompressionDB")
@patch("background.compression_queue.FileDB")
@patch("background.compression_queue.CompressionJobDB")
@patch("background.compression_queue._process_compression_job")
def test_worker_loop_processes_then_stops(
    mock_process, mock_job_cls, mock_file_cls, mock_comp_cls,
    mock_comp_rel_cls, mock_settings_cls, mock_default_cls,
):
    """Worker claims a job, processes it, then exits when stop_event is set."""
    stop_event = threading.Event()
    mock_job_db = mock_job_cls.return_value

    job = {"id": "job-1"}

    def claim_side_effect():
        if mock_job_db.claim_next_queued_job.call_count == 1:
            return job
        stop_event.set()
        return None

    mock_job_db.claim_next_queued_job.side_effect = claim_side_effect

    compression_worker_task(stop_event=stop_event)

    mock_process.assert_called_once()
    args, kwargs = mock_process.call_args
    assert args[0] == job


@patch("background.compression_queue.DefaultCompressionLevelsDB")
@patch("background.compression_queue.SettingsDB")
@patch("background.compression_queue.CompressionRelationsDB")
@patch("background.compression_queue.CompressionDB")
@patch("background.compression_queue.FileDB")
@patch("background.compression_queue.CompressionJobDB")
@patch("background.compression_queue._process_compression_job", side_effect=RuntimeError("loop blow-up"))
def test_worker_loop_recovers_when_process_raises(
    mock_process, mock_job_cls, mock_file_cls, mock_comp_cls,
    mock_comp_rel_cls, mock_settings_cls, mock_default_cls,
):
    """A crash inside _process_compression_job should be caught and the job marked failed."""
    stop_event = threading.Event()
    mock_job_db = mock_job_cls.return_value

    def claim_side_effect():
        if mock_job_db.claim_next_queued_job.call_count == 1:
            return {"id": "job-x"}
        stop_event.set()
        return None

    mock_job_db.claim_next_queued_job.side_effect = claim_side_effect

    compression_worker_task(stop_event=stop_event)

    mock_job_db.mark_failed.assert_called_once_with("job-x", "Internal worker error")


@patch("background.compression_queue.get_compression_worker_thread")
@patch("background.compression_queue.CompressionJobDB")
@patch("background.compression_queue.get_settings")
def test_worker_manager_starts_workers_only_when_jobs_exist(
    mock_get_settings,
    mock_job_cls,
    mock_get_worker,
):
    stop_event = threading.Event()
    mock_get_settings.return_value = MagicMock(compression_worker_concurrency=3)
    mock_job_db = mock_job_cls.return_value

    def count_side_effect(status=None, user_id=None):
        if mock_job_db.count_jobs.call_count == 1:
            return 0
        stop_event.set()
        return 2

    mock_job_db.count_jobs.side_effect = count_side_effect

    worker_one = MagicMock()
    worker_one.is_alive.return_value = True
    worker_two = MagicMock()
    worker_two.is_alive.return_value = True
    mock_get_worker.side_effect = [worker_one, worker_two]

    compression_worker_manager_task(stop_event=stop_event)

    worker_one.start.assert_called_once_with()
    worker_two.start.assert_called_once_with()
    assert mock_get_worker.call_count == 2


@patch("background.compression_queue.get_compression_worker_thread")
@patch("background.compression_queue.CompressionJobDB")
@patch("background.compression_queue.get_settings")
def test_worker_manager_honors_concurrency_limit(
    mock_get_settings,
    mock_job_cls,
    mock_get_worker,
):
    stop_event = threading.Event()
    mock_get_settings.return_value = MagicMock(compression_worker_concurrency=2)
    mock_job_db = mock_job_cls.return_value

    def count_side_effect(status=None, user_id=None):
        stop_event.set()
        return 5

    mock_job_db.count_jobs.side_effect = count_side_effect

    workers = []
    for _ in range(3):
        worker = MagicMock()
        worker.is_alive.return_value = True
        workers.append(worker)
    mock_get_worker.side_effect = workers

    compression_worker_manager_task(stop_event=stop_event)

    assert mock_get_worker.call_count == 2


@patch("background.compression_queue.get_compression_worker_thread")
@patch("background.compression_queue.CompressionJobDB")
@patch("background.compression_queue.get_settings")
def test_worker_manager_shrinks_back_when_queue_drains(
    mock_get_settings,
    mock_job_cls,
    mock_get_worker,
):
    stop_event = threading.Event()
    mock_get_settings.return_value = MagicMock(compression_worker_concurrency=3)
    mock_job_db = mock_job_cls.return_value

    def count_side_effect(status=None, user_id=None):
        if mock_job_db.count_jobs.call_count == 1:
            return 2
        stop_event.set()
        return 0

    mock_job_db.count_jobs.side_effect = count_side_effect

    worker_one = MagicMock()
    worker_one.is_alive.return_value = True
    worker_two = MagicMock()
    worker_two.is_alive.return_value = True
    mock_get_worker.side_effect = [worker_one, worker_two]

    compression_worker_manager_task(stop_event=stop_event)

    worker_one.start.assert_called_once_with()
    worker_two.start.assert_called_once_with()
    stop_event_one = mock_get_worker.call_args_list[0].kwargs["stop_event"]
    stop_event_two = mock_get_worker.call_args_list[1].kwargs["stop_event"]
    assert stop_event_one.is_set() is True
    assert stop_event_two.is_set() is True


def test_get_compression_worker_manager_thread_is_daemon():
    thread = get_compression_worker_manager_thread(stop_event=threading.Event(), worker_concurrency=2)
    assert isinstance(thread, threading.Thread)
    assert thread.daemon is True
    assert thread.name == "compression-queue-manager"


def test_get_compression_worker_thread_is_daemon():
    thread = get_compression_worker_thread(stop_event=threading.Event())
    assert isinstance(thread, threading.Thread)
    assert thread.daemon is True
    assert thread.name == "compression-queue-worker"
