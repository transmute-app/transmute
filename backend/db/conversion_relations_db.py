import sqlite3
from core import get_settings

class ConversionRelationsDB:
    settings = get_settings()
    DB_PATH = settings.db_path
    TABLE_NAME = settings.conversion_relations_table_name

    def __init__(self):
        self.conn = sqlite3.connect(self.DB_PATH, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        with self.conn:
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

    def insert_conversion_relation(self, metadata: dict):
        required_fields = [
            'original_file_id', 
            'converted_file_id',
            'original_filename',
            'original_media_type',
            'original_extension',
            'original_size_bytes'
        ]
        if metadata.keys() != set(required_fields):
            raise ValueError(f"Metadata must contain the following fields: {required_fields}. Missing or extra fields: {set(required_fields).symmetric_difference(metadata.keys())}")
        with self.conn:
            self.conn.execute(f"""
                INSERT INTO {self.TABLE_NAME} (
                original_file_id, converted_file_id, original_filename, 
                original_media_type, original_extension, original_size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                metadata['original_file_id'],
                metadata['converted_file_id'],
                metadata['original_filename'],
                metadata['original_media_type'],
                metadata['original_extension'],
                metadata['original_size_bytes']
            ))
    
    def get_conversion_from_file(self, original_file_id: str) -> dict | None:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {self.TABLE_NAME} WHERE original_file_id = ?", (original_file_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return row[1]
    
    def get_original_from_conversion(self, converted_file_id: str) -> dict | None:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {self.TABLE_NAME} WHERE converted_file_id = ?", (converted_file_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return row[0]
    
    def delete_relation_by_original(self, original_file_id: str):
        with self.conn:
            self.conn.execute(f"DELETE FROM {self.TABLE_NAME} WHERE original_file_id = ?", (original_file_id,))
    
    def delete_relation_by_converted(self, converted_file_id: str):
        with self.conn:
            self.conn.execute(f"DELETE FROM {self.TABLE_NAME} WHERE converted_file_id = ?", (converted_file_id,))
    
    def list_relations(self) -> list[dict]:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {self.TABLE_NAME}")
        rows = cursor.fetchall()
        return [
            {
                'original_file_id': row[0],
                'converted_file_id': row[1],
                'original_filename': row[2],
                'original_media_type': row[3],
                'original_extension': row[4],
                'original_size_bytes': row[5]
            }
            for row in rows
        ]
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()