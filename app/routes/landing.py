"""Public landing page (the app's front door)."""
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

bp = Blueprint("landing", __name__)


@bp.route("/")
def index():
    # Logged-in users go straight to their home; anonymous see the marketing landing.
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        if getattr(current_user, "status", "active") != "active":
            return redirect(url_for("auth.pending"))
        return redirect(url_for("dashboard.index"))
    return render_template("landing/index.html")
