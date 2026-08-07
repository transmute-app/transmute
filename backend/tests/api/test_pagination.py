"""Unit tests for optional list pagination helpers."""

from api.pagination import build_pagination_meta, resolve_pagination


def test_resolve_pagination_omitted_keeps_legacy_behaviour():
    assert resolve_pagination(None, None) is None


def test_resolve_pagination_defaults_missing_fields():
    assert resolve_pagination(2, None) == (2, 20, 20)
    assert resolve_pagination(None, 10) == (1, 10, 0)
    assert resolve_pagination(3, 5) == (3, 5, 10)


def test_build_pagination_meta_flags():
    meta = build_pagination_meta(total_items=25, page=2, page_size=10)
    assert meta == {
        "total_items": 25,
        "total_pages": 3,
        "current_page": 2,
        "page_size": 10,
        "has_next": True,
        "has_prev": True,
    }


def test_build_pagination_meta_empty_collection():
    meta = build_pagination_meta(total_items=0, page=1, page_size=20)
    assert meta["total_pages"] == 1
    assert meta["has_next"] is False
    assert meta["has_prev"] is False
