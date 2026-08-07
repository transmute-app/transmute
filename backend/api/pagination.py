"""Shared helpers for optional page/page_size list pagination."""

from __future__ import annotations

import math
from typing import Any


def build_pagination_meta(
    *,
    total_items: int,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Build the pagination metadata object recommended by issue #179."""
    total_pages = max(1, math.ceil(total_items / page_size)) if page_size else 1
    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def resolve_pagination(
    page: int | None,
    page_size: int | None,
    *,
    default_page_size: int = 20,
) -> tuple[int, int, int] | None:
    """Return ``(page, page_size, offset)`` when pagination is requested.

    Pagination is opt-in: if both ``page`` and ``page_size`` are omitted, return
    ``None`` so callers keep their existing unpaginated behaviour.
    """
    if page is None and page_size is None:
        return None
    resolved_page = 1 if page is None else page
    resolved_size = default_page_size if page_size is None else page_size
    offset = (resolved_page - 1) * resolved_size
    return resolved_page, resolved_size, offset
