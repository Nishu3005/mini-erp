"""Role-scoped URL scheme: /<role>/<username>/<rest...>

Per spec/rbac-redesign.md §4:
  - <role>+<username> in the path are DISPLAY-ONLY; identity comes from the session.
  - On a scoped URL the role+username segments must match current_user, else 403.
  - **Scoped is canonical.** A logged-in user who lands on a flat in-app URL is redirected to the
    matching scoped URL; the scoped URL renders the page in place (no further redirect).
  - Auth/static/logout/pending stay flat (no session-derived identity in the path).
"""
from flask import Blueprint, abort, current_app, redirect, request, url_for
from flask_login import current_user
from werkzeug.exceptions import HTTPException
from werkzeug.test import EnvironBuilder

bp = Blueprint("scoped", __name__)

# roles that may appear in scoped URLs
_ROLES = {"admin", "sales", "inventory", "manufacturing", "purchase", "owner"}

# flat URL prefixes that are NEVER scoped (no session/role on the path)
_NEVER_SCOPE_PREFIXES = ("/login", "/signup", "/logout", "/pending", "/static/")


def _expected_role_username():
    if not getattr(current_user, "is_authenticated", False):
        return (None, None)
    role = "admin" if current_user.is_admin else (current_user.role or None)
    return (role, current_user.login_id)


def _should_scope(flat_path: str) -> bool:
    if not flat_path.startswith("/"):
        return False
    if flat_path == "/":                       # the public landing route is never scoped
        return False
    if any(flat_path.startswith(p) for p in _NEVER_SCOPE_PREFIXES):
        return False
    return True


@bp.route("/<role>/<username>/", defaults={"rest": ""})
@bp.route("/<role>/<username>/<path:rest>")
def dispatch(role, username, rest):
    """Validate role+username, then RENDER the matching flat view in place (URL bar stays scoped)."""
    if role not in _ROLES:
        abort(404)
    expected_role, expected_username = _expected_role_username()
    if expected_role is None:
        return redirect(url_for("auth.login"))
    if role != expected_role or username != expected_username:
        abort(403)

    # Match the flat path against the URL map; call the matched view in-place.
    # request.args is read from the live request, so query string is preserved automatically.
    # Empty rest -> the user's home (dashboard or admin), not the landing page.
    if rest:
        target = "/" + rest
    elif role == "admin":
        target = "/admin/"
    else:
        target = "/dashboard/"
    adapter = current_app.url_map.bind("", path_info=target)
    try:
        endpoint, values = adapter.match(method=request.method)
    except HTTPException:
        # No flat route matches; let Flask route through registered error handlers (custom 404).
        abort(404)
    view = current_app.view_functions[endpoint]
    return view(**values)


# ---- auto-redirect flat -> scoped for logged-in users ----
@bp.before_app_request
def _canonicalize_to_scoped():
    """If a logged-in user hits a flat in-app URL, redirect to the scoped canonical."""
    path = request.path
    # If the URL is ALREADY scoped (/<role>/<username>/...) let the dispatcher handle it.
    # A scoped URL needs BOTH a known-role segment AND a non-empty username segment.
    parts = path.lstrip("/").split("/", 2)
    if len(parts) >= 2 and parts[0] in _ROLES and parts[1]:
        return None
    if not _should_scope(path):
        return None
    role, username = _expected_role_username()
    if not role or not username:
        return None
    # Special case: '/<role>/' (just the role, no username) -> the scoped home '/<role>/<username>/'
    # (avoids the silly '/admin/admin1/admin/' double-prefix when admin hits '/admin/').
    if path == f"/{role}/":
        scoped = f"/{role}/{username}/"
    else:
        scoped = f"/{role}/{username}{path}"
    if request.query_string:
        scoped += "?" + request.query_string.decode("latin-1")
    # only redirect safe methods (GET/HEAD); leave POST/PUT/DELETE alone (no body re-issue)
    if request.method in ("GET", "HEAD"):
        return redirect(scoped, code=302)
    return None


def route_for(endpoint: str, **values) -> str:
    """url_for, prefixed with /<role>/<username>/ when the user is logged in and scoping applies.

    Falls back to plain url_for for auth/static/logout/pending or anonymous users.
    """
    flat = url_for(endpoint, **values)
    role, username = _expected_role_username()
    if not role or not username:
        return flat
    if not _should_scope(flat):
        return flat
    if flat.startswith(f"/{role}/{username}/"):
        return flat
    return f"/{role}/{username}{flat}"
