from core.pagination import build_pagination


def test_build_pagination_for_middle_page():
    assert build_pagination(total_items=45, page=2, page_size=20) == {
        "total_items": 45,
        "total_pages": 3,
        "current_page": 2,
        "page_size": 20,
        "has_next": True,
        "has_prev": True,
    }


def test_build_pagination_for_empty_result():
    assert build_pagination(total_items=0, page=1, page_size=20) == {
        "total_items": 0,
        "total_pages": 0,
        "current_page": 1,
        "page_size": 20,
        "has_next": False,
        "has_prev": False,
    }
