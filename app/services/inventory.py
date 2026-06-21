"""Inventory engine: reserved quantity + on-hand movements + stock ledger.

The single source of truth for the quantity math in spec/inventory-and-stock-ledger.md:
    Free To Use = On Hand - Reserved
    Reserved = outstanding open SO lines + outstanding open MO components
On Hand moves only via record_movement() (the four triggers: receive / produce / consume / deliver).
"""
from decimal import Decimal

from flask_login import current_user
from sqlalchemy import func

from app.extensions import db
from app.models.logs import StockLedger
from app.models.manufacturing import MoComponent, ManufacturingOrder
from app.models.sales import SalesOrder, SalesOrderLine

# Order states that still hold a reservation (not yet fully fulfilled / cancelled).
_OPEN_SO = ("confirmed", "partially_delivered")
_OPEN_MO = ("confirmed", "in_progress")


def reserved_qty(product) -> Decimal:
    """Outstanding committed quantity for a product across open SOs and MOs."""
    total = Decimal(0)

    so_lines = (
        db.session.query(SalesOrderLine)
        .join(SalesOrder, SalesOrderLine.sales_order_id == SalesOrder.id)
        .filter(SalesOrderLine.product_id == product.id, SalesOrder.status.in_(_OPEN_SO))
        .all()
    )
    for line in so_lines:
        total += max(Decimal(line.ordered_qty or 0) - Decimal(line.delivered_qty or 0), Decimal(0))

    mo_comps = (
        db.session.query(MoComponent)
        .join(ManufacturingOrder, MoComponent.mo_id == ManufacturingOrder.id)
        .filter(MoComponent.product_id == product.id, ManufacturingOrder.status.in_(_OPEN_MO))
        .all()
    )
    for comp in mo_comps:
        total += max(Decimal(comp.to_consume or 0) - Decimal(comp.consumed_qty or 0), Decimal(0))

    return total


def reserved_qty_map() -> dict:
    """Reserved qty for ALL products in two aggregated queries (avoids N+1 on list views).

    Returns {product_id: Decimal}. Mirrors reserved_qty() exactly.
    """
    out: dict = {}

    so_q = (
        db.session.query(
            SalesOrderLine.product_id,
            func.sum(SalesOrderLine.ordered_qty - SalesOrderLine.delivered_qty),
        )
        .join(SalesOrder, SalesOrderLine.sales_order_id == SalesOrder.id)
        .filter(SalesOrder.status.in_(_OPEN_SO))
        .group_by(SalesOrderLine.product_id)
    )
    for pid, qty in so_q:
        out[pid] = out.get(pid, Decimal(0)) + max(Decimal(qty or 0), Decimal(0))

    mo_q = (
        db.session.query(
            MoComponent.product_id,
            func.sum(MoComponent.to_consume - MoComponent.consumed_qty),
        )
        .join(ManufacturingOrder, MoComponent.mo_id == ManufacturingOrder.id)
        .filter(ManufacturingOrder.status.in_(_OPEN_MO))
        .group_by(MoComponent.product_id)
    )
    for pid, qty in mo_q:
        out[pid] = out.get(pid, Decimal(0)) + max(Decimal(qty or 0), Decimal(0))

    return out


def record_movement(product, qty_delta: Decimal, source: str, source_ref: str) -> StockLedger:
    """Apply a signed On-Hand change and append a stock-ledger row. Caller commits.

    Concurrency-safe: takes a row-level lock on the product row before reading/writing
    `on_hand_qty` so two simultaneous receives/produces never overwrite each other.
    (SQLite serialises writes anyway; this matters on Postgres/MySQL — same code, real lock.)
    """
    qty_delta = Decimal(qty_delta)
    from app.models.product import Product
    # SELECT ... FOR UPDATE on the product row — fresh read inside the lock.
    locked = db.session.query(Product).filter(Product.id == product.id) \
        .with_for_update().one()
    locked.on_hand_qty = Decimal(locked.on_hand_qty or 0) + qty_delta
    # Keep the caller-passed `product` object in sync so callers reading it after see the new value.
    product.on_hand_qty = locked.on_hand_qty
    entry = StockLedger(
        product_id=locked.id,
        qty_delta=qty_delta,
        balance_after=locked.on_hand_qty,
        source=source,
        source_ref=source_ref,
        user_id=getattr(current_user, "id", None),
    )
    db.session.add(entry)
    return entry
