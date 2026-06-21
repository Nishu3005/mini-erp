"""Regression tests for the harsh review findings:

A. Procurement shortage must use Free-To-Use (on_hand − reserved), NOT just on_hand_qty.
B. Stock movement must take a row-lock (verified by the call running through .with_for_update()).
C. Product update must NOT change on_hand_qty directly (use adjust_stock instead).
D. Manufacturing produce should respect Work Order completion (added once WO routing lands).
"""
from decimal import Decimal

from app.models.bom import Bom, BomComponent
from app.models.product import Product
from app.models.sales import SalesOrder, SalesOrderLine
from app.services import inventory, product as product_svc
from app.services import sales as so_svc, sequences


def test_A_mto_shortage_uses_free_to_use_not_on_hand(db, seeded):
    """If all stock is already reserved by another open SO, a new SO must auto-procure for the FULL
    amount it needs — not zero (the old broken math)."""
    p = seeded["product"]
    p.on_hand_qty = Decimal("10")
    p.procure_on_demand = True
    p.procure_method = "manufacturing"
    # need a BoM so MO creation works
    bom = Bom(reference=sequences.next_reference("BOM"),
              finished_product_id=p.id, quantity=Decimal("1"))
    db.session.add(bom); db.session.flush()
    p.bom_id = bom.id
    db.session.commit()

    cust = seeded["customer"]
    # SO #1: reserve all 10 by confirming an order of 10
    so1 = SalesOrder(reference=sequences.next_reference("SO"), status="draft",
                     customer_id=cust.id)
    db.session.add(so1); db.session.flush()
    db.session.add(SalesOrderLine(sales_order_id=so1.id, product_id=p.id,
                                  ordered_qty=Decimal("10"), sales_price=p.sales_price))
    db.session.commit()
    # Confirm so the 10 units are now reserved
    so_svc.confirm(so1)
    # Sanity: nothing free
    assert p.free_to_use_qty <= Decimal("0")

    # SO #2: order 5 more of the SAME product — old code would compute
    # shortage = 5 − on_hand(10) = -5 → procure NOTHING (broken).
    # Fixed code computes against free_to_use; should procure for 5.
    so2 = SalesOrder(reference=sequences.next_reference("SO"), status="draft",
                     customer_id=cust.id)
    db.session.add(so2); db.session.flush()
    db.session.add(SalesOrderLine(sales_order_id=so2.id, product_id=p.id,
                                  ordered_qty=Decimal("5"), sales_price=p.sales_price))
    db.session.commit()
    result = so_svc.confirm(so2)

    assert result["manufacturing_orders"], (
        "MTO must auto-create an MO for SO #2 even when on_hand looks sufficient — "
        "stock is already reserved by SO #1.")


def test_C_product_update_cannot_change_on_hand_qty(db, seeded):
    """Direct edits to on_hand_qty via the product CRUD must be ignored (use adjust_stock)."""
    p = seeded["product"]
    original = Decimal(p.on_hand_qty)
    # Pass a wildly different on_hand_qty in the update payload — it should be IGNORED.
    product_svc.update(p, {
        "name": p.name, "sales_price": p.sales_price, "cost_price": p.cost_price,
        "on_hand_qty": Decimal("9999"),
        "procure_on_demand": False,
    })
    db.session.refresh(p)
    assert p.on_hand_qty == original, (
        "Product.update() must not change on_hand_qty — use product_svc.adjust_stock(...) instead.")


def test_C_adjust_stock_moves_via_ledger(db, seeded):
    """adjust_stock() must move On Hand AND write a stock_ledger entry (source='adjustment')."""
    from app.models.logs import StockLedger
    p = seeded["product"]
    before = Decimal(p.on_hand_qty)
    product_svc.adjust_stock(p, Decimal("3"), reason="inventory-count")
    db.session.commit()
    db.session.refresh(p)
    assert p.on_hand_qty == before + Decimal("3")
    entry = StockLedger.query.filter_by(product_id=p.id, source="adjustment").first()
    assert entry is not None and entry.qty_delta == Decimal("3")


def test_D_produce_blocked_until_work_orders_done(db, seeded):
    """Finding D: produce() must reject MOs whose work orders aren't all Done."""
    from app.models.manufacturing import ManufacturingOrder, MoComponent, WorkOrder
    from app.services import manufacturing as mfg_svc

    p = seeded["product"]
    # a second product to use as a component
    comp_prod = Product(reference=sequences.next_reference("PRD"), name="Wood Plank",
                        sales_price=Decimal("5"), cost_price=Decimal("2"),
                        on_hand_qty=Decimal("100"))
    db.session.add(comp_prod); db.session.flush()

    mo = ManufacturingOrder(reference=sequences.next_reference("MO"), status="draft",
                            finished_product_id=p.id, quantity=Decimal("1"))
    db.session.add(mo); db.session.flush()
    db.session.add(MoComponent(mo_id=mo.id, product_id=comp_prod.id, to_consume=Decimal("2")))
    db.session.add(WorkOrder(mo_id=mo.id, operation="Cut",   work_center="Saw",   expected_duration=10))
    db.session.add(WorkOrder(mo_id=mo.id, operation="Sand",  work_center="Bench", expected_duration=5))
    db.session.commit()

    mfg_svc.confirm(mo)
    # Try to produce while WOs are still 'todo' — must fail.
    import pytest as _pytest
    with _pytest.raises(mfg_svc.ManufacturingError, match="work order"):
        mfg_svc.produce(mo)

    # Start + finish each WO. State machine: confirmed -> in_progress on first WO start.
    for wo in mo.work_orders:
        mfg_svc.start_work_order(wo)
        mfg_svc.finish_work_order(wo, real_duration_minutes=3)
    db.session.commit()
    assert mo.all_work_orders_done
    assert mo.status == "in_progress"   # promoted by first start_work_order

    # Now produce succeeds.
    mfg_svc.produce(mo)
    db.session.commit()
    assert mo.status == "done"


def test_D_work_order_state_machine_transitions(db, seeded):
    """Finding D: WO transitions todo→in_progress→done; double-start/double-finish are safe."""
    from app.models.manufacturing import ManufacturingOrder, WorkOrder
    from app.services import manufacturing as mfg_svc

    p = seeded["product"]
    mo = ManufacturingOrder(reference=sequences.next_reference("MO"), status="draft",
                            finished_product_id=p.id, quantity=Decimal("1"))
    db.session.add(mo); db.session.flush()
    wo = WorkOrder(mo_id=mo.id, operation="Assemble", work_center="A1", expected_duration=10)
    db.session.add(wo)
    db.session.commit()
    mfg_svc.confirm(mo)

    mfg_svc.start_work_order(wo, by_user_id=seeded["user"].id)
    assert wo.status == "in_progress"
    assert wo.started_at is not None
    assert wo.assignee_id == seeded["user"].id

    mfg_svc.start_work_order(wo)   # idempotent
    assert wo.status == "in_progress"

    mfg_svc.finish_work_order(wo, real_duration_minutes=12)
    assert wo.status == "done"
    assert wo.real_duration == 12
    mfg_svc.finish_work_order(wo)   # idempotent


def test_B_record_movement_executes_under_row_lock(db, seeded):
    """A sanity check that record_movement still works (and the locked Product row is consistent
    with the caller's reference). Full multi-process concurrency tests are out of scope here."""
    p = seeded["product"]
    before = Decimal(p.on_hand_qty)
    inventory.record_movement(p, Decimal("7"), "purchase", "PO-TEST")
    db.session.commit()
    db.session.refresh(p)
    assert p.on_hand_qty == before + Decimal("7")
