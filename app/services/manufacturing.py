"""Manufacturing Order state machine — and the per-Work-Order operator state machine.

MO transitions (spec/sequences-and-conventions.md §2):
    draft -> confirmed -> in_progress -> done
    draft|confirmed|in_progress -> cancelled

WO transitions (Finding D — operator routing):
    todo -> in_progress -> done

`produce()` is GATED on all WOs being `done`. This makes Work Orders real, not decorative.
Stock rules unchanged (consume components, produce finished good on PRODUCE).
"""
from datetime import datetime
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
    GATED: every Work Order must be in `done` state (Finding D — operator routing).
    """
    if order.status not in ("confirmed", "in_progress"):
        raise ManufacturingError("MO must be Confirmed or In-Progress to produce.")
    # Block produce until every Work Order is done. MOs with no WOs are allowed (old behavior).
    if order.work_orders and not order.all_work_orders_done:
        pending = sum(1 for w in order.work_orders if w.status != "done")
        raise ManufacturingError(
            f"Cannot produce: {pending} work order(s) still pending. "
            "Operators must Start and Finish each work order first.")
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


# ---------- per-Work-Order operator routing (Finding D) ----------

def start_work_order(wo, *, by_user_id=None):
    """Operator clicks Start on a WO. MO must be in_progress (we promote from confirmed)."""
    if wo.status == "done":
        raise ManufacturingError("This work order is already done.")
    if wo.status == "in_progress":
        return  # idempotent: already started
    if wo.order.status == "confirmed":
        # promote the MO automatically — a started WO implies production is in progress
        _set_status(wo.order, "in_progress")
    elif wo.order.status != "in_progress":
        raise ManufacturingError("The manufacturing order must be Confirmed or In-Progress.")
    with atomic():
        wo.status = "in_progress"
        wo.started_at = datetime.utcnow()
        if by_user_id is not None and wo.assignee_id is None:
            wo.assignee_id = by_user_id
        audit.log("manufacturing", wo.order.reference, "WorkOrder", "status_change",
                  field=f"wo[{wo.operation}].status", old_value="todo", new_value="in_progress")


def finish_work_order(wo, *, real_duration_minutes: int | None = None):
    """Operator clicks Finish. Captures real_duration (override or auto from started_at)."""
    if wo.status == "done":
        return                                     # idempotent
    if wo.status != "in_progress":
        raise ManufacturingError("Start the work order before finishing it.")
    with atomic():
        wo.finished_at = datetime.utcnow()
        if real_duration_minutes is not None and real_duration_minutes >= 0:
            wo.real_duration = int(real_duration_minutes)
        elif wo.started_at:
            wo.real_duration = max(1, int((wo.finished_at - wo.started_at).total_seconds() / 60))
        wo.status = "done"
        audit.log("manufacturing", wo.order.reference, "WorkOrder", "status_change",
                  field=f"wo[{wo.operation}].status", old_value="in_progress", new_value="done",
                  )
        audit.log("manufacturing", wo.order.reference, "WorkOrder", "write",
                  field=f"wo[{wo.operation}].real_duration", new_value=wo.real_duration)


def assign_work_order(wo, user_id: int):
    """Reassign a WO to a different operator."""
    with atomic():
        old = wo.assignee_id
        wo.assignee_id = user_id
        audit.log("manufacturing", wo.order.reference, "WorkOrder", "write",
                  field=f"wo[{wo.operation}].assignee", old_value=old, new_value=user_id)
