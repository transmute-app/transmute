from core import get_settings
from .file_db import FileDB


class ConversionDB(FileDB):
    """Database class for managing converted file metadata.

    Extends FileDB to store metadata for files that are the result of
    a conversion operation. Uses a separate table from FileDB but shares
    the same schema and interface.

    Attributes:
        settings: Application settings instance.
        DB_PATH: Path to the SQLite database file.
        _TABLE_NAME: Name of the database table for conversion file metadata.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = settings.conversion_table_name

    def __init__(self) -> None:
        """Initialize ConversionDB and create the conversions table."""
        super().__init__()
