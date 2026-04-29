import threading
from unittest.mock import MagicMock, patch

import pytest

from background.conversion_queue import (
    _process_job,
    conversion_worker_task,
    get_conversion_worker_thread,
    recover_running_jobs,
)
from services import ConversionFailedError


# ── _process_job ────────────────────────────────────────────────────

def _job(**overrides):
    base = {
        "id": "job-1",
        "user_id": "user-a",
        "source_file_id": "file-1",
        "output_format": "png",
        "quality": None,
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


@patch("background.conversion_queue.run_conversion_job")
@patch("background.conversion_queue.registry")
def test_process_job_marks_completed_on_success(mock_registry, mock_run):
    mock_registry.get_converter_for_conversion.return_value = MagicMock(__name__="FakeConverter")
    mock_run.return_value = {"id": "out-1"}

    file_db = MagicMock()
    file_db.get_file_metadata.return_value = _source()
    job_db = MagicMock()

    _process_job(
        _job(),
        file_db=file_db,
        conversion_db=MagicMock(),
        conversion_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_qualities_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_completed.assert_called_once_with("job-1", output_file_id="out-1")
    job_db.mark_failed.assert_not_called()


@patch("background.conversion_queue.registry")
def test_process_job_fails_when_source_missing(mock_registry):
    file_db = MagicMock()
    file_db.get_file_metadata.return_value = None
    job_db = MagicMock()

    _process_job(
        _job(),
        file_db=file_db,
        conversion_db=MagicMock(),
        conversion_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_qualities_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_failed.assert_called_once()
    args, _ = job_db.mark_failed.call_args
    assert args[0] == "job-1"
    assert "no longer exists" in args[1].lower()
    job_db.mark_completed.assert_not_called()
    mock_registry.get_converter_for_conversion.assert_not_called()


@patch("background.conversion_queue.registry")
def test_process_job_fails_when_source_belongs_to_different_user(mock_registry):
    file_db = MagicMock()
    file_db.get_file_metadata.return_value = _source(user_id="other-user")
    job_db = MagicMock()

    _process_job(
        _job(user_id="user-a"),
        file_db=file_db,
        conversion_db=MagicMock(),
        conversion_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_qualities_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_failed.assert_called_once()
    job_db.mark_completed.assert_not_called()
    mock_registry.get_converter_for_conversion.assert_not_called()


@patch("background.conversion_queue.registry")
def test_process_job_fails_when_no_converter_available(mock_registry):
    mock_registry.get_converter_for_conversion.return_value = None

    file_db = MagicMock()
    file_db.get_file_metadata.return_value = _source()
    job_db = MagicMock()

    _process_job(
        _job(output_format="exotic"),
        file_db=file_db,
        conversion_db=MagicMock(),
        conversion_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_qualities_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_failed.assert_called_once()
    args, _ = job_db.mark_failed.call_args
    assert "No converter found" in args[1]


@patch("background.conversion_queue.run_conversion_job", side_effect=ConversionFailedError("boom"))
@patch("background.conversion_queue.registry")
def test_process_job_marks_failed_on_conversion_error(mock_registry, mock_run):
    mock_registry.get_converter_for_conversion.return_value = MagicMock()
    file_db = MagicMock()
    file_db.get_file_metadata.return_value = _source()
    job_db = MagicMock()

    _process_job(
        _job(),
        file_db=file_db,
        conversion_db=MagicMock(),
        conversion_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_qualities_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_failed.assert_called_once_with("job-1", "boom")
    job_db.mark_completed.assert_not_called()


@patch("background.conversion_queue.run_conversion_job", side_effect=RuntimeError("unexpected"))
@patch("background.conversion_queue.registry")
def test_process_job_marks_failed_on_unexpected_error(mock_registry, mock_run):
    mock_registry.get_converter_for_conversion.return_value = MagicMock()
    file_db = MagicMock()
    file_db.get_file_metadata.return_value = _source()
    job_db = MagicMock()

    _process_job(
        _job(),
        file_db=file_db,
        conversion_db=MagicMock(),
        conversion_relations_db=MagicMock(),
        settings_db=MagicMock(),
        default_qualities_db=MagicMock(),
        job_db=job_db,
    )

    job_db.mark_failed.assert_called_once()
    args, _ = job_db.mark_failed.call_args
    assert "Internal error" in args[1]


# ── recover_running_jobs ────────────────────────────────────────────

@patch("background.conversion_queue.ConversionJobDB")
def test_recover_running_jobs_calls_fail_running(mock_cls):
    mock_cls.return_value.fail_running_jobs.return_value = 3

    affected = recover_running_jobs()

    assert affected == 3
    mock_cls.return_value.fail_running_jobs.assert_called_once()
    args, _ = mock_cls.return_value.fail_running_jobs.call_args
    assert "restart" in args[0].lower()


# ── conversion_worker_task ──────────────────────────────────────────

@patch("background.conversion_queue.DefaultQualitiesDB")
@patch("background.conversion_queue.SettingsDB")
@patch("background.conversion_queue.ConversionRelationsDB")
@patch("background.conversion_queue.ConversionDB")
@patch("background.conversion_queue.FileDB")
@patch("background.conversion_queue.ConversionJobDB")
@patch("background.conversion_queue._process_job")
def test_worker_loop_processes_then_stops(
    mock_process, mock_job_cls, mock_file_cls, mock_conv_cls,
    mock_conv_rel_cls, mock_settings_cls, mock_default_cls,
):
    """Worker claims a job, processes it, then exits when stop_event is set."""
    stop_event = threading.Event()
    mock_job_db = mock_job_cls.return_value

    job = {"id": "job-1"}

    def claim_side_effect():
        # First call returns a job, second call sets the stop event and
        # returns None so the loop exits during the idle sleep.
        if mock_job_db.claim_next_queued_job.call_count == 1:
            return job
        stop_event.set()
        return None

    mock_job_db.claim_next_queued_job.side_effect = claim_side_effect

    conversion_worker_task(stop_event=stop_event)

    mock_process.assert_called_once()
    args, kwargs = mock_process.call_args
    assert args[0] == job


@patch("background.conversion_queue.DefaultQualitiesDB")
@patch("background.conversion_queue.SettingsDB")
@patch("background.conversion_queue.ConversionRelationsDB")
@patch("background.conversion_queue.ConversionDB")
@patch("background.conversion_queue.FileDB")
@patch("background.conversion_queue.ConversionJobDB")
@patch("background.conversion_queue._process_job", side_effect=RuntimeError("loop blow-up"))
def test_worker_loop_recovers_when_process_raises(
    mock_process, mock_job_cls, mock_file_cls, mock_conv_cls,
    mock_conv_rel_cls, mock_settings_cls, mock_default_cls,
):
    """A crash inside _process_job should be caught and the job marked failed."""
    stop_event = threading.Event()
    mock_job_db = mock_job_cls.return_value

    def claim_side_effect():
        if mock_job_db.claim_next_queued_job.call_count == 1:
            return {"id": "job-x"}
        stop_event.set()
        return None

    mock_job_db.claim_next_queued_job.side_effect = claim_side_effect

    conversion_worker_task(stop_event=stop_event)

    mock_job_db.mark_failed.assert_called_once_with("job-x", "Internal worker error")


def test_get_conversion_worker_thread_is_daemon():
    thread = get_conversion_worker_thread(stop_event=threading.Event())
    assert isinstance(thread, threading.Thread)
    assert thread.daemon is True
    assert thread.name == "conversion-queue-worker"
