"""Audit Logs read/query service — stats, filtering, pagination for the Audit Logs screen.

Writing entries lives in services/audit.py; this module only READS. See spec/pages/user/audit-logs.md.
"""
from datetime import datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models.logs import AuditLog
from app.models.user import User

PAGE_SIZE = 15


def stats() -> dict:
    """The 4 stat-card numbers (all-time)."""
    by_action = dict(
        db.session.query(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action).all()
    )
    return {
        "total": sum(by_action.values()),
        "create": by_action.get("create", 0),
        "update": by_action.get("write", 0),      # 'write' is our edit/update action
        "delete": by_action.get("delete", 0),
    }


def _apply_filters(q, *, user_id=None, module=None, action=None, date_from=None, date_to=None):
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if module:
        q = q.filter(AuditLog.module == module)
    if action:
        q = q.filter(AuditLog.action == action)
    if date_from:
        q = q.filter(AuditLog.timestamp >= date_from)
    if date_to:
        # inclusive of the whole end day
        q = q.filter(AuditLog.timestamp < date_to + timedelta(days=1))
    return q


def query(page=1, **filters) -> dict:
    """Return a page of filtered audit rows plus pagination meta."""
    q = _apply_filters(AuditLog.query, **filters).order_by(AuditLog.timestamp.desc())
    total = q.count()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, pages))
    rows = q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    return {"rows": rows, "page": page, "pages": pages, "total": total}


def filter_options() -> dict:
    """Distinct values to populate the User / Module / Action dropdowns."""
    users = User.query.order_by(User.name).all()
    modules = [m[0] for m in db.session.query(AuditLog.module)
               .distinct().order_by(AuditLog.module).all() if m[0]]
    actions = [a[0] for a in db.session.query(AuditLog.action)
               .distinct().order_by(AuditLog.action).all() if a[0]]
    return {"users": users, "modules": modules, "actions": actions}


def parse_date(s):
    """Accept 'YYYY-MM-DD' (HTML date input) -> datetime, else None."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None
