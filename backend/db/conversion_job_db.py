import sqlite3
import threading
import uuid
from typing import Optional

from core import get_settings, validate_sql_identifier, migrate_table_columns

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table
name is validated and locked after initialization, and the values are
parameterized to prevent SQL injection.
'''


# Allowed status values. The `cancel_requested` flag is intentionally separate
# so a running job can be flagged for future cancellation without losing its
# `running` status until the worker observes the flag.
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

ALL_STATUSES = {
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_CANCELLED,
}

TERMINAL_STATUSES = {STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED}

class ConversionJobDB:
    """Database class for managing queued conversion jobs.

    Stores durable status for conversions so users can see queued, running,
    completed, failed, and cancelled jobs even after closing the page or
    restarting the app.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = settings.conversion_jobs_table_name

    @property
    def TABLE_NAME(self) -> str:
        return self._table_name

    def __init__(self) -> None:
        object.__setattr__(self, '_table_name', validate_sql_identifier(self._TABLE_NAME))
        self._local = threading.local()
        self.create_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.DB_PATH)
        return self._local.conn

    def create_tables(self) -> None:
        """Create the conversion jobs table if missing and ensure all columns exist."""
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    source_file_id TEXT NOT NULL,
                    output_format TEXT NOT NULL,
                    quality TEXT,
                    status TEXT NOT NULL DEFAULT 'queued',
                    progress INTEGER,
                    error_message TEXT,
                    output_file_id TEXT,
                    converter_name TEXT,
                    source_filename TEXT,
                    source_media_type TEXT,
                    source_extension TEXT,
                    source_size_bytes INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)  # nosec B608

        # Tolerate older DBs by ensuring every expected column is present.
        migrate_table_columns(self.conn, self.TABLE_NAME, {
            "user_id":            "TEXT",
            "source_file_id":     "TEXT",
            "output_format":      "TEXT",
            "quality":            "TEXT",
            "status":             "TEXT",
            "progress":           "INTEGER",
            "error_message":      "TEXT",
            "output_file_id":     "TEXT",
            "converter_name":     "TEXT",
            "source_filename":    "TEXT",
            "source_media_type":  "TEXT",
            "source_extension":   "TEXT",
            "source_size_bytes":  "INTEGER",
            "created_at":         "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "started_at":         "TIMESTAMP",
            "completed_at":       "TIMESTAMP",
            "updated_at":         "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        })

        with self.conn:
            self.conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_user_created "  # nosec B608
                f"ON {self.TABLE_NAME} (user_id, created_at DESC)"
            )
            self.conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_status_created "  # nosec B608
                f"ON {self.TABLE_NAME} (status, created_at)"
            )
            self.conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_output_file "  # nosec B608
                f"ON {self.TABLE_NAME} (output_file_id)"
            )

    # ── inserts ─────────────────────────────────────────────────────

    def insert_job(self, metadata: dict) -> dict:
        """Insert a queued conversion job and return the stored row.

        Required keys: ``user_id``, ``source_file_id``, ``output_format``.
        Optional keys: ``id``, ``quality``, ``converter_name``,
        ``source_filename``, ``source_media_type``, ``source_extension``,
        ``source_size_bytes``.
        """
        required = {"user_id", "source_file_id", "output_format"}
        missing = required - metadata.keys()
        if missing:
            raise ValueError(f"insert_job missing required fields: {sorted(missing)}")

        job_id = metadata.get("id") or str(uuid.uuid4())

        with self.conn:
            self.conn.execute(
                f"""
                INSERT INTO {self.TABLE_NAME} (
                    id, user_id, source_file_id, output_format, quality,
                    status, converter_name,
                    source_filename, source_media_type, source_extension, source_size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,  # nosec B608
                (
                    job_id,
                    metadata["user_id"],
                    metadata["source_file_id"],
                    metadata["output_format"],
                    metadata.get("quality"),
                    STATUS_QUEUED,
                    metadata.get("converter_name"),
                    metadata.get("source_filename"),
                    metadata.get("source_media_type"),
                    metadata.get("source_extension"),
                    metadata.get("source_size_bytes"),
                ),
            )

        job = self.get_job(job_id)
        if job is None:
            # Should be unreachable, but fail loudly rather than return None.
            raise RuntimeError(f"Job {job_id} not found immediately after insert")
        return job

    # ── reads ───────────────────────────────────────────────────────

    def get_job(self, job_id: str, user_id: str | None = None) -> Optional[dict]:
        """Get a job by ID, optionally restricted to a specific owner."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        if user_id is not None:
            cursor.execute(
                f"SELECT * FROM {self.TABLE_NAME} WHERE id = ? AND user_id = ?",  # nosec B608
                (job_id, user_id),
            )
        else:
            cursor.execute(
                f"SELECT * FROM {self.TABLE_NAME} WHERE id = ?",  # nosec B608
                (job_id,),
            )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_jobs(
        self,
        user_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        """List jobs newest-first, filtered by owner and/or status."""
        clauses: list[str] = []
        params: list = []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = ""
        if limit is not None:
            limit_sql = " LIMIT ? OFFSET ?"
            params.extend([int(limit), int(offset)])

        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT * FROM {self.TABLE_NAME} {where_sql} ORDER BY created_at DESC, rowid DESC{limit_sql}",  # nosec B608
            tuple(params),
        )
        return [dict(row) for row in cursor.fetchall()]

    def count_jobs(self, user_id: str | None = None, status: str | None = None) -> int:
        """Count jobs, optionally filtered by owner and/or status."""
        clauses: list[str] = []
        params: list = []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT COUNT(*) FROM {self.TABLE_NAME} {where_sql}",  # nosec B608
            tuple(params),
        )
        row = cursor.fetchone()
        return int(row[0]) if row is not None else 0

    # ── status transitions ──────────────────────────────────────────

    def claim_next_queued_job(self) -> Optional[dict]:
        """Atomically pick the oldest queued job and mark it running.

        Returns the claimed job row or None if no queued job exists. Designed
        for a single-worker, single-process deployment; uses an IMMEDIATE
        transaction so a concurrent claimer would serialize on the SQLite
        write lock.
        """
        # BEGIN IMMEDIATE acquires the reserved lock so two workers cannot
        # both observe the same queued job and double-claim it.
        try:
            self.conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            return None
        try:
            cursor = self.conn.cursor()
            cursor.row_factory = sqlite3.Row
            cursor.execute(
                f"SELECT * FROM {self.TABLE_NAME} WHERE status = ? "  # nosec B608
                f"ORDER BY created_at ASC, rowid ASC LIMIT 1",
                (STATUS_QUEUED,),
            )
            row = cursor.fetchone()
            if row is None:
                self.conn.commit()
                return None
            job_id = row["id"]
            self.conn.execute(
                f"UPDATE {self.TABLE_NAME} "  # nosec B608
                f"SET status = ?, started_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id = ?",
                (STATUS_RUNNING, job_id),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        return self.get_job(job_id)

    def mark_completed(self, job_id: str, output_file_id: str) -> None:
        with self.conn:
            self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET "  # nosec B608
                f"status = ?, output_file_id = ?, error_message = NULL, "
                f"completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id = ?",
                (STATUS_COMPLETED, output_file_id, job_id),
            )

    def mark_failed(self, job_id: str, error_message: str) -> None:
        with self.conn:
            self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET "  # nosec B608
                f"status = ?, error_message = ?, "
                f"completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id = ?",
                (STATUS_FAILED, error_message, job_id),
            )

    def cancel_queued_job(self, job_id: str, user_id: str) -> bool:
        """Cancel a job only if it is currently queued and owned by user.

        Returns True when a row was updated, False otherwise.
        """
        with self.conn:
            cursor = self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET "  # nosec B608
                f"status = ?, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id = ? AND user_id = ? AND status = ?",
                (STATUS_CANCELLED, job_id, user_id, STATUS_QUEUED),
            )
            return cursor.rowcount > 0

    def retry_terminal_job(self, job_id: str, user_id: str) -> bool:
        """Re-queue a job that previously ended in failed or cancelled.

        Resets progress/error/timestamps/output so the worker treats it as a
        fresh queued job. Returns True when a row was updated, False otherwise.
        """
        with self.conn:
            cursor = self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET "  # nosec B608
                f"status = ?, progress = 0, error_message = NULL, "
                f"output_file_id = NULL, started_at = NULL, completed_at = NULL, "
                f"updated_at = CURRENT_TIMESTAMP "
                f"WHERE id = ? AND user_id = ? AND status IN (?, ?)",
                (STATUS_QUEUED, job_id, user_id, STATUS_FAILED, STATUS_CANCELLED),
            )
            return cursor.rowcount > 0

    def update_progress(self, job_id: str, progress: int) -> None:
        progress = max(0, min(100, int(progress)))
        with self.conn:
            self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET "  # nosec B608
                f"progress = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (progress, job_id),
            )

    def fail_running_jobs(self, error_message: str) -> int:
        """Mark every currently running job as failed.

        Used at startup to recover from crashes/restarts where the worker
        was interrupted mid-conversion. Returns the number of rows updated.
        """
        with self.conn:
            cursor = self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET "  # nosec B608
                f"status = ?, error_message = ?, "
                f"completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                f"WHERE status = ?",
                (STATUS_FAILED, error_message, STATUS_RUNNING),
            )
            return cursor.rowcount

    def requeue_running_jobs(self) -> int:
        """Re-queue every currently running job.

        Used at startup to recover from crashes/restarts where the worker
        was interrupted mid-conversion. Since jobs are not resumable, we
        reset them back to a fresh queued state so the worker can retry
        them from scratch.
        """
        with self.conn:
            cursor = self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET "  # nosec B608
                f"status = ?, progress = 0, error_message = NULL, "
                f"started_at = NULL, completed_at = NULL, updated_at = CURRENT_TIMESTAMP "
                f"WHERE status = ?",
                (STATUS_QUEUED, STATUS_RUNNING),
            )
            return cursor.rowcount

    # ── deletes ─────────────────────────────────────────────────────

    def delete_job(self, job_id: str, user_id: str | None = None) -> bool:
        with self.conn:
            if user_id is not None:
                cursor = self.conn.execute(
                    f"DELETE FROM {self.TABLE_NAME} WHERE id = ? AND user_id = ?",  # nosec B608
                    (job_id, user_id),
                )
            else:
                cursor = self.conn.execute(
                    f"DELETE FROM {self.TABLE_NAME} WHERE id = ?",  # nosec B608
                    (job_id,),
                )
            return cursor.rowcount > 0

    def delete_jobs_for_user(self, user_id: str) -> int:
        with self.conn:
            cursor = self.conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE user_id = ?",  # nosec B608
                (user_id,),
            )
            return cursor.rowcount

    def close(self) -> None:
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
