"""Shared helpers for paginated list endpoints."""
import math


def build_pagination(total_items: int, page: int, limit: int | None) -> dict:
    """Build the ``pagination`` block returned alongside a page of results.

    ``limit=None`` means the caller asked for everything in one go, which is
    reported as a single page.

    A ``page`` past the end is not an error: the endpoint returns an empty list
    and this block, so a client that was on page 3 when items were deleted can
    see that there are fewer pages now and step back.
    """
    if limit is None:
        total_pages = 1 if total_items > 0 else 0
    else:
        total_pages = math.ceil(total_items / limit)
    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page,
        "limit": limit,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }
