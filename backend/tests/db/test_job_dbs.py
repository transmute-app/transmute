"""Tests for bulk job deletes used by the "clear history" endpoints."""
import pytest

from db import CompressionJobDB, ConversionJobDB


@pytest.fixture
def conversion_job_db(monkeypatch):
    monkeypatch.setattr(ConversionJobDB, "DB_PATH", ":memory:")
    db = ConversionJobDB()
    yield db
    db.close()


@pytest.fixture
def compression_job_db(monkeypatch):
    monkeypatch.setattr(CompressionJobDB, "DB_PATH", ":memory:")
    db = CompressionJobDB()
    yield db
    db.close()


def _seed_conversion_jobs(db, user_id):
    """Insert one job per status for `user_id` and return {status: job_id}."""
    ids = {}

    running = db.insert_job({
        "user_id": user_id, "source_file_id": "src", "output_format": "png",
    })
    db.claim_next_queued_job()  # queued -> running
    ids["running"] = running["id"]

    failed = db.insert_job({
        "user_id": user_id, "source_file_id": "src", "output_format": "png",
    })
    db.mark_failed(failed["id"], "boom")
    ids["failed"] = failed["id"]

    completed = db.insert_job({
        "user_id": user_id, "source_file_id": "src", "output_format": "png",
    })
    db.mark_completed(completed["id"], "out-1")
    ids["completed"] = completed["id"]

    cancelled = db.insert_job({
        "user_id": user_id, "source_file_id": "src", "output_format": "png",
    })
    db.cancel_queued_job(cancelled["id"], user_id)
    ids["cancelled"] = cancelled["id"]

    queued = db.insert_job({
        "user_id": user_id, "source_file_id": "src", "output_format": "png",
    })
    ids["queued"] = queued["id"]

    return ids


class TestDeleteTerminalJobsForUser:

    def test_deletes_only_terminal_jobs(self, conversion_job_db):
        ids = _seed_conversion_jobs(conversion_job_db, "user-a")

        deleted = conversion_job_db.delete_terminal_jobs_for_user("user-a")

        assert deleted == 3  # completed + failed + cancelled
        remaining = {job["id"] for job in conversion_job_db.list_jobs(user_id="user-a")}
        assert remaining == {ids["queued"], ids["running"]}

    def test_leaves_other_users_jobs_alone(self, conversion_job_db):
        _seed_conversion_jobs(conversion_job_db, "user-a")
        other = conversion_job_db.insert_job({
            "user_id": "user-b", "source_file_id": "src", "output_format": "png",
        })
        conversion_job_db.mark_failed(other["id"], "boom")

        conversion_job_db.delete_terminal_jobs_for_user("user-a")

        assert conversion_job_db.get_job(other["id"]) is not None

    def test_returns_zero_when_nothing_to_delete(self, conversion_job_db):
        assert conversion_job_db.delete_terminal_jobs_for_user("user-a") == 0

    def test_compression_jobs_behave_the_same(self, compression_job_db):
        failed = compression_job_db.insert_job({
            "user_id": "user-a", "source_file_id": "src",
        })
        compression_job_db.mark_failed(failed["id"], "boom")
        queued = compression_job_db.insert_job({
            "user_id": "user-a", "source_file_id": "src",
        })

        deleted = compression_job_db.delete_terminal_jobs_for_user("user-a")

        assert deleted == 1
        remaining = {job["id"] for job in compression_job_db.list_jobs(user_id="user-a")}
        assert remaining == {queued["id"]}
