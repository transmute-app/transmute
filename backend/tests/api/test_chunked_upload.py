import pytest
from fastapi import HTTPException
from api.routes.files import _validate_upload_id


def test_validate_upload_id_accepts_valid_uuid():
    _validate_upload_id("12345678-1234-5678-1234-567812345678")
    _validate_upload_id("00000000-0000-0000-0000-000000000000")
    _validate_upload_id("ffffffff-ffff-ffff-ffff-ffffffffffff")


def test_validate_upload_id_rejects_directory_traversal():
    with pytest.raises(HTTPException) as exc_info:
        _validate_upload_id("../../etc")
    assert exc_info.value.status_code == 400
    assert "Invalid upload_id format" in exc_info.value.detail


def test_validate_upload_id_rejects_path_separators():
    with pytest.raises(HTTPException) as exc_info:
        _validate_upload_id("foo/bar")
    assert exc_info.value.status_code == 400


def test_validate_upload_id_rejects_empty_string():
    with pytest.raises(HTTPException) as exc_info:
        _validate_upload_id("")
    assert exc_info.value.status_code == 400


def test_validate_upload_id_rejects_none():
    with pytest.raises(HTTPException) as exc_info:
        _validate_upload_id(None)
    assert exc_info.value.status_code == 400


def test_validate_upload_id_rejects_arbitrary_strings():
    with pytest.raises(HTTPException) as exc_info:
        _validate_upload_id("not-a-uuid")
    assert exc_info.value.status_code == 400
