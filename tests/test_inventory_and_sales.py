"""Inventory math + sales/purchase/manufacturing state machines."""
from decimal import Decimal

import pytest

from app.models.purchase import PurchaseOrder, PurchaseOrderLine
from app.models.sales import SalesOrder, SalesOrderLine
from app.services import purchase as po_svc
from app.services import sales as so_svc
from app.services import sequences


def _so(db, seeded, qty="5"):
    o = SalesOrder(reference=sequences.next_reference("SO"), status="draft",
                   customer_id=seeded["customer"].id)
    db.session.add(o); db.session.flush()
    db.session.add(SalesOrderLine(sales_order_id=o.id, product_id=seeded["product"].id,
                                  ordered_qty=Decimal(qty), sales_price=Decimal("100")))
    db.session.commit()
    return o


def test_free_to_use_formula(db, seeded):
    p = seeded["product"]
    assert p.free_to_use_qty == p.on_hand_qty - p.reserved_qty


def test_confirm_reserves_then_partial_delivery_moves_stock(db, seeded):
    p = seeded["product"]
    o = _so(db, seeded, "5")
    so_svc.confirm(o)
    assert o.status == "confirmed"
    assert p.reserved_qty == Decimal("5")          # full order reserved
    assert p.free_to_use_qty == Decimal("15")      # 20 - 5

    so_svc.deliver(o, {o.lines[0].id: "2"})
    assert o.status == "partially_delivered"
    assert p.on_hand_qty == Decimal("18")          # stock moved on PARTIAL delivery
    assert p.reserved_qty == Decimal("3")          # outstanding shrinks

    so_svc.deliver(o, {o.lines[0].id: "3"})
    assert o.status == "fully_delivered"
    assert p.on_hand_qty == Decimal("15")
    assert p.reserved_qty == Decimal("0")          # released when fulfilled


def test_over_deliver_rejected(db, seeded):
    o = _so(db, seeded, "5")
    so_svc.confirm(o)
    with pytest.raises(so_svc.SalesError):
        so_svc.deliver(o, {o.lines[0].id: "6"})


def test_confirm_empty_order_rejected(db, seeded):
    o = SalesOrder(reference=sequences.next_reference("SO"), status="draft",
                   customer_id=seeded["customer"].id)
    db.session.add(o); db.session.commit()
    with pytest.raises(so_svc.SalesError):
        so_svc.confirm(o)


def test_purchase_receive_increases_stock(db, seeded):
    p = seeded["product"]
    o = PurchaseOrder(reference=sequences.next_reference("PO"), status="draft",
                      vendor_id=seeded["vendor"].id)
    db.session.add(o); db.session.flush()
    db.session.add(PurchaseOrderLine(purchase_order_id=o.id, product_id=p.id,
                                     ordered_qty=Decimal("10"), cost_price=Decimal("60")))
    db.session.commit()
    po_svc.confirm(o)
    before = p.on_hand_qty
    po_svc.receive(o, {o.lines[0].id: "10"})
    assert o.status == "fully_received"
    assert p.on_hand_qty == before + Decimal("10")


def test_sequences_unique(db, seeded):
    a, b = sequences.next_reference("SO"), sequences.next_reference("SO")
    assert a != b and a.startswith("SO-")
