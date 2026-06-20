"""Access-rights service. The ONLY read path for authorization checks.

See spec/access-rights.md. Admin users bypass all checks. Otherwise the (user, module) row's
flags decide. Deny by default.
"""
from functools import wraps

from flask import abort
from flask_login import current_user

from app.models.user import AccessRight

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


def can(user, module: str, action: str) -> bool:
    """True if `user` may perform `action` on `module`."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_admin", False):
        return True
    right = next((r for r in user.access_rights if r.module == module), None)
    if right is None:
        return False
    flag = _ACTION_FLAG.get(action)
    return bool(flag and getattr(right, flag, False))


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
