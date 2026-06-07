from db import CompressionDB


def test_compression_db_initializes_compression_level_column(monkeypatch):
    monkeypatch.setattr(CompressionDB, 'DB_PATH', ':memory:')

    db = CompressionDB()
    try:
        columns = db.conn.execute(f"PRAGMA table_info({db.TABLE_NAME})").fetchall()
        column_names = {column[1] for column in columns}

        assert 'compression_level' in column_names
    finally:
        db.close()
