import sqlite3
import threading
from enum import Enum
from core import get_settings, validate_sql_identifier, migrate_table_columns, assign_orphaned_rows_to_admin

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table 
name is validated and locked after initialization, and the values are 
parameterized to prevent SQL injection.
'''


class Theme(str, Enum):
    """Enumeration of available UI themes."""

    RUBEDO     = "rubedo"
    CITRINITAS = "citrinitas"
    VIRIDITAS  = "viriditas"
    NIGREDO    = "nigredo"
    ALBEDO     = "albedo"
    AURORA     = "aurora"
    CAELUM     = "caelum"
    ARGENTUM   = "argentum"


# Defaults applied when a user has no settings row yet
_DEFAULT_SETTINGS = {
    "theme":            Theme.RUBEDO.value,
    "auto_download":    False,
    "keep_originals":   True,
    "cleanup_enabled":  True,
    "cleanup_ttl_minutes": 60
}


class SettingsDB:
    """Database class for managing application settings.

    Manages a single-row settings table that stores user-configurable
    application preferences such as theme, auto-download behaviour,
    and whether original files are retained after conversion.

    Attributes:
        settings: Application settings instance.
        DB_PATH: Path to the SQLite database file.
        _TABLE_NAME: Name of the database table for app settings.
        conn: Active SQLite database connection.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = settings.app_settings_table_name

    @property
    def TABLE_NAME(self) -> str:
        """str: The validated, immutable table name."""
        return self._table_name

    def __init__(self) -> None:
        """Initialize SettingsDB, validate the table name, and create tables."""
        # Validate and lock table name — immutable after init
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
        """Create the app settings table if it does not already exist."""
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id             INTEGER PRIMARY KEY,
                    user_id        TEXT,
                    theme          TEXT    NOT NULL DEFAULT '{Theme.RUBEDO.value}',
                    auto_download  INTEGER NOT NULL DEFAULT 0,
                    keep_originals INTEGER NOT NULL DEFAULT 1,
                    cleanup_enabled INTEGER NOT NULL DEFAULT 1,
                    cleanup_ttl_minutes INTEGER NOT NULL DEFAULT 60
                )
            """)  # nosec B608

        # Ensure every expected column exists (handles older DB schemas)
        migrate_table_columns(self.conn, self.TABLE_NAME, {
            "user_id":             "TEXT",
            "theme":               f"TEXT NOT NULL DEFAULT '{Theme.RUBEDO.value}'",
            "auto_download":       "INTEGER NOT NULL DEFAULT 0",
            "keep_originals":      "INTEGER NOT NULL DEFAULT 1",
            "cleanup_enabled":     "INTEGER NOT NULL DEFAULT 1",
            "cleanup_ttl_minutes": "INTEGER NOT NULL DEFAULT 60",
        })  # nosec B608

        # Assign pre-auth orphaned rows to the first admin
        assign_orphaned_rows_to_admin(self.conn, self.TABLE_NAME)

    def _ensure_user_row(self, user_id: str) -> None:
        """Insert the default settings row for a user if it does not already exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT id FROM {self.TABLE_NAME} WHERE user_id = ?",  # nosec B608
            (user_id,)
        )
        if cursor.fetchone() is None:
            with self.conn:
                self.conn.execute(
                    f"INSERT INTO {self.TABLE_NAME} (user_id, theme, auto_download, keep_originals, cleanup_enabled, cleanup_ttl_minutes) "  # nosec B608
                    f"VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        _DEFAULT_SETTINGS["theme"],
                        int(_DEFAULT_SETTINGS["auto_download"]),
                        int(_DEFAULT_SETTINGS["keep_originals"]),
                        int(_DEFAULT_SETTINGS["cleanup_enabled"]),
                        int(_DEFAULT_SETTINGS["cleanup_ttl_minutes"]),
                    )
                )

    @staticmethod
    def _row_to_dict(row: dict) -> dict:
        """Normalise a raw database row dict into typed application settings.

        Args:
            row: A dictionary produced by the Row-factory cursor, keyed by
                column name.

        Returns:
            A dictionary with keys theme (str), auto_download (bool),
            keep_originals (bool), cleanup_enabled (bool), and
            cleanup_ttl_minutes (int).
        """
        return {
            "theme":               row["theme"],
            "auto_download":       bool(row["auto_download"]),
            "keep_originals":      bool(row["keep_originals"]),
            "cleanup_enabled":     bool(row["cleanup_enabled"]),
            "cleanup_ttl_minutes": int(row["cleanup_ttl_minutes"]),
        }

    def get_settings(self, user_id: str) -> dict:
        """Return the settings for a given user, creating defaults if needed."""
        self._ensure_user_row(user_id)
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT * FROM {self.TABLE_NAME} WHERE user_id = ?",  # nosec B608
            (user_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return dict(_DEFAULT_SETTINGS)
        return self._row_to_dict(row)

    def update_settings(self, user_id: str, updates: dict) -> dict:
        """Apply a partial or full update to a user's settings."""
        self._ensure_user_row(user_id)
        # Prevent SQL injection by allowing only known columns
        allowed = {"theme", "auto_download", "keep_originals", "cleanup_enabled", "cleanup_ttl_minutes"}
        filtered = {k: v for k, v in updates.items() if k in allowed}

        if not filtered:
            return self.get_settings(user_id)

        # Prevent SQL injection by allowing only known theme values
        if "theme" in filtered:
            try:
                filtered["theme"] = Theme(filtered["theme"]).value
            except ValueError:
                valid = [t.value for t in Theme]
                raise ValueError(f"Invalid theme '{filtered['theme']}'. Must be one of: {valid}")

        if "auto_download" in filtered:
            filtered["auto_download"] = int(bool(filtered["auto_download"]))
        if "keep_originals" in filtered:
            filtered["keep_originals"] = int(bool(filtered["keep_originals"]))
        if "cleanup_enabled" in filtered:
            filtered["cleanup_enabled"] = int(bool(filtered["cleanup_enabled"]))
        if "cleanup_ttl_minutes" in filtered:
            filtered["cleanup_ttl_minutes"] = int(filtered["cleanup_ttl_minutes"])

        set_clause = ", ".join(f"{col} = ?" for col in filtered)
        values = list(filtered.values()) + [user_id]

        with self.conn:
            self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET {set_clause} WHERE user_id = ?",  # nosec B608
                values
            )

        return self.get_settings(user_id)

    def get_admin_cleanup_settings(self) -> dict:
        """Return cleanup settings from the first admin user's row.

        Falls back to defaults if no admin settings row exists or the
        users table has not been created yet (fresh install).
        Used by the background cleanup task.
        """
        try:
            cursor = self.conn.cursor()
            cursor.row_factory = sqlite3.Row
            # Find the first admin's settings by joining against the users table
            user_table = validate_sql_identifier(self.settings.user_table_name)
            cursor.execute(
                f"SELECT s.cleanup_enabled, s.cleanup_ttl_minutes "
                f"FROM {self.TABLE_NAME} s "
                f"INNER JOIN {user_table} u ON s.user_id = u.uuid "
                f"WHERE u.role = 'admin' "
                f"ORDER BY u.rowid LIMIT 1",  # nosec B608
            )
            row = cursor.fetchone()
        except sqlite3.OperationalError:
            row = None
        if row is None:
            return {
                "cleanup_enabled": _DEFAULT_SETTINGS["cleanup_enabled"],
                "cleanup_ttl_minutes": _DEFAULT_SETTINGS["cleanup_ttl_minutes"],
            }
        return {
            "cleanup_enabled": bool(row["cleanup_enabled"]),
            "cleanup_ttl_minutes": int(row["cleanup_ttl_minutes"]),
        }

    def delete_settings(self, user_id: str) -> bool:
        """Delete the settings row for a given user. Returns True if a row was deleted."""
        with self.conn:
            cursor = self.conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE user_id = ?",  # nosec B608
                (user_id,)
            )
        return cursor.rowcount > 0

    def close(self) -> None:
        """Close the current thread's database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
