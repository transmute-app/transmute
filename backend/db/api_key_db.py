import sqlite3
import threading
from typing import Optional
from core import get_settings, validate_sql_identifier, migrate_table_columns

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table
name is validated and locked after initialization, and the values are
parameterized to prevent SQL injection.
'''


class ApiKeyDB:
    """Database class for managing per-user API keys.

    Stores hashed API keys with a short prefix for identification.
    The raw key is shown once at creation time and never stored.

    Attributes:
        settings: Application settings instance.
        DB_PATH: Path to the SQLite database file.
        _TABLE_NAME: Name of the database table for API keys.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = "API_KEYS"

    @property
    def TABLE_NAME(self) -> str:
        """str: The validated, immutable table name."""
        return self._table_name

    def __init__(self) -> None:
        """Initialize ApiKeyDB, validate the table name, and create tables."""
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
        """Create the API keys table if it does not already exist."""
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id TEXT PRIMARY KEY UNIQUE,
                    user_uuid TEXT NOT NULL,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    prefix TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)  # nosec B608

        with self.conn:
            self.conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME.lower()}_user_uuid ON {self.TABLE_NAME} (user_uuid)"  # nosec B608
            )

        with self.conn:
            self.conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME.lower()}_prefix ON {self.TABLE_NAME} (prefix)"  # nosec B608
            )

        migrate_table_columns(self.conn, self.TABLE_NAME, {
            "user_uuid": "TEXT NOT NULL",
            "name": "TEXT NOT NULL",
            "key_hash": "TEXT NOT NULL",
            "prefix": "TEXT NOT NULL",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        })

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Normalize a raw database row into API key metadata (no hash)."""
        return {
            "id": row["id"],
            "user_uuid": row["user_uuid"],
            "name": row["name"],
            "prefix": row["prefix"],
            "created_at": row["created_at"],
        }

    def insert_api_key(self, key_data: dict) -> dict:
        """Insert a new API key record into the database.

        Args:
            key_data: Dictionary with keys: id, user_uuid, name, key_hash, prefix.

        Returns:
            The inserted record as a dictionary (without key_hash).
        """
        with self.conn:
            self.conn.execute(
                f"INSERT INTO {self.TABLE_NAME} (id, user_uuid, name, key_hash, prefix) "  # nosec B608
                f"VALUES (?, ?, ?, ?, ?)",
                (
                    key_data["id"],
                    key_data["user_uuid"],
                    key_data["name"],
                    key_data["key_hash"],
                    key_data["prefix"],
                )
            )
        return {
            "id": key_data["id"],
            "user_uuid": key_data["user_uuid"],
            "name": key_data["name"],
            "prefix": key_data["prefix"],
        }

    def list_keys_for_user(self, user_uuid: str) -> list[dict]:
        """Retrieve all API keys for a user (without hashes)."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT id, user_uuid, name, prefix, created_at FROM {self.TABLE_NAME} WHERE user_uuid = ? ORDER BY created_at",  # nosec B608
            (user_uuid,)
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_all_keys_with_hashes(self) -> list[dict]:
        """Retrieve all API key records including hashes (for auth lookup)."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT id, user_uuid, name, key_hash, prefix, created_at FROM {self.TABLE_NAME}"  # nosec B608
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_keys_by_prefix(self, prefix: str) -> list[dict]:
        """Retrieve API key records matching a given prefix (includes hashes)."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT id, user_uuid, key_hash, prefix FROM {self.TABLE_NAME} WHERE prefix = ?",  # nosec B608
            (prefix,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_key(self, key_id: str) -> Optional[dict]:
        """Retrieve a single API key record by its ID (includes hash)."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT id, user_uuid, name, key_hash, prefix, created_at FROM {self.TABLE_NAME} WHERE id = ?",  # nosec B608
            (key_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def delete_key(self, key_id: str, user_uuid: str) -> bool:
        """Delete an API key by ID, scoped to the owning user."""
        with self.conn:
            cursor = self.conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE id = ? AND user_uuid = ?",  # nosec B608
                (key_id, user_uuid)
            )
        return cursor.rowcount > 0

    def delete_all_keys_for_user(self, user_uuid: str) -> int:
        """Delete all API keys for a user. Returns the number deleted."""
        with self.conn:
            cursor = self.conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE user_uuid = ?",  # nosec B608
                (user_uuid,)
            )
        return cursor.rowcount

    def close(self) -> None:
        """Close the current thread's database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
