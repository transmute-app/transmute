import sqlite3
import threading
from typing import Optional
from core import get_settings, validate_sql_identifier, migrate_table_columns, assign_orphaned_rows_to_admin

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table 
name is validated and locked after initialization, and the values are 
parameterized to prevent SQL injection.
'''


class FileDB:
    """Database class for managing file metadata.

    Handles storage and retrieval of metadata for uploaded files,
    including file identifiers, storage paths, media types, and checksums.

    Attributes:
        settings: Application settings instance.
        DB_PATH: Path to the SQLite database file.
        _TABLE_NAME: Name of the database table for file metadata.
        conn: Active SQLite database connection.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = settings.file_table_name

    @property
    def TABLE_NAME(self) -> str:
        """str: The validated, immutable table name."""
        return self._table_name

    def __init__(self) -> None:
        """Initialize FileDB, validate the table name, and create tables."""
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
        """Create the file metadata table if it does not already exist."""
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                id TEXT PRIMARY KEY UNIQUE,
                storage_path TEXT,
                original_filename TEXT,
                media_type TEXT,
                extension TEXT,
                size_bytes INTEGER,
                sha256_checksum TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)  # nosec B608

        # Ensure every expected column exists (handles older DB schemas)
        migrate_table_columns(self.conn, self.TABLE_NAME, {
            "storage_path":     "TEXT",
            "original_filename": "TEXT",
            "media_type":       "TEXT",
            "extension":        "TEXT",
            "size_bytes":       "INTEGER",
            "sha256_checksum":  "TEXT",
            "created_at":       "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "user_id":          "TEXT",
        })

        # Assign pre-auth orphaned rows to the first admin
        assign_orphaned_rows_to_admin(self.conn, self.TABLE_NAME)

    def insert_file_metadata(self, metadata: dict) -> None:
        """Insert a new file metadata record into the database.

        Args:
            metadata: A dictionary containing the following required keys:
                id (str): Unique identifier for the file.
                storage_path (str): Path where the file is stored.
                original_filename (str): Original name of the uploaded file.
                media_type (str): MIME type of the file.
                extension (str): File extension.
                size_bytes (int): Size of the file in bytes.
                sha256_checksum (str): SHA-256 checksum of the file.

        Raises:
            ValueError: If the metadata dictionary contains missing or extra fields.
        """
        required_fields = [
            'id', 
            'storage_path',
            'original_filename',
            'media_type',
            'extension',
            'size_bytes',
            'sha256_checksum',
            'user_id'
        ]
        if metadata.keys() != set(required_fields):
            raise ValueError(f"Metadata must contain the following fields: {required_fields}. Missing or extra fields: {set(required_fields).symmetric_difference(metadata.keys())}")
        with self.conn:
            self.conn.execute(f"INSERT INTO {self.TABLE_NAME} (id, storage_path, original_filename, media_type, extension, size_bytes, sha256_checksum, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (  # nosec B608
                metadata['id'],
                metadata['storage_path'],
                metadata['original_filename'],
                metadata['media_type'],
                metadata['extension'],
                metadata['size_bytes'],
                metadata['sha256_checksum'],
                metadata['user_id'],
            ))  # nosec B608

    def get_file_metadata(self, file_id: str) -> Optional[dict]:
        """Retrieve metadata for a specific file by its ID.

        Args:
            file_id: The unique identifier of the file.

        Returns:
            A dictionary containing the file metadata, or None if no file
            with the given ID exists.
        """
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(f"SELECT * FROM {self.TABLE_NAME} WHERE id = ?", (file_id,))  # nosec B608
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def list_files(self, user_id: str | None = None) -> list[dict]:
        """Retrieve metadata for files, optionally filtered by user."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        if user_id is not None:
            cursor.execute(f"SELECT * FROM {self.TABLE_NAME} WHERE user_id = ?", (user_id,))  # nosec B608
        else:
            cursor.execute(f"SELECT * FROM {self.TABLE_NAME}")  # nosec B608
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def delete_file_metadata(self, file_id: str) -> None:
        """Delete the metadata record for a specific file.

        Args:
            file_id: The unique identifier of the file whose metadata
                should be deleted.
        """
        with self.conn:
            self.conn.execute(f"DELETE FROM {self.TABLE_NAME} WHERE id = ?", (file_id,))  # nosec B608

    def close(self) -> None:
        """Close the current thread's database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
