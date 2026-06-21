"""Application factory. See spec/project-structure.md."""
from pathlib import Path

from flask import Flask, render_template
from sqlalchemy.exc import OperationalError

from config import config_by_name
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_name: str = "dev") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Fail fast: production must supply a real SECRET_KEY (no insecure fallback).
    if config_name == "prod" and not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable is required in production.")

    # ensure instance/ exists for the SQLite file
    Path(app.root_path).parent.joinpath("instance").mkdir(exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    adding_admin = db

    from app import models  # noqa: F401  (register models with metadata)

    # Self-heal: if the DB file is missing the core `user` table (fresh clone, deleted file,
    # corrupted migration state), create everything from the ORM metadata. This makes the app
    # bootable even if the user never ran `flask reset-db`. Idempotent — no-op when tables exist.
    with app.app_context():
        from sqlalchemy import inspect
        try:
            if not inspect(db.engine).has_table("user"):
                db.create_all()
        except Exception:
            # If even the inspector fails (no DB file at all), create_all from scratch.
            db.create_all()

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(models.User, int(user_id))
        except OperationalError:
            # DB got wiped/dropped while we were running (e.g. `flask reset-db` in another shell,
            # a test suite, manual file delete). Recreate the schema and treat this request as
            # anonymous — the user's next click will land them on /login.
            db.session.rollback()
            db.create_all()
            return None

    from app.routes.admin import bp as admin_bp
    from app.routes.api import bp as api_bp
    from app.routes.audit import bp as audit_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.bom import bp as bom_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.landing import bp as landing_bp
    from app.routes.manufacturing import bp as manufacturing_bp
    from app.routes.product import bp as product_bp
    from app.routes.profile import bp as profile_bp
    from app.routes.purchase import bp as purchase_bp
    from app.routes.sales import bp as sales_bp
    from app.services.urlscheme import bp as scoped_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)                 # /api/v1/...  (JWT-guarded, see spec/jwt-api.md)
    csrf.exempt(api_bp)                            # API uses Bearer JWT, not session CSRF
    app.register_blueprint(audit_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(bom_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(landing_bp)
    app.register_blueprint(manufacturing_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(purchase_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(scoped_bp)            # /<role>/<username>/<rest> dispatcher

    @app.context_processor
    def inject_helpers():
        from app.services.access import can_current
        from app.services.urlscheme import route_for
        return {"access_can": can_current, "route_for": route_for}

    # also expose route_for as a Jinja global so macros (no context) can use it
    from app.services.urlscheme import route_for as _route_for
    app.jinja_env.globals["route_for"] = _route_for

    # per-page footer illustration (returns None if static/illustrations/<page>/ is empty)
    from app.services.illustrations import page_illustration_url as _page_illustration
    app.jinja_env.globals["page_illustration"] = _page_illustration

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    _register_cli(app)
    return app


def _register_cli(app: Flask) -> None:
    import click

    from app.models.user import AccessRight, RIGHTS_MODULES, User

    @app.cli.command("init-db")
    def init_db():
        """Create all tables (dev shortcut; use migrations in real flow)."""
        db.create_all()
        click.echo("Tables created.")

    @app.cli.command("reset-db")
    def reset_db():
        """One-shot: nuke the SQLite file, recreate tables via db.create_all(), reseed.

        The idiot-proof recovery: whatever mess the DB is in, this puts it back to a clean
        seeded state in seconds. (Skips Alembic — uses metadata.create_all directly so it works
        even if migration state is corrupted.)
        """
        import os
        from app.services import seed
        # 1. Drop ALL tables in the live engine (handles file-locked case better than os.remove)
        db.drop_all()
        # 2. Recreate every table from the live ORM metadata
        db.create_all()
        # 3. Stamp Alembic to head so future migrations work
        try:
            from flask_migrate import stamp
            stamp(revision="head")
        except Exception:
            pass
        # 4. Seed
        summary = seed.seed()
        click.echo("DB reset.")
        click.echo("Seeded: " + ", ".join(f"{k}={v}" for k, v in summary.items()))

    @app.cli.command("seed-admin")
    @click.option("--login-id", default="admin1")
    @click.option("--email", default="admin@shiv.local")
    @click.option("--password", default="Admin@123")
    def seed_admin(login_id, email, password):
        """Create a System Administrator account."""
        if User.query.filter_by(login_id=login_id).first():
            click.echo("Admin already exists.")
            return
        admin = User(login_id=login_id, email=email, name="System Administrator",
                     position="Administrator", is_admin=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin '{login_id}' created. Password set from the --password option.")

    @app.cli.command("seed-data")
    @click.option("--reset", is_flag=True, help="Wipe existing data first, then reload.")
    def seed_data(reset):
        """Load JSON from data/ and data/generated/ into the DB (fast, bulk-insert)."""
        from app.services import seed

        if seed.has_data() and not reset:
            click.echo("Data already present. Use --reset to wipe and reload.")
            return
        if reset:
            seed.reset()
            click.echo("Existing data wiped.")
        summary = seed.seed()
        click.echo("Seeded: " + ", ".join(f"{k}={v}" for k, v in summary.items()))

