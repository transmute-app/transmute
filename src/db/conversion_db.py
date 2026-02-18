import sqlite3
from core import get_settings
from .file_db import FileDB

class ConversionDB(FileDB):
    settings = get_settings()
    DB_PATH = settings.db_path
    TABLE_NAME = settings.conversion_table_name

    def __init__(self):
        super().__init__()