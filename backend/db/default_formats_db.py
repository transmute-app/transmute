import sqlite3
import threading
from core import get_settings, validate_sql_identifier, migrate_table_columns, assign_orphaned_rows_to_admin

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table 
name is validated and locked after initialization, and the values are 
parameterized to prevent SQL injection.
'''


class DefaultFormatsDB:
    """Database class for managing default format conversion mappings.

    Stores user-configured default output formats for given input formats.
    For example, a user can set png -> jpeg so that every time a PNG is
    uploaded, the output format dropdown defaults to JPEG.

    Attributes:
        settings: Application settings instance.
        DB_PATH: Path to the SQLite database file.
        _TABLE_NAME: Name of the database table for default formats.
        conn: Active SQLite database connection.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = "DEFAULT_FORMATS"

    @property
    def TABLE_NAME(self) -> str:
        """str: The validated, immutable table name."""
        return self._table_name

    def __init__(self) -> None:
        """Initialize DefaultFormatsDB, validate the table name, and create tables."""
        object.__setattr__(self, '_table_name', validate_sql_identifier(self._TABLE_NAME))
        self._local = threading.local()
        self.create_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        """Return a thread-local SQLite connection, creating one if needed."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.DB_PATH)
        return self._local.conn

    def create_tables(self) -> None:
        """Create the default formats table if it does not already exist."""
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    user_id       TEXT NOT NULL,
                    input_format  TEXT NOT NULL,
                    output_format TEXT NOT NULL,
                    PRIMARY KEY (user_id, input_format)
                )
            """)  # nosec B608

        migrate_table_columns(self.conn, self.TABLE_NAME, {
            "user_id":       "TEXT",
            "input_format":  "TEXT",
            "output_format": "TEXT",
        })

        # Assign pre-auth orphaned rows to the first admin
        assign_orphaned_rows_to_admin(self.conn, self.TABLE_NAME)

        # Migrate from old single-column PK (input_format) to composite PK (user_id, input_format).
        # SQLite's CREATE TABLE IF NOT EXISTS won't alter an existing table's PK,
        # so we must detect the old schema and rebuild.
        self._migrate_primary_key()

    def _migrate_primary_key(self) -> None:
        """Rebuild the table if the PK is the old single-column (input_format) layout."""
        cursor = self.conn.execute(
            f"PRAGMA table_info({self.TABLE_NAME})"  # nosec B608
        )
        pk_columns = [row[1] for row in cursor.fetchall() if row[5] > 0]  # row[5] = pk flag
        # If user_id is already part of the PK, nothing to do
        if "user_id" in pk_columns:
            return
        # Rebuild: copy data → drop old → create new → restore data
        tmp = f"{self.TABLE_NAME}_migrate_tmp"
        with self.conn:
            self.conn.execute(
                f"CREATE TABLE {tmp} AS SELECT user_id, input_format, output_format FROM {self.TABLE_NAME}"  # nosec B608
            )
            self.conn.execute(f"DROP TABLE {self.TABLE_NAME}")  # nosec B608
            self.conn.execute(f"""
                CREATE TABLE {self.TABLE_NAME} (
                    user_id       TEXT NOT NULL,
                    input_format  TEXT NOT NULL,
                    output_format TEXT NOT NULL,
                    PRIMARY KEY (user_id, input_format)
                )
            """)  # nosec B608
            self.conn.execute(
                f"INSERT OR IGNORE INTO {self.TABLE_NAME} (user_id, input_format, output_format) "  # nosec B608
                f"SELECT user_id, input_format, output_format FROM {tmp}"
            )
            self.conn.execute(f"DROP TABLE {tmp}")  # nosec B608

    def get_all(self, user_id: str) -> list[dict]:
        """Return all default format mappings for a user."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT input_format, output_format FROM {self.TABLE_NAME} WHERE user_id = ? ORDER BY input_format",  # nosec B608
            (user_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get(self, user_id: str, input_format: str) -> dict | None:
        """Return the default output format for a given input format and user."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT input_format, output_format FROM {self.TABLE_NAME} WHERE user_id = ? AND input_format = ?",  # nosec B608
            (user_id, input_format)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def upsert(self, user_id: str, input_format: str, output_format: str) -> dict:
        """Insert or update a default format mapping for a user."""
        with self.conn:
            self.conn.execute(
                f"INSERT INTO {self.TABLE_NAME} (user_id, input_format, output_format) "  # nosec B608
                f"VALUES (?, ?, ?) "
                f"ON CONFLICT(user_id, input_format) DO UPDATE SET output_format = excluded.output_format",
                (user_id, input_format, output_format)
            )
        return {"input_format": input_format, "output_format": output_format}

    def delete(self, user_id: str, input_format: str) -> bool:
        """Delete a default format mapping for a user."""
        with self.conn:
            cursor = self.conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE user_id = ? AND input_format = ?",  # nosec B608
                (user_id, input_format)
            )
        return cursor.rowcount > 0

    def delete_all(self, user_id: str) -> int:
        """Delete all default format mappings for a user."""
        with self.conn:
            cursor = self.conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE user_id = ?",  # nosec B608
                (user_id,)
            )
        return cursor.rowcount

    def close(self) -> None:
        """Close the current thread's database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
