"""Pytest fixtures: an app bound to a fresh in-memory SQLite DB per test."""
from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db as _db
from app.models.partner import Customer, Vendor
from app.models.product import Product
from app.models.user import AccessRight, User


@pytest.fixture()
def app():
    app = create_app("dev")
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
        TESTING=True,
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()


def _grant_all(user, module):
    return AccessRight(user_id=user.id, module=module, role="user",
                       can_view=True, can_create=True, can_edit=True, can_delete=True,
                       can_approve=True, can_production_entry=True, can_edit_bom=True)


@pytest.fixture()
def seeded(db):
    """A minimal coherent dataset: one full-access user, a customer, vendor, and product."""
    u = User(login_id="tester1", email="t@x.com", is_admin=False, name="Tester")
    u.set_password("Strong@1pass")
    db.session.add(u); db.session.flush()
    for m in ("sales", "purchase", "manufacturing", "product"):
        db.session.add(_grant_all(u, m))

    from app.services import sequences
    cust = Customer(name="Acme", address="A St")
    vend = Vendor(name="VendCo", address="V St")
    prod = Product(reference=sequences.next_reference("PRD"), name="Chair",
                   sales_price=Decimal("100"), cost_price=Decimal("60"),
                   on_hand_qty=Decimal("20"))
    db.session.add_all([cust, vend, prod])
    db.session.commit()
    return {"user": u, "customer": cust, "vendor": vend, "product": prod}
