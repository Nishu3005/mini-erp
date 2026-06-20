"""Dashboard count logic. Builds the All/My status pills per the dashboard wireframe.

See spec/pages/user/dashboard.md. Derived (non-stored) buckets:
  - Sales/Purchase "Late": confirmed/partial whose expected_date has passed (model.is_late).
  - Manufacturing "To Close": in_progress (work effectively done, awaiting Produce/close).
Routes stay thin; this is the only place dashboard math lives.
"""
from datetime import datetime

from app.extensions import db
from app.models.manufacturing import ManufacturingOrder
from app.models.purchase import PurchaseOrder
from app.models.sales import SalesOrder


def _base_count(model, status, owner_field=None, owner_id=None):
    q = db.session.query(model).filter(model.status == status)
    if owner_field is not None:
        q = q.filter(owner_field == owner_id)
    return q.count()


def _late_count(model, open_statuses, owner_field=None, owner_id=None):
    q = db.session.query(model).filter(
        model.status.in_(open_statuses),
        model.expected_date.isnot(None),
        model.expected_date < datetime.utcnow(),
    )
    if owner_field is not None:
        q = q.filter(owner_field == owner_id)
    return q.count()


def sales_card(user):
    """All + My pill rows for Sales, matching the wireframe order."""
    of = SalesOrder.salesperson_id
    return {
        "all": [
            ("draft", "Draft", _base_count(SalesOrder, "draft")),
            ("confirmed", "Confirmed", _base_count(SalesOrder, "confirmed")),
            ("partially_delivered", "Partially Delivered",
             _base_count(SalesOrder, "partially_delivered")),
            ("fully_delivered", "Delivered", _base_count(SalesOrder, "fully_delivered")),
            ("late", "Late", _late_count(SalesOrder, ("confirmed", "partially_delivered"))),
        ],
        "my": [
            ("confirmed", "Confirmed", _base_count(SalesOrder, "confirmed", of, user.id)),
            ("draft", "Draft", _base_count(SalesOrder, "draft", of, user.id)),
            ("fully_delivered", "Delivered", _base_count(SalesOrder, "fully_delivered", of, user.id)),
        ],
    }


def purchase_card(user):
    of = PurchaseOrder.responsible_id
    return {
        "all": [
            ("draft", "Draft", _base_count(PurchaseOrder, "draft")),
            ("confirmed", "Confirmed", _base_count(PurchaseOrder, "confirmed")),
            ("partially_received", "Partially Received",
             _base_count(PurchaseOrder, "partially_received")),
            ("fully_received", "Received", _base_count(PurchaseOrder, "fully_received")),
            ("late", "Late", _late_count(PurchaseOrder, ("confirmed", "partially_received"))),
        ],
        "my": [
            ("confirmed", "Confirmed", _base_count(PurchaseOrder, "confirmed", of, user.id)),
            ("draft", "Draft", _base_count(PurchaseOrder, "draft", of, user.id)),
            ("fully_received", "Received", _base_count(PurchaseOrder, "fully_received", of, user.id)),
        ],
    }


def manufacturing_card(user):
    of = ManufacturingOrder.assignee_id
    # "To Close" = in_progress (production effectively done, awaiting the Produce/close step).
    return {
        "all": [
            ("draft", "Draft", _base_count(ManufacturingOrder, "draft")),
            ("confirmed", "Confirmed", _base_count(ManufacturingOrder, "confirmed")),
            ("in_progress", "In-Progress", _base_count(ManufacturingOrder, "in_progress")),
            ("to_close", "To Close", _base_count(ManufacturingOrder, "in_progress")),
            ("done", "Done", _base_count(ManufacturingOrder, "done")),
        ],
        "my": [
            ("confirmed", "Confirmed", _base_count(ManufacturingOrder, "confirmed", of, user.id)),
            ("in_progress", "In-Progress", _base_count(ManufacturingOrder, "in_progress", of, user.id)),
            ("done", "Done", _base_count(ManufacturingOrder, "done", of, user.id)),
        ],
    }
