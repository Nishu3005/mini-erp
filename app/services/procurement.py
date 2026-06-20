"""Procurement automation (MTS vs MTO) — the headline ERP feature.

On Sales Order confirmation, for each line whose product has `procure_on_demand`, if there is a
shortage, auto-create a Draft Purchase Order or Manufacturing Order for the shortfall.
See spec/inventory-and-stock-ledger.md §6 and spec/pages/user/product/product.md.

Caller (sales.confirm) commits the transaction.
"""
from decimal import Decimal

from app.extensions import db
from app.models.bom import Bom
from app.models.manufacturing import (ManufacturingOrder, MoComponent,
                                      WorkOrder)
from app.models.purchase import PurchaseOrder, PurchaseOrderLine
from app.services import audit, sequences


def run_for_sales_order(order) -> dict:
    """Create procurement docs for shortages on a just-confirmed SO. Returns counts/refs."""
    created = {"purchase_orders": [], "manufacturing_orders": []}

    for line in order.lines:
        product = line.product
        if not product.procure_on_demand:
            continue  # MTS with stock, or procurement disabled -> nothing to do

        # Shortage = ordered demand beyond what is physically on hand.
        shortage = Decimal(line.ordered_qty or 0) - Decimal(product.on_hand_qty or 0)
        if shortage <= 0:
            continue

        if product.procure_method == "purchase":
            ref = _create_purchase_order(product, shortage, order)
            created["purchase_orders"].append(ref)
        elif product.procure_method == "manufacturing":
            ref = _create_manufacturing_order(product, shortage, order)
            created["manufacturing_orders"].append(ref)

    return created


def _create_purchase_order(product, qty: Decimal, source_so) -> str:
    po = PurchaseOrder(
        reference=sequences.next_reference("PO"),
        status="draft",
        vendor_id=product.vendor_id,
        vendor_address=product.vendor.address if product.vendor else None,
    )
    db.session.add(po)
    db.session.flush()
    db.session.add(PurchaseOrderLine(
        purchase_order_id=po.id, product_id=product.id,
        ordered_qty=qty, cost_price=product.cost_price,
    ))
    audit.log("purchase", po.reference, "PurchaseOrder", "create",
              field="auto_from", new_value=source_so.reference)
    return po.reference


def _create_manufacturing_order(product, qty: Decimal, source_so) -> str:
    bom = db.session.get(Bom, product.bom_id) if product.bom_id else None
    mo = ManufacturingOrder(
        reference=sequences.next_reference("MO"),
        status="draft",
        finished_product_id=product.id,
        quantity=qty,
        bom_id=bom.id if bom else None,
    )
    db.session.add(mo)
    db.session.flush()
    if bom:
        for comp in bom.components:
            db.session.add(MoComponent(
                mo_id=mo.id, product_id=comp.product_id,
                to_consume=Decimal(comp.to_consume or 0) * qty,
            ))
        for op in bom.operations:
            db.session.add(WorkOrder(
                mo_id=mo.id, operation=op.operation, work_center=op.work_center,
                expected_duration=int((op.expected_duration or 0) * int(qty)),
            ))
    audit.log("manufacturing", mo.reference, "ManufacturingOrder", "create",
              field="auto_from", new_value=source_so.reference)
    return mo.reference
