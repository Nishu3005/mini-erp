"""User account and per-module access rights.

See spec/database-schema.md (`user`, `access_right`) and spec/access-rights.md.
"""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

# Modules that carry access rights (one access_right row per user+module).
RIGHTS_MODULES = ("sales", "purchase", "manufacturing", "product")


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.String(12), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120))
    address = db.Column(db.String(255))
    mobile = db.Column(db.String(40))
    position = db.Column(db.String(80))           # admin-only editable
    photo_path = db.Column(db.String(255))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    access_rights = db.relationship(
        "AccessRight", backref="user", cascade="all, delete-orphan", lazy="selectin"
    )

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def __repr__(self) -> str:
        return f"<User {self.login_id}>"


class AccessRight(db.Model):
    """One row per (user, module): a baseline role plus CRUD/action flags."""
    __tablename__ = "access_right"
    __table_args__ = (db.UniqueConstraint("user_id", "module", name="uq_user_module"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    module = db.Column(db.String(20), nullable=False)        # sales/purchase/manufacturing/product
    role = db.Column(db.String(10), nullable=False, default="none")  # admin/user/none

    can_view = db.Column(db.Boolean, default=False)
    can_create = db.Column(db.Boolean, default=False)
    can_edit = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    can_approve = db.Column(db.Boolean, default=False)            # sales confirm / purchase approve
    can_production_entry = db.Column(db.Boolean, default=False)   # manufacturing only
    can_edit_bom = db.Column(db.Boolean, default=False)          # manufacturing only

    def __repr__(self) -> str:
        return f"<AccessRight u{self.user_id} {self.module}={self.role}>"
