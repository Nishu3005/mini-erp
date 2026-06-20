"""Audit Logs screen — stats, filters, paginated table. Admin-only (full, cross-module).

Per spec/access-rights.md the standalone Audit Logs view is Admin-only. The per-record "Logs"
panels on forms remain visible to module viewers; this is the master screen + the destination of a
form's "Logs" button (which pre-applies ?module=).
"""
from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.services import audit_query

bp = Blueprint("audit", __name__, url_prefix="/audit")


@bp.route("/")
@login_required
def index():
    if not current_user.is_admin:
        abort(403)

    user_id = request.args.get("user_id", type=int)
    module = request.args.get("module") or None
    action = request.args.get("action") or None
    date_from = audit_query.parse_date(request.args.get("date_from"))
    date_to = audit_query.parse_date(request.args.get("date_to"))
    page = request.args.get("page", default=1, type=int)

    filters = dict(user_id=user_id, module=module, action=action,
                   date_from=date_from, date_to=date_to)
    result = audit_query.query(page=page, **filters)

    return render_template(
        "audit/index.html",
        stats=audit_query.stats(),
        options=audit_query.filter_options(),
        result=result,
        selected=dict(user_id=user_id, module=module, action=action,
                      date_from=request.args.get("date_from", ""),
                      date_to=request.args.get("date_to", "")),
    )
