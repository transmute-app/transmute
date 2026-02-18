import sqlite3
from core import get_settings

class FileDB:
  settings = get_settings()
  DB_PATH = settings.db_path
  TABLE_NAME = settings.file_table_name

  def __init__(self):
    self.conn = sqlite3.connect(self.DB_PATH)
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
          stored_as TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
      """)
  
  def insert_file_metadata(self, metadata: dict):
    required_fields = [
        'id', 
        'storage_path',
        'original_filename',
        'media_type',
        'extension',
        'size_bytes',
        'sha256_checksum',
        'stored_as'
    ]
    if metadata.keys() != set(required_fields):
      raise ValueError(f"Metadata must contain the following fields: {required_fields}. Missing or extra fields: {set(required_fields).symmetric_difference(metadata.keys())}")
    with self.conn:
      self.conn.execute(f"""
        INSERT INTO {self.TABLE_NAME} (
          id, storage_path, original_filename, media_type, extension, size_bytes, sha256_checksum, stored_as
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      """, (
        metadata['id'],
        metadata['storage_path'],
        metadata['original_filename'],
        metadata['media_type'],
        metadata['extension'],
        metadata['size_bytes'],
        metadata['sha256_checksum'],
        metadata['stored_as']
      ))