import sqlite3
import threading
from typing import Optional
from core import get_settings, validate_sql_identifier, migrate_table_columns, assign_orphaned_rows_to_admin

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table 
name is validated and locked after initialization, and the values are 
parameterized to prevent SQL injection.
'''


class ConversionRelationsDB:
    """Database class for managing relationships between original and converted files.

    Stores and retrieves mappings between original uploaded files and their
    converted counterparts, along with key metadata from the original file.

    Attributes:
        settings: Application settings instance.
        DB_PATH: Path to the SQLite database file.
        _TABLE_NAME: Name of the database table for conversion relations.
        conn: Active SQLite database connection.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = settings.conversion_relations_table_name

    @property
    def TABLE_NAME(self) -> str:
        """str: The validated, immutable table name."""
        return self._table_name

    def __init__(self) -> None:
        """Initialize ConversionRelationsDB, validate the table name, and create tables."""
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
        """Create the conversion relations table if it does not already exist."""
        with self.conn:
            # nosec B608
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                original_file_id TEXT,
                converted_file_id TEXT,
                original_filename TEXT,
                original_media_type TEXT,
                original_extension TEXT,
                original_size_bytes INTEGER
                )
            """)

        # Ensure every expected column exists (handles older DB schemas)
        migrate_table_columns(self.conn, self.TABLE_NAME, {
            "original_file_id":   "TEXT",
            "converted_file_id":  "TEXT",
            "original_filename":  "TEXT",
            "original_media_type": "TEXT",
            "original_extension": "TEXT",
            "original_size_bytes": "INTEGER",
            "user_id":            "TEXT",
        })

        # Assign pre-auth orphaned rows to the first admin
        assign_orphaned_rows_to_admin(self.conn, self.TABLE_NAME)

    def insert_conversion_relation(self, metadata: dict) -> None:
        """Insert a new conversion relation record into the database.

        Args:
            metadata: A dictionary containing the following required keys:
                original_file_id (str): ID of the original file.
                converted_file_id (str): ID of the converted file.
                original_filename (str): Original name of the uploaded file.
                original_media_type (str): MIME type of the original file.
                original_extension (str): File extension of the original file.
                original_size_bytes (int): Size of the original file in bytes.

        Raises:
            ValueError: If the metadata dictionary contains missing or extra fields.
        """
        required_fields = [
            'original_file_id', 
            'converted_file_id',
            'original_filename',
            'original_media_type',
            'original_extension',
            'original_size_bytes',
            'user_id'
        ]
        if metadata.keys() != set(required_fields):
            raise ValueError(f"Metadata must contain the following fields: {required_fields}. Missing or extra fields: {set(required_fields).symmetric_difference(metadata.keys())}")
        with self.conn:
            # nosec B608
            self.conn.execute(f"INSERT INTO {self.TABLE_NAME} (original_file_id, converted_file_id, original_filename, original_media_type, original_extension, original_size_bytes, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)", (  # nosec B608
                metadata['original_file_id'],
                metadata['converted_file_id'],
                metadata['original_filename'],
                metadata['original_media_type'],
                metadata['original_extension'],
                metadata['original_size_bytes'],
                metadata['user_id'],
            ))

    def get_conversion_from_file(self, original_file_id: str) -> Optional[str]:
        """Retrieve the converted file ID associated with an original file.

        Args:
            original_file_id: The unique identifier of the original file.

        Returns:
            The converted file ID as a string, or None if no relation exists
            for the given original file ID.
        """
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(f"SELECT * FROM {self.TABLE_NAME} WHERE original_file_id = ?", (original_file_id,))  # nosec B608
        row = cursor.fetchone()
        if row is None:
            return None
        return row['converted_file_id']

    def get_original_from_conversion(self, converted_file_id: str) -> Optional[str]:
        """Retrieve the original file ID associated with a converted file.

        Args:
            converted_file_id: The unique identifier of the converted file.

        Returns:
            The original file ID as a string, or None if no relation exists
            for the given converted file ID.
        """
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(f"SELECT * FROM {self.TABLE_NAME} WHERE converted_file_id = ?", (converted_file_id,))  # nosec B608
        row = cursor.fetchone()
        if row is None:
            return None
        return row['original_file_id']

    def delete_relation_by_original(self, original_file_id: str) -> None:
        """Delete all conversion relations associated with an original file.

        Args:
            original_file_id: The unique identifier of the original file
                whose relations should be deleted.
        """
        with self.conn:
            self.conn.execute(f"DELETE FROM {self.TABLE_NAME} WHERE original_file_id = ?", (original_file_id,))  # nosec B608

    def delete_relation_by_converted(self, converted_file_id: str) -> None:
        """Delete all conversion relations associated with a converted file.

        Args:
            converted_file_id: The unique identifier of the converted file
                whose relations should be deleted.
        """
        with self.conn:
            self.conn.execute(f"DELETE FROM {self.TABLE_NAME} WHERE converted_file_id = ?", (converted_file_id,))  # nosec B608

    def list_relations(self, user_id: str | None = None) -> list[dict]:
        """Retrieve conversion relations, optionally filtered by user."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        if user_id is not None:
            cursor.execute(f"SELECT * FROM {self.TABLE_NAME} WHERE user_id = ?", (user_id,))  # nosec B608
        else:
            cursor.execute(f"SELECT * FROM {self.TABLE_NAME}")  # nosec B608
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        """Close the current thread's database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
