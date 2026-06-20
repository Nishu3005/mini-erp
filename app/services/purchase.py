"""Purchase Order state machine. The ONLY place PO status changes.

State machine (spec/sequences-and-conventions.md §2):
    draft -> confirmed -> partially_received -> fully_received
    draft|confirmed -> cancelled

Stock rule (spec/inventory-and-stock-ledger.md §3a): on each Receive event, On Hand INCREASES by the
qty received this event (per-event movement), each writing a stock-ledger row. This closes the
"half-real inventory" gap — purchase receiving now actually moves stock.
"""
from decimal import Decimal

from app.models.purchase import PurchaseOrder
from app.services import audit, inventory
from app.services.unitofwork import InputError, atomic


class PurchaseError(ValueError):
    """Invalid transition; routes flash the message."""


def _set_status(order, new):
    old = order.status
    order.status = new
    audit.log("purchase", order.reference, "PurchaseOrder", "status_change",
              field="status", old_value=old, new_value=new)


def confirm(order):
    if order.status != "draft":
        raise PurchaseError("Only a Draft order can be confirmed.")
    if not order.lines:
        raise PurchaseError("Cannot confirm an order with no product lines.")
    with atomic():
        _set_status(order, "confirmed")


def receive(order, receipts: dict):
    """Apply incremental receipts. `receipts` maps line_id -> qty received THIS event."""
    if order.status not in ("confirmed", "partially_received"):
        raise PurchaseError("Order must be Confirmed before receiving.")

    with atomic():
        moved = False
        for line in order.lines:
            add = Decimal(str(receipts.get(line.id, 0) or 0))
            if add <= 0:
                continue
            remaining = Decimal(line.ordered_qty or 0) - Decimal(line.received_qty or 0)
            if add > remaining:
                raise PurchaseError(
                    f"Cannot receive {add} of {line.product.name}; only {remaining} remain.")
            # Stock IN for the incremental qty.
            inventory.record_movement(line.product, add, "purchase", order.reference)
            line.received_qty = Decimal(line.received_qty or 0) + add
            audit.log("purchase", order.reference, "PurchaseOrderLine", "receive",
                      field="received_qty", new_value=line.received_qty)
            moved = True

        if not moved:
            raise PurchaseError("Enter at least one received quantity.")

        fully = all(Decimal(l.received_qty or 0) >= Decimal(l.ordered_qty or 0)
                    for l in order.lines)
        _set_status(order, "fully_received" if fully else "partially_received")


def cancel(order):
    if order.status not in ("draft", "confirmed"):
        raise PurchaseError("Only a Draft or Confirmed order can be cancelled.")
    if any(Decimal(l.received_qty or 0) > 0 for l in order.lines):
        raise PurchaseError("Cannot cancel an order that has receipts.")
    with atomic():
        _set_status(order, "cancelled")
