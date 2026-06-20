"""Sales Order state machine. The ONLY place SO status changes.

State machine (spec/sequences-and-conventions.md §2):
    draft -> confirmed -> partially_delivered -> fully_delivered
    draft|confirmed -> cancelled

Stock & reservation rules (spec/inventory-and-stock-ledger.md):
  - confirm: order becomes a reservation (computed from open lines); may trigger procurement.
  - deliver: On Hand decreases by the INCREMENTAL qty delivered THIS event (P0 fix — not only at
    full completion); each event writes a stock-ledger row; reservation shrinks automatically as
    delivered_qty rises.
  - cancel: releases all reservation (status leaves the open set); no stock movement.
"""
from decimal import Decimal

from app.extensions import db
from app.models.partner import Customer
from app.models.product import Product
from app.models.sales import SalesOrder, SalesOrderLine
from app.services import audit, inventory, procurement, sequences
from app.services.unitofwork import InputError, atomic, to_decimal, to_int


class SalesError(ValueError):
    """Raised on an invalid transition; routes flash the message."""


def create_order(customer_id, salesperson_id, line_inputs) -> SalesOrder:
    """Create a Draft SO from validated inputs. `line_inputs` = list of (product_id, qty) pairs.

    Rejects: missing customer, no valid lines, zero/negative qty, duplicate products.
    """
    customer = db.session.get(Customer, to_int(customer_id, "Customer"))
    if customer is None:
        raise InputError("Select a valid customer.")

    cleaned = []
    seen = set()
    for pid, qty in line_inputs:
        if not pid or qty in (None, "", "0"):
            continue
        pid = to_int(pid, "Product")
        q = to_decimal(qty, "Ordered quantity", minimum=0, allow_zero=False)
        if pid in seen:
            raise InputError("The same product appears on more than one line.")
        product = db.session.get(Product, pid)
        if product is None:
            raise InputError("One of the selected products no longer exists.")
        seen.add(pid)
        cleaned.append((product, q))

    if not cleaned:
        raise InputError("Add at least one product line with a quantity.")

    with atomic():
        order = SalesOrder(
            reference=sequences.next_reference("SO"), status="draft",
            customer_id=customer.id, customer_address=customer.address,
            salesperson_id=salesperson_id,
        )
        db.session.add(order)
        db.session.flush()
        for product, q in cleaned:
            db.session.add(SalesOrderLine(
                sales_order_id=order.id, product_id=product.id,
                ordered_qty=q, sales_price=product.sales_price))
        audit.log("sales", order.reference, "SalesOrder", "create")
    return order


def _set_status(order: SalesOrder, new: str) -> None:
    old = order.status
    order.status = new
    audit.log("sales", order.reference, "SalesOrder", "status_change",
              field="status", old_value=old, new_value=new)


def confirm(order: SalesOrder) -> dict:
    """Draft -> Confirmed. Reserves stock (implicitly) and triggers procurement on shortage.

    Returns a summary of any procurement documents auto-created.
    """
    if order.status != "draft":
        raise SalesError("Only a Draft order can be confirmed.")
    if not order.lines:
        raise SalesError("Cannot confirm an order with no product lines.")

    with atomic():
        _set_status(order, "confirmed")
        # Procurement runs AFTER the status flips so reservations are already in effect.
        created = procurement.run_for_sales_order(order)
    return created


def deliver(order: SalesOrder, deliveries: dict) -> None:
    """Apply incremental deliveries. `deliveries` maps line_id -> qty delivered THIS event.

    Moves stock per event, then recomputes the order's delivered/partial/full status.
    """
    if order.status not in ("confirmed", "partially_delivered"):
        raise SalesError("Order must be Confirmed before delivering.")

    with atomic():
        moved = False
        for line in order.lines:
            add = Decimal(str(deliveries.get(line.id, 0) or 0))
            if add <= 0:
                continue
            remaining = Decimal(line.ordered_qty or 0) - Decimal(line.delivered_qty or 0)
            if add > remaining:
                raise SalesError(
                    f"Cannot deliver {add} of {line.product.name}; only {remaining} remain.")
            # P0 fix: move physical stock NOW for the incremental qty.
            inventory.record_movement(line.product, -add, "sales", order.reference)
            line.delivered_qty = Decimal(line.delivered_qty or 0) + add
            audit.log("sales", order.reference, "SalesOrderLine", "deliver",
                      field="delivered_qty", new_value=line.delivered_qty)
            moved = True

        if not moved:
            raise SalesError("Enter at least one delivery quantity.")

        fully = all(Decimal(l.delivered_qty or 0) >= Decimal(l.ordered_qty or 0)
                    for l in order.lines)
        _set_status(order, "fully_delivered" if fully else "partially_delivered")


def cancel(order: SalesOrder) -> None:
    """Cancel from Draft or Confirmed (before any delivery). Releases reservation."""
    if order.status not in ("draft", "confirmed"):
        raise SalesError("Only a Draft or Confirmed order can be cancelled.")
    if any(Decimal(l.delivered_qty or 0) > 0 for l in order.lines):
        raise SalesError("Cannot cancel an order that has deliveries.")
    with atomic():
        _set_status(order, "cancelled")
