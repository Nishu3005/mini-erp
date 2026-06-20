"""Audit-log writer. Every *(track logs)* change/transition records an entry.

See spec/pages/user/audit-logs.md and spec/sequences-and-conventions.md §3. Caller commits.
"""
from flask_login import current_user

from app.extensions import db
from app.models.logs import AuditLog


def log(module: str, record_ref: str, record_type: str, action: str,
        field: str = None, old_value=None, new_value=None) -> AuditLog:
    entry = AuditLog(
        user_id=getattr(current_user, "id", None),
        module=module,
        record_ref=record_ref,
        record_type=record_type,
        action=action,
        field=field,
        old_value=None if old_value is None else str(old_value),
        new_value=None if new_value is None else str(new_value),
    )
    db.session.add(entry)
    return entry
