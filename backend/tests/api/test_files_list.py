"""HTTP-level tests for GET /api/files sorting and pagination."""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import get_current_active_user, get_file_db
from api.routes import files as files_routes
from db import FileDB

USER = {"uuid": "user-a", "disabled": False}


@pytest.fixture
def client(monkeypatch, tmp_path):
    # A file database, not ":memory:": FastAPI runs sync routes in worker
    # threads, and FileDB keeps one connection per thread.
    monkeypatch.setattr(FileDB, "DB_PATH", str(tmp_path / "files.db"))
    db = FileDB()

    app = FastAPI()
    app.include_router(files_routes.router, prefix="/api")
    app.dependency_overrides[get_file_db] = lambda: db
    app.dependency_overrides[get_current_active_user] = lambda: USER
    app.state.db = db
    yield TestClient(app)
    db.close()


def _add(db, name, *, size=1, media_type="png", user="user-a"):
    db.insert_file_metadata({
        "id": str(uuid.uuid4()),
        "storage_path": f"/data/uploads/{name}",
        "original_filename": name,
        "media_type": media_type,
        "extension": ".png",
        "size_bytes": size,
        "sha256_checksum": "x",
        "user_id": user,
    })


def _names(resp):
    return [f["original_filename"] for f in resp.json()["files"]]


def test_no_params_returns_everything_in_the_old_order(client):
    for name in ("c.png", "a.png", "b.png"):
        _add(client.app.state.db, name)

    resp = client.get("/api/files")

    assert resp.status_code == 200
    assert _names(resp) == ["c.png", "a.png", "b.png"]
    assert resp.json()["pagination"] == {
        "total_items": 3, "total_pages": 1, "current_page": 1,
        "limit": None, "has_next": False, "has_prev": False,
    }


def test_no_files_is_an_empty_list_with_zero_pages(client):
    resp = client.get("/api/files", params={"limit": 10})

    assert resp.status_code == 200
    assert resp.json()["files"] == []
    assert resp.json()["pagination"]["total_pages"] == 0
    assert resp.json()["pagination"]["has_next"] is False


def test_first_middle_and_last_page(client):
    for i in range(5):
        _add(client.app.state.db, f"f{i}", size=i)
    params = {"limit": 2, "sort": "size", "order": "asc"}

    first = client.get("/api/files", params={**params, "page": 1})
    middle = client.get("/api/files", params={**params, "page": 2})
    last = client.get("/api/files", params={**params, "page": 3})

    assert _names(first) == ["f0", "f1"]
    assert _names(middle) == ["f2", "f3"]
    assert _names(last) == ["f4"]
    assert first.json()["pagination"] == {
        "total_items": 5, "total_pages": 3, "current_page": 1,
        "limit": 2, "has_next": True, "has_prev": False,
    }
    assert middle.json()["pagination"]["has_next"] is True
    assert middle.json()["pagination"]["has_prev"] is True
    assert last.json()["pagination"]["has_next"] is False
    assert last.json()["pagination"]["has_prev"] is True


def test_exact_multiple_of_page_size(client):
    for i in range(4):
        _add(client.app.state.db, f"f{i}")

    resp = client.get("/api/files", params={"limit": 2, "page": 2})

    assert len(resp.json()["files"]) == 2
    assert resp.json()["pagination"]["total_pages"] == 2
    assert resp.json()["pagination"]["has_next"] is False


def test_page_past_the_end_is_empty_not_an_error(client):
    _add(client.app.state.db, "only")

    resp = client.get("/api/files", params={"limit": 5, "page": 9})

    assert resp.status_code == 200
    assert resp.json()["files"] == []
    assert resp.json()["pagination"]["total_items"] == 1
    assert resp.json()["pagination"]["current_page"] == 9
    assert resp.json()["pagination"]["has_next"] is False


def test_only_the_current_users_files_are_listed_and_counted(client):
    db = client.app.state.db
    for i in range(3):
        _add(db, f"mine{i}")
        _add(db, f"theirs{i}", user="user-b")

    resp = client.get("/api/files", params={"limit": 10})

    assert len(resp.json()["files"]) == 3
    assert resp.json()["pagination"]["total_items"] == 3


def test_sort_by_filename_ignores_case(client):
    for name in ("banana.png", "Apple.png", "cherry.png"):
        _add(client.app.state.db, name)

    resp = client.get("/api/files", params={"sort": "filename", "order": "asc"})

    assert _names(resp) == ["Apple.png", "banana.png", "cherry.png"]


def test_each_file_still_carries_compatible_formats(client):
    _add(client.app.state.db, "pic.png", media_type="png")

    resp = client.get("/api/files", params={"limit": 5})

    assert "compatible_formats" in resp.json()["files"][0]


@pytest.mark.parametrize("params", [
    {"limit": 0},
    {"limit": -1},
    {"limit": files_routes.MAX_PAGE_SIZE + 1},
    {"limit": 10, "page": 0},
    {"sort": "storage_path"},
    {"sort": "date; DROP TABLE x"},
    {"order": "sideways"},
])
def test_invalid_parameters_are_rejected(client, params):
    assert client.get("/api/files", params=params).status_code == 422
