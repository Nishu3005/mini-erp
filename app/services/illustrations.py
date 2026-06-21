"""Tiny runtime helper for the per-page footer illustration.

The generator (`tools/illustrations/generate.py`) writes images into
`app/static/illustrations/<page>/`. This helper picks one for a given page key, or returns None
if the folder is empty (the footer then renders nothing).

A deterministic-but-distinct choice per page-load is overkill; we just pick the first file. Pages
are free to vary by passing a different key (e.g. "sales-form" vs "sales-list").
"""
from pathlib import Path
from random import choice

from flask import request, url_for

_ROOT = Path(__file__).resolve().parents[1] / "static" / "illustrations"
_EXT_OK = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# Map blueprint name -> illustration folder. Blueprints not here render no banner.
_BLUEPRINT_TO_PAGE = {
    "dashboard": "dashboard", "sales": "sales", "purchase": "purchase",
    "manufacturing": "manufacturing", "bom": "bom", "product": "product",
    "audit": "audit", "admin": "admin", "profile": "profile",
    "auth": "auth", "landing": "landing",
}


def _current_page_key() -> str | None:
    """Infer the page key from the live request.

    Tries the endpoint's blueprint first (`sales.list_view` → `sales`). The scoped URL dispatcher
    re-invokes a view in-place without updating `request.endpoint` (it stays `scoped.dispatch`),
    so we then fall back to parsing the URL path: `/admin/admin1/sales/...` → `sales`.
    """
    if not request:
        return None
    endpoint = request.endpoint or ""
    bp = endpoint.split(".", 1)[0]
    if bp in _BLUEPRINT_TO_PAGE:
        return _BLUEPRINT_TO_PAGE[bp]
    if endpoint in ("not_found", "forbidden") or bp in ("not_found", "forbidden"):
        return "errors"

    # Path fallback: skip the /<role>/<username>/ prefix if present, then take the next segment.
    _ROLES = {"admin", "sales", "inventory", "manufacturing", "purchase", "owner"}
    parts = [p for p in (request.path or "").split("/") if p]
    if len(parts) >= 2 and parts[0] in _ROLES:
        parts = parts[2:]      # drop role + username
    if not parts:
        return "dashboard"     # scoped home (/<role>/<username>/) goes to the dashboard
    head = parts[0]
    # admin's home is the admin dashboard
    if head == "admin":
        return "admin"
    return _BLUEPRINT_TO_PAGE.get(head)


def page_illustration_url(page: str | None = None) -> str | None:
    """Return a /static URL for ONE image in `static/illustrations/<page>/`, or None if empty.

    If `page` is omitted or falsy, infer it from the current request's blueprint —
    so base.html can just call `{{ page_illustration() }}` without any per-template wiring.
    """
    if not page:
        page = _current_page_key()
    if not page:
        return None
    folder = _ROOT / page
    if not folder.is_dir():
        return None
    files = [p for p in folder.iterdir() if p.suffix.lower() in _EXT_OK]
    if not files:
        return None
    chosen = choice(files)
    return url_for("static", filename=f"illustrations/{page}/{chosen.name}")
