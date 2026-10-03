import os
import time
import uuid
import threading
import pytest
from unittest.mock import MagicMock, patch

from background.cleanup import (
    file_cleanup_logic,
    guest_cleanup_logic,
    chunk_cleanup_logic,
    job_cleanup_logic,
    file_cleanup_task,
    get_upload_cleanup_thread,
)


# ── helpers ──────────────────────────────────────────────────────────

def _make_file(file_id, created_minutes_ago):
    """Return a fake file-metadata dict with `created_at` in the past."""
    ts = time.gmtime(time.time() - created_minutes_ago * 60)
    return {
        "id": file_id,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S", ts),
    }


def _timestamp(minutes_ago):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - minutes_ago * 60))


def _make_job(job_id, status, created_minutes_ago, completed_minutes_ago=None):
    """Return a fake job row with timestamps in the past."""
    return {
        "id": job_id,
        "status": status,
        "created_at": _timestamp(created_minutes_ago),
        "completed_at": (
            _timestamp(completed_minutes_ago) if completed_minutes_ago is not None else None
        ),
    }


# ── file_cleanup_logic ──────────────────────────────────────────────

class TestFileCleanupLogic:

    @patch("background.cleanup.SettingsDB")
    @patch("background.cleanup.delete_file_and_metadata")
    def test_cleanup_disabled_does_nothing(self, mock_delete, mock_settings_cls):
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": False,
            "cleanup_ttl_minutes": 10,
        }
        file_db = MagicMock()
        file_cleanup_logic(file_db)
        file_db.list_files.assert_not_called()
        mock_delete.assert_not_called()

    @patch("background.cleanup.SettingsDB")
    @patch("background.cleanup.delete_file_and_metadata")
    def test_deletes_expired_files(self, mock_delete, mock_settings_cls):
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": True,
            "cleanup_ttl_minutes": 5,
        }
        file_db = MagicMock()
        old_file = _make_file("old-1", created_minutes_ago=10)
        new_file = _make_file("new-1", created_minutes_ago=1)
        file_db.list_files.return_value = [old_file, new_file]

        file_cleanup_logic(file_db)

        mock_delete.assert_called_once_with("old-1", file_db)

    @patch("background.cleanup.SettingsDB")
    @patch("background.cleanup.delete_file_and_metadata")
    def test_deletes_conversion_relations(self, mock_delete, mock_settings_cls):
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": True,
            "cleanup_ttl_minutes": 5,
        }
        file_db = MagicMock()
        conv_rel_db = MagicMock()
        old_file = _make_file("old-1", created_minutes_ago=10)
        file_db.list_files.return_value = [old_file]

        file_cleanup_logic(file_db, conversion_relations_db=conv_rel_db)

        conv_rel_db.delete_relation_by_converted.assert_called_once_with("old-1")

    @patch("background.cleanup.SettingsDB")
    @patch("background.cleanup.delete_file_and_metadata")
    def test_keeps_fresh_files(self, mock_delete, mock_settings_cls):
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": True,
            "cleanup_ttl_minutes": 60,
        }
        file_db = MagicMock()
        file_db.list_files.return_value = [_make_file("f1", created_minutes_ago=5)]

        file_cleanup_logic(file_db)

        mock_delete.assert_not_called()

    @patch("background.cleanup.SettingsDB")
    @patch("background.cleanup.delete_file_and_metadata")
    def test_skips_file_without_created_at(self, mock_delete, mock_settings_cls):
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": True,
            "cleanup_ttl_minutes": 1,
        }
        file_db = MagicMock()
        file_db.list_files.return_value = [{"id": "no-ts", "created_at": None}]

        file_cleanup_logic(file_db)

        mock_delete.assert_not_called()


# ── job_cleanup_logic ───────────────────────────────────────────────

class TestJobCleanupLogic:

    @patch("background.cleanup.SettingsDB")
    def test_cleanup_disabled_does_nothing(self, mock_settings_cls):
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": False,
            "cleanup_ttl_minutes": 10,
        }
        job_db = MagicMock()
        job_cleanup_logic(job_db)
        job_db.list_jobs.assert_not_called()
        job_db.delete_job.assert_not_called()

    @patch("background.cleanup.SettingsDB")
    def test_deletes_expired_failed_job(self, mock_settings_cls):
        """A failed job produces no output file, so only this can clear it."""
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": True,
            "cleanup_ttl_minutes": 5,
        }
        job_db = MagicMock()
        job_db.list_jobs.return_value = [
            _make_job("old-failed", "failed", 10, completed_minutes_ago=10),
            _make_job("fresh-failed", "failed", 1, completed_minutes_ago=1),
        ]

        job_cleanup_logic(job_db)

        job_db.delete_job.assert_called_once_with("old-failed")

    @patch("background.cleanup.SettingsDB")
    def test_deletes_expired_completed_and_cancelled_jobs(self, mock_settings_cls):
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": True,
            "cleanup_ttl_minutes": 5,
        }
        job_db = MagicMock()
        job_db.list_jobs.return_value = [
            _make_job("old-completed", "completed", 10, completed_minutes_ago=10),
            _make_job("old-cancelled", "cancelled", 10, completed_minutes_ago=10),
        ]

        job_cleanup_logic(job_db)

        deleted = {call.args[0] for call in job_db.delete_job.call_args_list}
        assert deleted == {"old-completed", "old-cancelled"}

    @patch("background.cleanup.SettingsDB")
    def test_keeps_unfinished_jobs_regardless_of_age(self, mock_settings_cls):
        """Queued and running jobs belong to the worker, never to cleanup."""
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": True,
            "cleanup_ttl_minutes": 5,
        }
        job_db = MagicMock()
        job_db.list_jobs.return_value = [
            _make_job("queued-1", "queued", 600),
            _make_job("running-1", "running", 600),
        ]

        job_cleanup_logic(job_db)

        job_db.delete_job.assert_not_called()

    @patch("background.cleanup.SettingsDB")
    def test_ages_terminal_job_from_completion_not_creation(self, mock_settings_cls):
        """A job that sat in the queue for hours still gets its full TTL."""
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": True,
            "cleanup_ttl_minutes": 5,
        }
        job_db = MagicMock()
        job_db.list_jobs.return_value = [
            _make_job("slow-queue", "failed", 600, completed_minutes_ago=1),
        ]

        job_cleanup_logic(job_db)

        job_db.delete_job.assert_not_called()

    @patch("background.cleanup.SettingsDB")
    def test_falls_back_to_created_at_without_completed_at(self, mock_settings_cls):
        """Older rows predate completed_at being written."""
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": True,
            "cleanup_ttl_minutes": 5,
        }
        job_db = MagicMock()
        job_db.list_jobs.return_value = [_make_job("legacy", "failed", 10)]

        job_cleanup_logic(job_db)

        job_db.delete_job.assert_called_once_with("legacy")

    @patch("background.cleanup.SettingsDB")
    def test_skips_job_without_timestamps(self, mock_settings_cls):
        mock_settings_cls.return_value.get_admin_cleanup_settings.return_value = {
            "cleanup_enabled": True,
            "cleanup_ttl_minutes": 5,
        }
        job_db = MagicMock()
        job_db.list_jobs.return_value = [
            {"id": "no-ts", "status": "failed", "created_at": None, "completed_at": None},
        ]

        job_cleanup_logic(job_db)

        job_db.delete_job.assert_not_called()


# ── guest_cleanup_logic ──────────────────────────────────────────────

class TestGuestCleanupLogic:

    @patch("background.cleanup.ApiKeyDB")
    @patch("background.cleanup.DefaultFormatsDB")
    @patch("background.cleanup.SettingsDB")
    @patch("background.cleanup.ConversionRelationsDB")
    @patch("background.cleanup.ConversionDB")
    @patch("background.cleanup.FileDB")
    @patch("background.cleanup.UserDB")
    @patch("background.cleanup.delete_file_and_metadata")
    def test_no_expired_guests_is_noop(
        self, mock_delete, mock_user_cls, mock_file_cls, mock_conv_cls,
        mock_conv_rel_cls, mock_settings_cls, mock_default_cls, mock_apikey_cls,
    ):
        mock_user_cls.return_value.list_expired_guests.return_value = []
        guest_cleanup_logic()
        mock_file_cls.assert_not_called()
        mock_delete.assert_not_called()

    @patch("background.cleanup.ApiKeyDB")
    @patch("background.cleanup.DefaultFormatsDB")
    @patch("background.cleanup.SettingsDB")
    @patch("background.cleanup.ConversionRelationsDB")
    @patch("background.cleanup.ConversionDB")
    @patch("background.cleanup.FileDB")
    @patch("background.cleanup.UserDB")
    @patch("background.cleanup.delete_file_and_metadata")
    def test_deletes_all_guest_data(
        self, mock_delete, mock_user_cls, mock_file_cls, mock_conv_cls,
        mock_conv_rel_cls, mock_settings_cls, mock_default_cls, mock_apikey_cls,
    ):
        guest = {"uuid": "guest-1"}
        mock_user_cls.return_value.list_expired_guests.return_value = [guest]

        mock_file_db = mock_file_cls.return_value
        mock_conv_db = mock_conv_cls.return_value
        mock_conv_rel_db = mock_conv_rel_cls.return_value
        mock_settings_db = mock_settings_cls.return_value
        mock_default_db = mock_default_cls.return_value
        mock_apikey_db = mock_apikey_cls.return_value

        mock_file_db.list_files.return_value = [{"id": "f1"}]
        mock_conv_db.list_files.return_value = [{"id": "c1"}]

        guest_cleanup_logic()

        # Files cleaned
        mock_delete.assert_any_call("f1", mock_file_db, raise_if_not_found=False)
        # Conversions cleaned
        mock_delete.assert_any_call("c1", mock_conv_db, raise_if_not_found=False)
        mock_conv_rel_db.delete_relation_by_converted.assert_called_once_with("c1")
        # Per-user records cleaned
        mock_apikey_db.delete_all_keys_for_user.assert_called_once_with("guest-1")
        mock_settings_db.delete_settings.assert_called_once_with("guest-1")
        mock_default_db.delete_all.assert_called_once_with("guest-1")
        mock_user_cls.return_value.delete_user.assert_called_once_with("guest-1")


# ── file_cleanup_task ────────────────────────────────────────────────

@patch("background.cleanup.time.sleep", side_effect=StopIteration)
@patch("background.cleanup.guest_cleanup_logic")
@patch("background.cleanup.job_cleanup_logic")
@patch("background.cleanup.file_cleanup_logic")
@patch("background.cleanup.CompressionJobDB")
@patch("background.cleanup.ConversionJobDB")
@patch("background.cleanup.ConversionRelationsDB")
@patch("background.cleanup.ConversionDB")
@patch("background.cleanup.FileDB")
def test_cleanup_task_runs_one_iteration(
    mock_file_cls, mock_conv_cls, mock_conv_rel_cls,
    mock_conv_job_cls, mock_comp_job_cls,
    mock_file_cleanup, mock_job_cleanup, mock_guest_cleanup, mock_sleep,
):
    with pytest.raises(StopIteration):
        file_cleanup_task()

    assert mock_file_cleanup.call_count == 2  # FileDB + ConversionDB
    # ConversionJobDB + CompressionJobDB
    assert mock_job_cleanup.call_count == 2
    mock_guest_cleanup.assert_called_once()
    mock_sleep.assert_called_once_with(60)


@patch("background.cleanup.time.sleep", side_effect=StopIteration)
@patch("background.cleanup.guest_cleanup_logic", side_effect=RuntimeError("boom"))
@patch("background.cleanup.job_cleanup_logic")
@patch("background.cleanup.file_cleanup_logic")
@patch("background.cleanup.CompressionJobDB")
@patch("background.cleanup.ConversionJobDB")
@patch("background.cleanup.ConversionRelationsDB")
@patch("background.cleanup.ConversionDB")
@patch("background.cleanup.FileDB")
def test_cleanup_task_catches_exceptions(
    mock_file_cls, mock_conv_cls, mock_conv_rel_cls,
    mock_conv_job_cls, mock_comp_job_cls,
    mock_file_cleanup, mock_job_cleanup, mock_guest_cleanup, mock_sleep,
):
    """Exceptions inside the loop are caught so the task keeps running."""
    with pytest.raises(StopIteration):
        file_cleanup_task()

    mock_sleep.assert_called_once_with(60)


# ── get_upload_cleanup_thread ────────────────────────────────────────

def test_returns_daemon_thread():
    t = get_upload_cleanup_thread()
    assert isinstance(t, threading.Thread)
    assert t.daemon is True
    assert t.is_alive() is False


# ── chunk_cleanup_logic ──────────────────────────────────────────────

class TestChunkCleanupLogic:

    def test_removes_stale_sessions(self, tmp_path, monkeypatch):
        chunks_dir = tmp_path / "chunks"
        chunks_dir.mkdir()
        stale = chunks_dir / str(uuid.uuid4())
        stale.mkdir()
        (stale / "0.part").write_bytes(b"data")

        old_time = time.time() - 90000
        os.utime(stale, (old_time, old_time))

        monkeypatch.setattr("background.cleanup.get_settings", lambda: MagicMock(chunks_dir=chunks_dir))

        chunk_cleanup_logic()

        assert not stale.exists()

    def test_keeps_fresh_sessions(self, tmp_path, monkeypatch):
        chunks_dir = tmp_path / "chunks"
        chunks_dir.mkdir()
        fresh = chunks_dir / str(uuid.uuid4())
        fresh.mkdir()
        (fresh / "0.part").write_bytes(b"data")

        monkeypatch.setattr("background.cleanup.get_settings", lambda: MagicMock(chunks_dir=chunks_dir))

        chunk_cleanup_logic()

        assert fresh.exists()
        assert (fresh / "0.part").read_bytes() == b"data"
