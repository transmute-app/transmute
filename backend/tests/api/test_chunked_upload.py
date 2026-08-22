import json
import uuid
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from fastapi import HTTPException

from api.routes import files as files_module
from api.routes.files import (
    complete_chunked_upload,
    init_chunked_upload,
)
from api.schemas import ChunkedUploadCompleteRequest, ChunkedUploadInitRequest


def _setup_session(tmp_path, monkeypatch, total_size, total_chunks, chunk_data):
    chunks_dir = tmp_path / "chunks"
    upload_dir = tmp_path / "uploads"
    chunks_dir.mkdir()
    upload_dir.mkdir()

    monkeypatch.setattr(files_module, "CHUNKS_DIR", chunks_dir)
    monkeypatch.setattr(files_module, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(files_module, "detect_media_type", lambda _: "mp4")
    monkeypatch.setattr(
        files_module.converter_registry,
        "get_compatible_formats_and_qualities",
        lambda _: [("mp3", "128k")],
    )

    upload_id = str(uuid.uuid4())
    session_dir = chunks_dir / upload_id
    session_dir.mkdir()

    meta = {
        "upload_id": upload_id,
        "filename": "test.mp4",
        "total_size": total_size,
        "total_chunks": total_chunks,
        "user_id": "user-1",
    }
    (session_dir / "meta.json").write_text(json.dumps(meta))

    for i, data in enumerate(chunk_data):
        (session_dir / f"{i}.part").write_bytes(data)

    return upload_id, upload_dir


def test_rejects_size_mismatch(tmp_path, monkeypatch):
    chunk_data = [b"a" * 30, b"b" * 20]
    upload_id, upload_dir = _setup_session(
        tmp_path, monkeypatch, total_size=100, total_chunks=2, chunk_data=chunk_data
    )

    file_db = MagicMock()
    user = {"uuid": "user-1"}
    request = ChunkedUploadCompleteRequest(upload_id=upload_id)

    with pytest.raises(HTTPException) as exc_info:
        complete_chunked_upload(request, file_db=file_db, current_user=user)

    assert exc_info.value.status_code == 400
    assert "Size mismatch" in exc_info.value.detail
    assert "100" in exc_info.value.detail
    assert "50" in exc_info.value.detail

    file_db.insert_file_metadata.assert_not_called()

    assert not any(upload_dir.iterdir()), "Partial file should have been cleaned up"


def test_succeeds_when_size_matches(tmp_path, monkeypatch):
    chunk_data = [b"a" * 30, b"b" * 20]
    upload_id, upload_dir = _setup_session(
        tmp_path, monkeypatch, total_size=50, total_chunks=2, chunk_data=chunk_data
    )

    file_db = MagicMock()
    user = {"uuid": "user-1"}
    request = ChunkedUploadCompleteRequest(upload_id=upload_id)

    result = complete_chunked_upload(request, file_db=file_db, current_user=user)

    assert result["message"] == "File uploaded successfully"
    file_db.insert_file_metadata.assert_called_once()
    stored = file_db.insert_file_metadata.call_args[0][0]
    assert stored["size_bytes"] == 50
    assert stored["original_filename"] == "test.mp4"
    assert stored["user_id"] == "user-1"

    assembled = Path(stored["storage_path"])
    assert assembled.exists()
    assert assembled.read_bytes() == b"a" * 30 + b"b" * 20


def test_rejects_invalid_upload_id(tmp_path, monkeypatch):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    monkeypatch.setattr(files_module, "CHUNKS_DIR", chunks_dir)

    file_db = MagicMock()
    user = {"uuid": "user-1"}
    request = ChunkedUploadCompleteRequest(upload_id="../etc/passwd")

    with pytest.raises(HTTPException) as exc_info:
        complete_chunked_upload(request, file_db=file_db, current_user=user)

    assert exc_info.value.status_code == 400
    file_db.insert_file_metadata.assert_not_called()


def test_rejects_missing_chunk(tmp_path, monkeypatch):
    chunk_data = [b"a" * 30]
    upload_id, _ = _setup_session(
        tmp_path, monkeypatch, total_size=50, total_chunks=2, chunk_data=chunk_data
    )

    file_db = MagicMock()
    user = {"uuid": "user-1"}
    request = ChunkedUploadCompleteRequest(upload_id=upload_id)

    with pytest.raises(HTTPException) as exc_info:
        complete_chunked_upload(request, file_db=file_db, current_user=user)

    assert exc_info.value.status_code == 400
    assert "Missing chunk 1" in exc_info.value.detail
    file_db.insert_file_metadata.assert_not_called()


def test_rejects_user_mismatch(tmp_path, monkeypatch):
    chunk_data = [b"a" * 30, b"b" * 20]
    upload_id, _ = _setup_session(
        tmp_path, monkeypatch, total_size=50, total_chunks=2, chunk_data=chunk_data
    )

    file_db = MagicMock()
    user = {"uuid": "different-user"}
    request = ChunkedUploadCompleteRequest(upload_id=upload_id)

    with pytest.raises(HTTPException) as exc_info:
        complete_chunked_upload(request, file_db=file_db, current_user=user)

    assert exc_info.value.status_code == 404
    file_db.insert_file_metadata.assert_not_called()


def test_rejects_unsupported_format(tmp_path, monkeypatch):
    chunk_data = [b"a" * 30, b"b" * 20]
    upload_id, upload_dir = _setup_session(
        tmp_path, monkeypatch, total_size=50, total_chunks=2, chunk_data=chunk_data
    )

    monkeypatch.setattr(
        files_module.converter_registry,
        "get_compatible_formats_and_qualities",
        lambda _: [],
    )

    file_db = MagicMock()
    user = {"uuid": "user-1"}
    request = ChunkedUploadCompleteRequest(upload_id=upload_id)

    with pytest.raises(HTTPException) as exc_info:
        complete_chunked_upload(request, file_db=file_db, current_user=user)

    assert exc_info.value.status_code == 422
    file_db.insert_file_metadata.assert_not_called()

    assert not any(upload_dir.iterdir()), "Assembled file should have been cleaned up"


def test_init_creates_session(tmp_path, monkeypatch):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    monkeypatch.setattr(files_module, "CHUNKS_DIR", chunks_dir)

    user = {"uuid": "user-1"}
    request = ChunkedUploadInitRequest(
        filename="big.mp4", total_size=1000, total_chunks=3
    )

    result = init_chunked_upload(request, current_user=user)

    upload_id = result["upload_id"]
    uuid.UUID(upload_id)

    session_dir = chunks_dir / upload_id
    assert session_dir.is_dir()

    meta = json.loads((session_dir / "meta.json").read_text())
    assert meta["filename"] == "big.mp4"
    assert meta["total_size"] == 1000
    assert meta["total_chunks"] == 3
    assert meta["user_id"] == "user-1"
