from math import ceil


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def build_pagination(total_items: int, page: int, page_size: int) -> dict:
    """Build consistent pagination metadata for list endpoints."""
    total_pages = ceil(total_items / page_size) if total_items else 0
    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "has_next": page < total_pages,
        "has_prev": page > 1 and total_pages > 0,
    }
