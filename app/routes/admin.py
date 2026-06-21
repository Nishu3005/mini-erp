"""System Administrator routes. Admin-only (is_admin). See spec/pages/system-adminstrator/."""
from functools import wraps

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required

from app.models.user import User
from app.services import admin as admin_svc
from app.services.rights_grid import ACTIONS, MODULES, TABS

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_only(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(current_user, "is_admin", False):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@bp.route("/")
@login_required
@admin_only
def dashboard():
    """System Administrator Dashboard — the Users list (admin landing page)."""
    search = (request.args.get("q") or "").strip()
    status = request.args.get("status") or None
    view = "kanban" if request.args.get("view") == "kanban" else "list"
    users = admin_svc.list_users(search, status=status)
    return render_template("admin/dashboard.html", users=users, search=search, view=view,
                           status=status, pending_count=admin_svc.pending_count())


@bp.route("/users/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_only
def user_form(user_id):
    """User Management form: read-only profile header + Position + 4-tab CRUD rights grid."""
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        # collect checked grid cells: input name "right-<module>-<action>"
        grid = {(m, a): bool(request.form.get(f"right-{m}-{a}"))
                for m in MODULES for a in ACTIONS}
        admin_svc.save_user_rights(
            user,
            request.form.get("position", "").strip(),
            grid,
            role=request.form.get("role") or None,
        )
        flash(f"Rights for {user.name or user.login_id} saved.", "success")
        return redirect(url_for("admin.user_form", user_id=user.id))

    from app.services.roles import REQUESTABLE_ROLES, ROLE_LABELS
    return render_template(
        "admin/user_form.html",
        user=user,
        tabs=TABS,
        rights=admin_svc.rights_for(user),
        active_tab=request.args.get("tab", "sales"),
        requestable_roles=[(r, ROLE_LABELS[r]) for r in REQUESTABLE_ROLES],
    )


@bp.route("/users/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_only
def approve(user_id):
    user = User.query.get_or_404(user_id)
    try:
        admin_svc.approve_user(user, request.form.get("role") or user.requested_role)
        flash(f"{user.name or user.login_id} approved as {user.role_label}.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.user_form", user_id=user.id))


@bp.route("/users/<int:user_id>/reject", methods=["POST"])
@login_required
@admin_only
def reject(user_id):
    user = User.query.get_or_404(user_id)
    admin_svc.reject_user(user)
    flash(f"{user.name or user.login_id}'s request was rejected.", "info")
    return redirect(url_for("admin.dashboard"))


@bp.route("/bulk-import", methods=["POST"])
@login_required
@admin_only
def bulk_import():
    """Admin bulk-uploads a JSON file of customers / vendors / products."""
    from app.services import bulk_import as bi
    from app.services.unitofwork import InputError

    dataset = (request.form.get("dataset") or "").strip()
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Choose a JSON file to import.", "error")
        return redirect(url_for("admin.dashboard"))
    try:
        result = bi.import_json(dataset, file.read())
    except InputError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.dashboard"))

    msg = f"{dataset.title()} import — added {result['added']}, skipped {result['skipped']} (duplicates)"
    if result["error_count"]:
        msg += f", {result['error_count']} rejected row(s)"
        for err in result["errors"][:3]:
            msg += f"\n  · {err}"
    flash(msg, "success" if result["added"] else "info")
    return redirect(url_for("admin.dashboard"))
