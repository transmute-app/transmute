from core import get_settings, migrate_table_columns
from .file_db import FileDB


class CompressionDB(FileDB):
    """Database class for managing compressed file metadata.

    Extends FileDB to store metadata for files that are the result of a
    compression operation. Uses a separate table from FileDB but shares the
    same schema and interface, with an additional compression_level column.

    Attributes:
        settings: Application settings instance.
        DB_PATH: Path to the SQLite database file.
        _TABLE_NAME: Name of the database table for compression file metadata.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = settings.compression_table_name

    def __init__(self) -> None:
        """Initialize CompressionDB and create the compressions table."""
        super().__init__()
        self._ensure_compression_level_column()

    def _ensure_compression_level_column(self) -> None:
        """Ensure the compression metadata table has the optional compression_level column."""
        migrate_table_columns(self.conn, self.TABLE_NAME, {
            "compression_level": "TEXT",
        })

    def create_tables(self) -> None:
        """Create the compression metadata table with the compression_level column."""
        super().create_tables()
        self._ensure_compression_level_column()

    def insert_file_metadata(self, metadata: dict) -> None:
        """Insert a new compression file metadata record, including optional compression_level."""
        compression_level = metadata.pop('compression_level', None)
        super().insert_file_metadata(metadata)
        if compression_level is not None:
            with self.conn:
                self.conn.execute(
                    f"UPDATE {self.TABLE_NAME} SET compression_level = ? WHERE id = ?",  # nosec B608
                    (compression_level, metadata['id']),
                )
