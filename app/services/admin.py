"""System-administrator service: user listing/search + per-module rights editing.

See spec/pages/system-adminstrator/system-adminstrator-pages.md.
"""
from app.models.user import AccessRight, User
from app.services import audit
from app.services.rights_grid import ACTIONS, MODULES
from app.services.unitofwork import atomic

# the access_right boolean column backing each grid action
_FLAG = {"create": "can_create", "view": "can_view", "edit": "can_edit", "delete": "can_delete"}


def list_users(search: str = "", status: str = None) -> list:
    """Non-admin users an admin manages, optionally filtered by search and/or status."""
    q = User.query.filter_by(is_admin=False)
    if status:
        q = q.filter(User.status == status)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (User.name.ilike(like)) | (User.login_id.ilike(like)) | (User.email.ilike(like)))
    return q.order_by(User.status.desc(), User.name).all()


def pending_count() -> int:
    return User.query.filter_by(is_admin=False, status="pending").count()


def approve_user(user, role: str) -> None:
    """Approve a waiting-list user: set their role + activate. Admin-gated upstream."""
    from app.services.roles import REQUESTABLE_ROLES
    if role not in REQUESTABLE_ROLES:
        raise ValueError("Choose a valid role to approve the user as.")
    with atomic():
        audit.log("audit", user.login_id, "User", "write",
                  field="status", old_value=user.status, new_value="active")
        audit.log("audit", user.login_id, "User", "write",
                  field="role", old_value=user.role, new_value=role)
        user.role = role
        user.status = "active"


def reject_user(user) -> None:
    with atomic():
        audit.log("audit", user.login_id, "User", "write",
                  field="status", old_value=user.status, new_value="rejected")
        user.status = "rejected"


def rights_for(user) -> dict:
    """{module: AccessRight} for the user, creating empty (none) rows in-memory where missing."""
    existing = {r.module: r for r in user.access_rights}
    out = {}
    for m in MODULES:
        out[m] = existing.get(m) or AccessRight(user_id=user.id, module=m, role="none")
    return out


def save_user_rights(user, position, grid, role=None) -> None:
    """Persist Position (admin-only) + optional Role change + per-module CRUD flag overrides.

    `grid` = {(module, action): bool}. One access_right row per module is upserted; the module-level
    flag is the OR of its grid checkboxes for that action (field rows share the module permission).
    """
    from app.services.roles import REQUESTABLE_ROLES
    with atomic():
        # Position is the only profile field an admin may change.
        if position is not None and (user.position or "") != position:
            audit.log("audit", user.login_id, "User", "write",
                      field="position", old_value=user.position, new_value=position)
            user.position = position

        # Optional role change — admin can re-assign an active user's role.
        if role and role != user.role and role in REQUESTABLE_ROLES:
            audit.log("audit", user.login_id, "User", "write",
                      field="role", old_value=user.role, new_value=role)
            user.role = role

        existing = {r.module: r for r in user.access_rights}
        for module in MODULES:
            row = existing.get(module)
            if row is None:
                row = AccessRight(user_id=user.id, module=module, role="none")
                from app.extensions import db
                db.session.add(row)
            for action in ACTIONS:
                new = bool(grid.get((module, action)))
                setattr(row, _FLAG[action], new)
            # role mirrors view access for a quick admin/user/none read
            row.role = "user" if row.can_view else "none"
        audit.log("audit", user.login_id, "User", "write", field="access_rights")
