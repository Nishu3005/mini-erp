"""Procurement automation (MTS/MTO) + access-control checks."""
from decimal import Decimal

from app.models.bom import Bom, BomComponent
from app.models.manufacturing import ManufacturingOrder
from app.models.product import Product
from app.models.purchase import PurchaseOrder
from app.models.sales import SalesOrder, SalesOrderLine
from app.services import access, sequences
from app.services import sales as so_svc


def test_mto_confirm_autocreates_mo(db, seeded):
    """A procure-on-demand=manufacturing product with shortage -> auto MO on SO confirm."""
    leg = Product(reference="PRD-LEG", name="Leg", on_hand_qty=Decimal("100"),
                  sales_price=Decimal("1"), cost_price=Decimal("1"))
    db.session.add(leg); db.session.flush()
    bom = Bom(reference=sequences.next_reference("BOM"),
              finished_product_id=seeded["product"].id, quantity=Decimal("1"))
    db.session.add(bom); db.session.flush()
    db.session.add(BomComponent(bom_id=bom.id, product_id=leg.id, to_consume=Decimal("4")))
    p = seeded["product"]
    p.procure_on_demand = True
    p.procure_method = "manufacturing"
    p.bom_id = bom.id
    p.on_hand_qty = Decimal("3")
    db.session.commit()

    o = SalesOrder(reference=sequences.next_reference("SO"), status="draft",
                   customer_id=seeded["customer"].id)
    db.session.add(o); db.session.flush()
    db.session.add(SalesOrderLine(sales_order_id=o.id, product_id=p.id,
                                  ordered_qty=Decimal("20"), sales_price=Decimal("100")))
    db.session.commit()

    created = so_svc.confirm(o)
    assert created["manufacturing_orders"], "expected an auto MO"
    mo = ManufacturingOrder.query.filter_by(
        reference=created["manufacturing_orders"][0]).first()
    assert mo.quantity == Decimal("17")          # shortage 20 - 3
    assert mo.status == "draft"


def test_mts_no_procurement(db, seeded):
    """Enough stock -> no PO/MO created."""
    p = seeded["product"]
    p.procure_on_demand = True
    p.procure_method = "purchase"
    p.vendor_id = seeded["vendor"].id
    db.session.commit()
    o = SalesOrder(reference=sequences.next_reference("SO"), status="draft",
                   customer_id=seeded["customer"].id)
    db.session.add(o); db.session.flush()
    db.session.add(SalesOrderLine(sales_order_id=o.id, product_id=p.id,
                                  ordered_qty=Decimal("5"), sales_price=Decimal("100")))
    db.session.commit()
    created = so_svc.confirm(o)
    assert not created["purchase_orders"] and not created["manufacturing_orders"]
    assert PurchaseOrder.query.count() == 0


def test_access_admin_bypass_and_deny(db, seeded):
    from app.models.user import User
    admin = User(login_id="admin9", email="a@x.com", is_admin=True)
    admin.set_password("X"); db.session.add(admin); db.session.commit()
    assert access.can(admin, "sales", "approve") is True       # admin bypass
    # the seeded user has all module grants
    assert access.can(seeded["user"], "sales", "view") is True


def test_access_none_denied(db, seeded):
    from app.models.user import AccessRight, User
    u = User(login_id="viewer1", email="v@x.com", is_admin=False)
    u.set_password("X"); db.session.add(u); db.session.flush()
    db.session.add(AccessRight(user_id=u.id, module="sales", role="none", can_view=False))
    db.session.commit()
    assert access.can(u, "sales", "view") is False
    assert access.can(u, "purchase", "view") is False          # no row -> deny
