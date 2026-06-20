"""Profile route (User Login Detail Management). Thin controller; logic in services/profile.py."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.services import profile as profile_svc

bp = Blueprint("profile", __name__, url_prefix="/profile")


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        try:
            profile_svc.update_self(current_user, request.form, request.files.get("photo"))
            flash("Profile updated.", "success")
        except ValueError as e:
            flash(str(e), "error")
        return redirect(url_for("profile.index"))
    return render_template("profile/index.html", user=current_user)
