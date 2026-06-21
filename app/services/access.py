"""Access-rights service. The ONLY read path for authorization checks.

Resolution (spec/rbac-redesign.md §3):
  1. not logged in / not an active member (pending/rejected) -> deny
  2. admin -> allow everything
  3. a per-user access_right OVERRIDE row for the module -> use its flag
  4. otherwise fall back to the user's ROLE default (services/roles.py)
Deny by default.
"""
from functools import wraps

from flask import abort
from flask_login import current_user

from app.services.roles import role_allows

# action -> the AccessRight flag that grants it
_ACTION_FLAG = {
    "view": "can_view",
    "create": "can_create",
    "edit": "can_edit",
    "delete": "can_delete",
    "approve": "can_approve",
    "confirm": "can_approve",
    "production_entry": "can_production_entry",
    "edit_bom": "can_edit_bom",
}
# normalize the two action aliases to their role-matrix name
_ROLE_ACTION = {"confirm": "approve"}


def can(user, module: str, action: str) -> bool:
    """True if `user` may perform `action` on `module`."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    # pending / rejected users (non-admin) get nothing
    if not getattr(user, "is_active_member", True):
        return False
    if getattr(user, "is_admin", False) or getattr(user, "role", None) == "admin":
        return True

    # per-user override row wins when present
    right = next((r for r in user.access_rights if r.module == module), None)
    if right is not None:
        flag = _ACTION_FLAG.get(action)
        return bool(flag and getattr(right, flag, False))

    # else fall back to the role default
    return role_allows(getattr(user, "role", None), module, _ROLE_ACTION.get(action, action))


def can_current(module: str, action: str) -> bool:
    """can() for the logged-in user — convenience for routes/templates."""
    return can(current_user, module, action)


def require(module: str, action: str):
    """Route decorator: 403 unless current_user can do (module, action)."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not can(current_user, module, action):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
