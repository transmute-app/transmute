"""Tests for run_compression_job in the compression service.

Compression is same-format: the output keeps the source's media type and
extension. The service persists the compressed file metadata and a relation
back to the original.
"""
from __future__ import annotations

import errno
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services import compression_service


class _FakeCompressor:
    """Pluggable compressor stub that writes a single pre-defined file."""

    payload: tuple[str, bytes] = ("out.jpg", b"smaller")

    def __init__(self, input_file, output_dir, media_type):
        self.output_dir = Path(output_dir)
        self.media_type = media_type

    def compress(self, overwrite=True, compression_level=None):
        name, data = self._payload
        target = self.output_dir / name
        target.write_bytes(data)
        return [str(target)]


def _make_compressor(payload: tuple[str, bytes]):
    return type(
        "ConfiguredFakeCompressor",
        (_FakeCompressor,),
        {"_payload": payload},
    )


def _source_metadata(upload_dir: Path) -> dict:
    src = upload_dir / f"{uuid4().hex}.jpg"
    src.write_bytes(b"original-larger-bytes")
    return {
        "id": "src-id",
        "user_id": "user-a",
        "media_type": "jpg",
        "extension": ".jpg",
        "size_bytes": src.stat().st_size,
        "original_filename": "photo.jpg",
        "storage_path": str(src),
    }


@pytest.fixture
def fake_dbs():
    compression_db = MagicMock()
    compression_relations_db = MagicMock()
    file_db = MagicMock()
    settings_db = MagicMock()
    settings_db.get_settings.return_value = {"keep_originals": True}
    return file_db, compression_db, compression_relations_db, settings_db


@pytest.fixture
def patched_settings(safe_path_test_settings, monkeypatch):
    monkeypatch.setattr(compression_service, "get_settings", lambda: safe_path_test_settings)
    return safe_path_test_settings


def test_compression_keeps_format_and_extension(patched_settings, fake_dbs):
    file_db, compression_db, compression_relations_db, settings_db = fake_dbs
    src_meta = _source_metadata(patched_settings.upload_dir)
    compressor_cls = _make_compressor(("out.jpg", b"smaller"))

    result = compression_service.run_compression_job(
        source_metadata=src_meta,
        compression_level="balanced",
        compressor_type=compressor_cls,
        user_id="user-a",
        file_db=file_db,
        compression_db=compression_db,
        compression_relations_db=compression_relations_db,
        settings_db=settings_db,
    )

    assert result["media_type"] == "jpg"
    assert result["extension"] == ".jpg"
    assert result["compression_level"] == "balanced"
    out_path = Path(result["storage_path"])
    assert out_path.exists()
    assert out_path.suffix == ".jpg"
    assert out_path.read_bytes() == b"smaller"


def test_compression_persists_metadata_and_relation(patched_settings, fake_dbs):
    file_db, compression_db, compression_relations_db, settings_db = fake_dbs
    src_meta = _source_metadata(patched_settings.upload_dir)
    compressor_cls = _make_compressor(("out.jpg", b"smaller"))

    result = compression_service.run_compression_job(
        source_metadata=src_meta,
        compression_level=None,
        compressor_type=compressor_cls,
        user_id="user-a",
        file_db=file_db,
        compression_db=compression_db,
        compression_relations_db=compression_relations_db,
        settings_db=settings_db,
    )

    compression_db.insert_file_metadata.assert_called_once()
    compression_relations_db.insert_compression_relation.assert_called_once()
    relation = compression_relations_db.insert_compression_relation.call_args.args[0]
    assert relation["original_file_id"] == "src-id"
    assert relation["compressed_file_id"] == result["id"]
    assert relation["user_id"] == "user-a"


def test_compression_resolves_default_level_when_none(patched_settings, fake_dbs):
    file_db, compression_db, compression_relations_db, settings_db = fake_dbs
    src_meta = _source_metadata(patched_settings.upload_dir)
    compressor_cls = _make_compressor(("out.jpg", b"smaller"))

    default_db = MagicMock()
    default_db.get.return_value = {"media_format": "jpeg", "compression_level": "max"}

    result = compression_service.run_compression_job(
        source_metadata=src_meta,
        compression_level=None,
        compressor_type=compressor_cls,
        user_id="user-a",
        file_db=file_db,
        compression_db=compression_db,
        compression_relations_db=compression_relations_db,
        settings_db=settings_db,
        default_compression_levels_db=default_db,
    )

    # The source media type ``jpg`` is normalized to its canonical format
    # ``jpeg`` before resolving the user's stored default.
    default_db.get.assert_called_once_with("user-a", "jpeg")
    assert result["compression_level"] == "max"


def test_compression_deletes_source_when_keep_originals_false(patched_settings, fake_dbs, monkeypatch):
    file_db, compression_db, compression_relations_db, settings_db = fake_dbs
    settings_db.get_settings.return_value = {"keep_originals": False}
    src_meta = _source_metadata(patched_settings.upload_dir)
    compressor_cls = _make_compressor(("out.jpg", b"smaller"))

    mock_delete = MagicMock()
    monkeypatch.setattr(compression_service, "delete_file_and_metadata", mock_delete)

    compression_service.run_compression_job(
        source_metadata=src_meta,
        compression_level=None,
        compressor_type=compressor_cls,
        user_id="user-a",
        file_db=file_db,
        compression_db=compression_db,
        compression_relations_db=compression_relations_db,
        settings_db=settings_db,
    )

    mock_delete.assert_called_once_with(file_id="src-id", file_db=file_db)


def test_compression_falls_back_when_rename_crosses_devices(patched_settings, fake_dbs, monkeypatch):
    file_db, compression_db, compression_relations_db, settings_db = fake_dbs
    src_meta = _source_metadata(patched_settings.upload_dir)
    compressor_cls = _make_compressor(("out.jpg", b"smaller"))
    original_rename = Path.rename

    def fake_rename(self, target):
        if self.parent == patched_settings.tmp_dir:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fake_rename)

    result = compression_service.run_compression_job(
        source_metadata=src_meta,
        compression_level=None,
        compressor_type=compressor_cls,
        user_id="user-a",
        file_db=file_db,
        compression_db=compression_db,
        compression_relations_db=compression_relations_db,
        settings_db=settings_db,
    )

    out_path = Path(result["storage_path"])
    assert out_path.exists()
    assert out_path.read_bytes() == b"smaller"
    assert not (patched_settings.tmp_dir / "out.jpg").exists()


def test_empty_output_raises(patched_settings, fake_dbs):
    file_db, compression_db, compression_relations_db, settings_db = fake_dbs
    src_meta = _source_metadata(patched_settings.upload_dir)

    class _EmptyCompressor:
        def __init__(self, input_file, output_dir, media_type):
            pass

        def compress(self, overwrite=True, compression_level=None):
            return []

    with pytest.raises(compression_service.CompressionFailedError):
        compression_service.run_compression_job(
            source_metadata=src_meta,
            compression_level=None,
            compressor_type=_EmptyCompressor,
            user_id="user-a",
            file_db=file_db,
            compression_db=compression_db,
            compression_relations_db=compression_relations_db,
            settings_db=settings_db,
        )


def test_compressor_exception_raises_compression_failed(patched_settings, fake_dbs):
    file_db, compression_db, compression_relations_db, settings_db = fake_dbs
    src_meta = _source_metadata(patched_settings.upload_dir)

    class _BrokenCompressor:
        def __init__(self, input_file, output_dir, media_type):
            pass

        def compress(self, overwrite=True, compression_level=None):
            raise RuntimeError("encoder exploded")

    with pytest.raises(compression_service.CompressionFailedError):
        compression_service.run_compression_job(
            source_metadata=src_meta,
            compression_level=None,
            compressor_type=_BrokenCompressor,
            user_id="user-a",
            file_db=file_db,
            compression_db=compression_db,
            compression_relations_db=compression_relations_db,
            settings_db=settings_db,
        )
