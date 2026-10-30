"""Tests for FileDB sorting, paging and counting used by GET /api/files."""
import uuid

import pytest

from db import FileDB
from db.file_db import FILE_SORT_COLUMNS

USER = "user-a"
OTHER = "user-b"


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(FileDB, "DB_PATH", ":memory:")
    database = FileDB()
    yield database
    database.close()


def _add(db, name, *, size=1, media_type="png", user=USER, created_at=None):
    file_id = str(uuid.uuid4())
    db.insert_file_metadata({
        "id": file_id,
        "storage_path": f"/data/uploads/{file_id}",
        "original_filename": name,
        "media_type": media_type,
        "extension": ".bin",
        "size_bytes": size,
        "sha256_checksum": "x",
        "user_id": user,
    })
    if created_at is not None:
        with db.conn:
            db.conn.execute(
                f"UPDATE {db.TABLE_NAME} SET created_at = ? WHERE id = ?", (created_at, file_id)
            )
    return file_id


def _names(rows):
    return [r["original_filename"] for r in rows]


class TestUnchangedBehaviour:
    """With no new arguments the method must behave exactly as it did before."""

    def test_returns_every_row_in_insertion_order(self, db):
        for name in ("c.png", "a.png", "b.png"):
            _add(db, name)
        assert _names(db.list_files(user_id=USER)) == ["c.png", "a.png", "b.png"]

    def test_no_user_returns_all_users(self, db):
        _add(db, "mine.png")
        _add(db, "theirs.png", user=OTHER)
        assert len(db.list_files()) == 2


class TestSorting:
    def test_filename_is_case_insensitive(self, db):
        """The table used to sort with localeCompare, which ignores case."""
        for name in ("banana.png", "Apple.png", "cherry.png"):
            _add(db, name)
        rows = db.list_files(user_id=USER, sort_by="filename", order="asc")
        assert _names(rows) == ["Apple.png", "banana.png", "cherry.png"]

    def test_size_descending(self, db):
        _add(db, "small", size=10)
        _add(db, "big", size=3000)
        _add(db, "mid", size=200)
        rows = db.list_files(user_id=USER, sort_by="size", order="desc")
        assert _names(rows) == ["big", "mid", "small"]

    def test_type_ascending(self, db):
        _add(db, "v", media_type="mp4")
        _add(db, "i", media_type="jpg")
        _add(db, "d", media_type="docx")
        rows = db.list_files(user_id=USER, sort_by="type", order="asc")
        assert [r["media_type"] for r in rows] == ["docx", "jpg", "mp4"]

    def test_date_newest_first(self, db):
        _add(db, "old", created_at="2026-01-01 10:00:00")
        _add(db, "new", created_at="2026-03-01 10:00:00")
        _add(db, "mid", created_at="2026-02-01 10:00:00")
        rows = db.list_files(user_id=USER, sort_by="date", order="desc")
        assert _names(rows) == ["new", "mid", "old"]

    def test_uploads_in_the_same_second_still_sort_newest_first(self, db):
        """created_at has one-second resolution, so a burst of uploads ties on it.

        The tiebreaker must follow the sort direction, otherwise "newest first"
        would show the earliest of those uploads on top.
        """
        for name in ("first", "second", "third"):
            _add(db, name)  # all get the same CURRENT_TIMESTAMP
        assert _names(db.list_files(user_id=USER, sort_by="date", order="desc")) == ["third", "second", "first"]
        assert _names(db.list_files(user_id=USER, sort_by="date", order="asc")) == ["first", "second", "third"]

    def test_limit_alone_defaults_to_newest_first(self, db):
        _add(db, "old", created_at="2026-01-01 10:00:00")
        _add(db, "new", created_at="2026-03-01 10:00:00")
        assert _names(db.list_files(user_id=USER, limit=10)) == ["new", "old"]


class TestPaging:
    def test_limit_and_offset_slice_the_sorted_list(self, db):
        for i in range(7):
            _add(db, f"f{i}", size=i)
        page2 = db.list_files(user_id=USER, sort_by="size", order="asc", limit=3, offset=3)
        assert _names(page2) == ["f3", "f4", "f5"]

    def test_last_page_is_short(self, db):
        for i in range(7):
            _add(db, f"f{i}", size=i)
        last = db.list_files(user_id=USER, sort_by="size", order="asc", limit=3, offset=6)
        assert _names(last) == ["f6"]

    def test_offset_past_the_end_is_empty(self, db):
        _add(db, "only")
        assert db.list_files(user_id=USER, limit=5, offset=50) == []

    @pytest.mark.parametrize("sort_by", sorted(FILE_SORT_COLUMNS))
    def test_pages_never_repeat_or_skip_rows_even_with_ties(self, db, sort_by):
        """Every row shares created_at, size and type, so ties are everywhere.

        Paging must cover each row exactly once. Note this guards the overall
        property; SQLite happens to order tied rows stably on a small table, so
        the tiebreaker itself is pinned by
        test_uploads_in_the_same_second_still_sort_newest_first.
        """
        expected = {_add(db, "same.png", size=5, media_type="png") for _ in range(11)}
        seen: list[str] = []
        for offset in range(0, 11, 4):
            page = db.list_files(user_id=USER, sort_by=sort_by, order="asc", limit=4, offset=offset)
            seen.extend(r["id"] for r in page)
        assert len(seen) == 11
        assert set(seen) == expected

    def test_tied_rows_have_a_stable_order_across_calls(self, db):
        for _ in range(6):
            _add(db, "same.png", size=5)
        first = [r["id"] for r in db.list_files(user_id=USER, sort_by="size", order="asc", limit=6)]
        second = [r["id"] for r in db.list_files(user_id=USER, sort_by="size", order="asc", limit=6)]
        assert first == second

    def test_paging_only_sees_the_users_own_files(self, db):
        for i in range(3):
            _add(db, f"mine{i}")
            _add(db, f"theirs{i}", user=OTHER)
        rows = db.list_files(user_id=USER, limit=10)
        assert len(rows) == 3
        assert all(r["user_id"] == USER for r in rows)


class TestCount:
    def test_counts_only_the_users_files(self, db):
        _add(db, "a")
        _add(db, "b")
        _add(db, "c", user=OTHER)
        assert db.count_files(user_id=USER) == 2
        assert db.count_files(user_id=OTHER) == 1

    def test_counts_all_without_a_user(self, db):
        _add(db, "a")
        _add(db, "c", user=OTHER)
        assert db.count_files() == 2

    def test_empty_is_zero(self, db):
        assert db.count_files(user_id=USER) == 0


class TestRejectsBadInput:
    def test_unknown_sort_key(self, db):
        with pytest.raises(ValueError):
            db.list_files(user_id=USER, sort_by="storage_path")

    def test_sql_in_sort_key_never_reaches_the_query(self, db):
        _add(db, "a")
        with pytest.raises(ValueError):
            db.list_files(user_id=USER, sort_by="date; DROP TABLE FILES_METADATA")
        assert db.count_files(user_id=USER) == 1

    def test_bad_order(self, db):
        with pytest.raises(ValueError):
            db.list_files(user_id=USER, sort_by="date", order="sideways")
