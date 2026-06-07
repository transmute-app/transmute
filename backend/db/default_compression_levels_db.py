import sqlite3
import threading
from core import get_settings, validate_sql_identifier, migrate_table_columns, assign_orphaned_rows_to_admin

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table 
name is validated and locked after initialization, and the values are 
parameterized to prevent SQL injection.
'''

class DefaultCompressionLevelsDB:
    """Database class for managing default compression levels per media format.

    Stores user-configured default compression levels for media formats that
    support compression-level presets.  For example, a user can set
    jpeg -> max so that every time a JPEG is compressed, the compression-level
    dropdown defaults to 'max' instead of 'balanced'.

    Attributes:
        settings: Application settings instance.
        DB_PATH: Path to the SQLite database file.
        _TABLE_NAME: Name of the database table for default compression levels.
        conn: Active SQLite database connection.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = "DEFAULT_COMPRESSION_LEVELS"

    @property
    def TABLE_NAME(self) -> str:
        """str: The validated, immutable table name."""
        return self._table_name

    def __init__(self) -> None:
        """Initialize DefaultCompressionLevelsDB, validate the table name, and create tables."""
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
        """Create the default compression levels table if it does not already exist."""
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    user_id            TEXT NOT NULL,
                    media_format       TEXT NOT NULL,
                    compression_level  TEXT NOT NULL,
                    PRIMARY KEY (user_id, media_format)
                )
            """)  # nosec B608

        migrate_table_columns(self.conn, self.TABLE_NAME, {
            "user_id":            "TEXT",
            "media_format":       "TEXT",
            "compression_level":  "TEXT",
        })

        # Assign pre-auth orphaned rows to the first admin
        assign_orphaned_rows_to_admin(self.conn, self.TABLE_NAME)

    def get_all(self, user_id: str) -> list[dict]:
        """Return all default compression-level mappings for a user."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT media_format, compression_level FROM {self.TABLE_NAME} WHERE user_id = ? ORDER BY media_format",  # nosec B608
            (user_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get(self, user_id: str, media_format: str) -> dict | None:
        """Return the default compression level for a given media format and user."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT media_format, compression_level FROM {self.TABLE_NAME} WHERE user_id = ? AND media_format = ?",  # nosec B608
            (user_id, media_format)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def upsert(self, user_id: str, media_format: str, compression_level: str) -> dict:
        """Insert or update a default compression-level mapping for a user."""
        with self.conn:
            self.conn.execute(
                f"INSERT INTO {self.TABLE_NAME} (user_id, media_format, compression_level) "  # nosec B608
                f"VALUES (?, ?, ?) "
                f"ON CONFLICT(user_id, media_format) DO UPDATE SET compression_level = excluded.compression_level",
                (user_id, media_format, compression_level)
            )
        return {"media_format": media_format, "compression_level": compression_level}

    def delete(self, user_id: str, media_format: str) -> bool:
        """Delete a default compression-level mapping for a user."""
        with self.conn:
            cursor = self.conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE user_id = ? AND media_format = ?",  # nosec B608
                (user_id, media_format)
            )
        return cursor.rowcount > 0

    def delete_all(self, user_id: str) -> int:
        """Delete all default compression-level mappings for a user."""
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
