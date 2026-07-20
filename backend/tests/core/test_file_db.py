import pytest

from db import FileDB


@pytest.fixture
def file_db(monkeypatch):
    monkeypatch.setattr(FileDB, "DB_PATH", ":memory:")
    db = FileDB()
    try:
        yield db
    finally:
        db.close()


def _metadata(file_id: str, user_id: str) -> dict:
    return {
        "id": file_id,
        "storage_path": f"/tmp/{file_id}.txt",
        "original_filename": f"{file_id}.txt",
        "media_type": "txt",
        "extension": ".txt",
        "size_bytes": 10,
        "sha256_checksum": file_id,
        "user_id": user_id,
    }


def test_list_files_paginates_newest_first_and_filters_by_user(file_db):
    file_db.insert_file_metadata(_metadata("first", "user-a"))
    file_db.insert_file_metadata(_metadata("second", "user-a"))
    file_db.insert_file_metadata(_metadata("other", "user-b"))
    file_db.insert_file_metadata(_metadata("third", "user-a"))

    first_page = file_db.list_files(user_id="user-a", limit=2, offset=0)
    second_page = file_db.list_files(user_id="user-a", limit=2, offset=2)

    assert [item["id"] for item in first_page] == ["third", "second"]
    assert [item["id"] for item in second_page] == ["first"]
    assert file_db.count_files(user_id="user-a") == 3
    assert file_db.count_files(user_id="user-b") == 1
    assert file_db.count_files() == 4
