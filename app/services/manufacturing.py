"""Manufacturing Order state machine. The ONLY place MO status changes.

State machine (spec/sequences-and-conventions.md §2):
    draft -> confirmed -> in_progress -> done
    draft|confirmed|in_progress -> cancelled

Stock rules (spec/inventory-and-stock-ledger.md §3b,§3c) on PRODUCE (-> done):
    - each component: On Hand DECREASES by consumed_qty (consumed)
    - finished product: On Hand INCREASES by MO quantity (produced)
Components reserved while confirmed/in_progress; released on done/cancel. This closes the other half
of "half-real inventory".
"""
from decimal import Decimal

from app.services import audit, inventory
from app.services.unitofwork import atomic


class ManufacturingError(ValueError):
    """Invalid transition; routes flash the message."""


def _set_status(order, new):
    old = order.status
    order.status = new
    audit.log("manufacturing", order.reference, "ManufacturingOrder", "status_change",
              field="status", old_value=old, new_value=new)


def confirm(order):
    if order.status != "draft":
        raise ManufacturingError("Only a Draft MO can be confirmed.")
    if not order.finished_product_id:
        raise ManufacturingError("A finished product is required.")
    with atomic():
        _set_status(order, "confirmed")


def start(order):
    if order.status != "confirmed":
        raise ManufacturingError("Only a Confirmed MO can be started.")
    with atomic():
        _set_status(order, "in_progress")


def produce(order, consumes: dict = None):
    """Finish the MO: consume components, produce the finished good. consumes maps comp_id->qty.

    If `consumes` is omitted, each component consumes its full to_consume.
    """
    if order.status not in ("confirmed", "in_progress"):
        raise ManufacturingError("MO must be Confirmed or In-Progress to produce.")
    consumes = consumes or {}

    with atomic():
        # consume components
        for comp in order.components:
            qty = consumes.get(comp.id)
            qty = Decimal(str(qty)) if qty not in (None, "") else Decimal(comp.to_consume or 0)
            if qty < 0:
                raise ManufacturingError("Consumed quantity cannot be negative.")
            if qty > 0:
                inventory.record_movement(comp.product, -qty, "manufacturing", order.reference)
                comp.consumed_qty = qty
                audit.log("manufacturing", order.reference, "MoComponent", "produce",
                          field="consumed_qty", new_value=qty)

        # produce finished good
        produced = Decimal(order.quantity or 0)
        if produced > 0:
            inventory.record_movement(order.finished_product, produced,
                                      "manufacturing", order.reference)
            audit.log("manufacturing", order.reference, "ManufacturingOrder", "produce",
                      field="produced_qty", new_value=produced)

        _set_status(order, "done")


def cancel(order):
    if order.status not in ("draft", "confirmed", "in_progress"):
        raise ManufacturingError("This MO can no longer be cancelled.")
    with atomic():
        _set_status(order, "cancelled")
