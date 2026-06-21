"""Tiny pagination helper for list views.

Usage:
    page = request.args.get('page', type=int, default=1)
    rows, meta = paginate(query, page, per_page=25)
    # meta = {'page': 1, 'pages': 12, 'total': 287, 'has_prev': False, 'has_next': True}
"""
from math import ceil


PAGE_SIZE = 25


def paginate(q, page=1, per_page=PAGE_SIZE):
    """Return (rows_on_this_page, meta). Caller passes a SQLAlchemy query."""
    total = q.count()
    pages = max(1, ceil(total / per_page))
    page = max(1, min(page, pages))
    rows = q.offset((page - 1) * per_page).limit(per_page).all()
    return rows, {
        "page": page, "pages": pages, "total": total, "per_page": per_page,
        "has_prev": page > 1, "has_next": page < pages,
        "prev_page": page - 1, "next_page": page + 1,
        "from_row": (page - 1) * per_page + 1 if total else 0,
        "to_row": min(page * per_page, total),
    }
