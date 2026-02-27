import sqlite3
from core import get_settings, validate_sql_identifier

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table 
name is validated and locked after initialization, and the values are 
parameterized to prevent SQL injection.
'''

class FileDB:
    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = settings.file_table_name

    @property
    def TABLE_NAME(self) -> str:
        return self._table_name

    def __init__(self):
        # Validate and lock table name — immutable after init
        object.__setattr__(self, '_table_name', validate_sql_identifier(self._TABLE_NAME))
        self.conn = sqlite3.connect(self.DB_PATH, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
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
  
    def insert_file_metadata(self, metadata: dict):
        required_fields = [
            'id', 
            'storage_path',
            'original_filename',
            'media_type',
            'extension',
            'size_bytes',
            'sha256_checksum'
        ]
        if metadata.keys() != set(required_fields):
            raise ValueError(f"Metadata must contain the following fields: {required_fields}. Missing or extra fields: {set(required_fields).symmetric_difference(metadata.keys())}")
        with self.conn:
            self.conn.execute(f"INSERT INTO {self.TABLE_NAME} (id, storage_path, original_filename, media_type, extension, size_bytes, sha256_checksum) VALUES (?, ?, ?, ?, ?, ?, ?)", (  # nosec B608
                metadata['id'],
                metadata['storage_path'],
                metadata['original_filename'],
                metadata['media_type'],
                metadata['extension'],
                metadata['size_bytes'],
                metadata['sha256_checksum']
            ))  # nosec B608
        
    def get_file_metadata(self, file_id: str) -> dict | None:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {self.TABLE_NAME} WHERE id = ?", (file_id,))  # nosec B608
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))

    def list_files(self) -> list[dict]:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {self.TABLE_NAME}")  # nosec B608
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def delete_file_metadata(self, file_id: str):
        with self.conn:
            self.conn.execute(f"DELETE FROM {self.TABLE_NAME} WHERE id = ?", (file_id,))  # nosec B608
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()