import pytest

from db import ConversionJobDB


@pytest.fixture
def job_db(monkeypatch):
    monkeypatch.setattr(ConversionJobDB, "DB_PATH", ":memory:")
    db = ConversionJobDB()
    try:
        yield db
    finally:
        db.close()


def _make_job(user_id="user-a", source_id="file-1", output_format="png", **extra):
    base = {
        "user_id": user_id,
        "source_file_id": source_id,
        "output_format": output_format,
        "quality": "medium",
        "converter_name": "PillowConverter",
        "source_filename": "photo.jpg",
        "source_media_type": "jpg",
        "source_extension": ".jpg",
        "source_size_bytes": 12345,
    }
    base.update(extra)
    return base


def test_table_has_all_expected_columns(job_db):
    columns = {row[1] for row in job_db.conn.execute(
        f"PRAGMA table_info({job_db.TABLE_NAME})"
    ).fetchall()}

    expected = {
        "id", "user_id", "source_file_id", "output_format", "quality",
        "status", "progress", "error_message", "output_file_id",
        "converter_name", "source_filename", "source_media_type",
        "source_extension", "source_size_bytes",
        "created_at", "started_at", "completed_at", "updated_at",
    }
    assert expected.issubset(columns)


def test_insert_job_returns_queued_row(job_db):
    job = job_db.insert_job(_make_job())

    assert job["status"] == "queued"
    assert job["id"]
    assert job["user_id"] == "user-a"
    assert job["source_file_id"] == "file-1"
    assert job["output_format"] == "png"
    assert job["progress"] is None
    assert job["output_file_id"] is None
    assert job["created_at"] is not None


def test_insert_job_rejects_missing_required_fields(job_db):
    with pytest.raises(ValueError):
        job_db.insert_job({"user_id": "u", "output_format": "png"})


def test_get_job_enforces_owner_filter(job_db):
    job = job_db.insert_job(_make_job(user_id="user-a"))

    assert job_db.get_job(job["id"], user_id="user-a") is not None
    assert job_db.get_job(job["id"], user_id="user-b") is None
    # No filter still returns it
    assert job_db.get_job(job["id"]) is not None


def test_list_jobs_filters_by_user_and_status(job_db):
    job_db.insert_job(_make_job(user_id="user-a", source_id="f1"))
    job_db.insert_job(_make_job(user_id="user-a", source_id="f2"))
    job_db.insert_job(_make_job(user_id="user-b", source_id="f3"))

    a_jobs = job_db.list_jobs(user_id="user-a")
    assert {j["source_file_id"] for j in a_jobs} == {"f1", "f2"}

    queued = job_db.list_jobs(user_id="user-a", status="queued")
    assert len(queued) == 2

    completed = job_db.list_jobs(user_id="user-a", status="completed")
    assert completed == []


def test_count_jobs_filters_by_user_and_status(job_db):
    job_a1 = job_db.insert_job(_make_job(user_id="user-a", source_id="f1"))
    job_db.insert_job(_make_job(user_id="user-a", source_id="f2"))
    job_db.insert_job(_make_job(user_id="user-b", source_id="f3"))
    job_db.claim_next_queued_job()
    job_db.mark_completed(job_a1["id"], output_file_id="out-1")

    assert job_db.count_jobs() == 3
    assert job_db.count_jobs(user_id="user-a") == 2
    assert job_db.count_jobs(user_id="user-b") == 1
    assert job_db.count_jobs(user_id="user-a", status="completed") == 1
    assert job_db.count_jobs(status="queued") == 2


def test_claim_next_queued_job_marks_running(job_db):
    job1 = job_db.insert_job(_make_job(source_id="f1"))
    job2 = job_db.insert_job(_make_job(source_id="f2"))

    claimed = job_db.claim_next_queued_job()
    assert claimed is not None
    # Oldest first - job1 was inserted first.
    assert claimed["id"] == job1["id"]
    assert claimed["status"] == "running"
    assert claimed["started_at"] is not None

    second = job_db.claim_next_queued_job()
    assert second is not None
    assert second["id"] == job2["id"]

    # Queue exhausted
    assert job_db.claim_next_queued_job() is None


def test_mark_completed_sets_output_file_id(job_db):
    job = job_db.insert_job(_make_job())
    job_db.claim_next_queued_job()

    job_db.mark_completed(job["id"], output_file_id="out-1")

    refreshed = job_db.get_job(job["id"])
    assert refreshed["status"] == "completed"
    assert refreshed["output_file_id"] == "out-1"
    assert refreshed["completed_at"] is not None
    assert refreshed["error_message"] is None


def test_mark_failed_records_error(job_db):
    job = job_db.insert_job(_make_job())
    job_db.claim_next_queued_job()

    job_db.mark_failed(job["id"], "boom")

    refreshed = job_db.get_job(job["id"])
    assert refreshed["status"] == "failed"
    assert refreshed["error_message"] == "boom"
    assert refreshed["completed_at"] is not None


def test_cancel_queued_job_only_works_when_queued(job_db):
    job = job_db.insert_job(_make_job(user_id="user-a"))

    assert job_db.cancel_queued_job(job["id"], "user-a") is True
    assert job_db.get_job(job["id"])["status"] == "cancelled"

    # Cannot cancel again
    assert job_db.cancel_queued_job(job["id"], "user-a") is False


def test_cancel_queued_job_rejects_running(job_db):
    job = job_db.insert_job(_make_job(user_id="user-a"))
    job_db.claim_next_queued_job()

    assert job_db.cancel_queued_job(job["id"], "user-a") is False
    assert job_db.get_job(job["id"])["status"] == "running"


def test_cancel_queued_job_enforces_owner(job_db):
    job = job_db.insert_job(_make_job(user_id="user-a"))

    assert job_db.cancel_queued_job(job["id"], "user-b") is False
    assert job_db.get_job(job["id"])["status"] == "queued"


def test_retry_terminal_job_resets_failed_to_queued(job_db):
    job = job_db.insert_job(_make_job(user_id="user-a"))
    job_db.claim_next_queued_job()
    job_db.mark_failed(job["id"], "boom")

    assert job_db.retry_terminal_job(job["id"], "user-a") is True
    refreshed = job_db.get_job(job["id"])
    assert refreshed["status"] == "queued"
    assert refreshed["error_message"] is None
    assert refreshed["output_file_id"] is None
    assert refreshed["started_at"] is None
    assert refreshed["completed_at"] is None
    assert refreshed["progress"] == 0


def test_retry_terminal_job_resets_cancelled_to_queued(job_db):
    job = job_db.insert_job(_make_job(user_id="user-a"))
    job_db.cancel_queued_job(job["id"], "user-a")

    assert job_db.retry_terminal_job(job["id"], "user-a") is True
    assert job_db.get_job(job["id"])["status"] == "queued"


def test_retry_terminal_job_rejects_running_and_completed(job_db):
    job = job_db.insert_job(_make_job(user_id="user-a"))
    job_db.claim_next_queued_job()

    # running -> not retryable
    assert job_db.retry_terminal_job(job["id"], "user-a") is False
    assert job_db.get_job(job["id"])["status"] == "running"

    job_db.mark_completed(job["id"], "out-1")
    # completed -> not retryable
    assert job_db.retry_terminal_job(job["id"], "user-a") is False
    assert job_db.get_job(job["id"])["status"] == "completed"


def test_retry_terminal_job_enforces_owner(job_db):
    job = job_db.insert_job(_make_job(user_id="user-a"))
    job_db.claim_next_queued_job()
    job_db.mark_failed(job["id"], "boom")

    assert job_db.retry_terminal_job(job["id"], "user-b") is False
    assert job_db.get_job(job["id"])["status"] == "failed"


def test_fail_running_jobs_recovers_stale_running(job_db):
    job = job_db.insert_job(_make_job())
    job_db.claim_next_queued_job()
    queued_only = job_db.insert_job(_make_job(source_id="f-other"))

    affected = job_db.fail_running_jobs("interrupted")

    assert affected == 1
    assert job_db.get_job(job["id"])["status"] == "failed"
    assert job_db.get_job(job["id"])["error_message"] == "interrupted"
    # Queued jobs remain untouched.
    assert job_db.get_job(queued_only["id"])["status"] == "queued"


def test_requeue_running_jobs_recovers_stale_running(job_db):
    job = job_db.insert_job(_make_job())
    job_db.claim_next_queued_job()
    job_db.update_progress(job["id"], 42)
    queued_only = job_db.insert_job(_make_job(source_id="f-other"))

    affected = job_db.requeue_running_jobs()

    assert affected == 1
    recovered = job_db.get_job(job["id"])
    assert recovered["status"] == "queued"
    assert recovered["progress"] == 0
    assert recovered["error_message"] is None
    assert recovered["started_at"] is None
    assert recovered["completed_at"] is None
    # Queued jobs remain untouched.
    assert job_db.get_job(queued_only["id"])["status"] == "queued"


def test_update_progress_clamps_values(job_db):
    job = job_db.insert_job(_make_job())

    job_db.update_progress(job["id"], 150)
    assert job_db.get_job(job["id"])["progress"] == 100

    job_db.update_progress(job["id"], -10)
    assert job_db.get_job(job["id"])["progress"] == 0

    job_db.update_progress(job["id"], 42)
    assert job_db.get_job(job["id"])["progress"] == 42


def test_delete_jobs_for_user_only_removes_owned_rows(job_db):
    job_db.insert_job(_make_job(user_id="user-a", source_id="f1"))
    job_db.insert_job(_make_job(user_id="user-a", source_id="f2"))
    other = job_db.insert_job(_make_job(user_id="user-b", source_id="f3"))

    deleted = job_db.delete_jobs_for_user("user-a")

    assert deleted == 2
    assert job_db.list_jobs(user_id="user-a") == []
    assert job_db.get_job(other["id"]) is not None
