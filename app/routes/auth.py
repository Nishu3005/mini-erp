"""Auth routes: login (user + admin share one table), signup, logout.

Thin controller — validation lives in forms, persistence is a small unit of work here.
See spec/pages/auth/auth.md.
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.forms.auth import LoginForm, SignupForm
from app.models.user import User
from app.services import audit

bp = Blueprint("auth", __name__)

INVALID_MSG = "Invalid Login Id or Password"   # exact string from spec — do not change


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    # `as_admin` toggles which login surface is shown; auth itself is identical.
    as_admin = request.args.get("as_admin") == "1"
    if form.validate_on_submit():
        user = User.query.filter_by(login_id=form.login_id.data).first()
        if user is None or not user.check_password(form.password.data):
            flash(INVALID_MSG, "error")
        else:
            login_user(user)
            return redirect(url_for("dashboard.index"))
    return render_template("auth/login.html", form=form, as_admin=as_admin)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = SignupForm()
    if form.validate_on_submit():
        # uniqueness checks (login_id + email) beyond field validators
        if User.query.filter_by(login_id=form.login_id.data).first():
            flash("Login Id already exists.", "error")
        elif User.query.filter_by(email=form.email.data).first():
            flash("Email Id already exists.", "error")
        else:
            user = User(login_id=form.login_id.data, email=form.email.data, is_admin=False)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()
            audit.log("audit", user.login_id, "User", "create")
            db.session.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/signup.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
