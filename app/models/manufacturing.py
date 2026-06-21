"""Manufacturing Order + components + work orders. See spec/pages/user/manufacturing/manufacturing.md."""
from datetime import datetime
from decimal import Decimal

from app.extensions import db

MO_STATUSES = ("draft", "confirmed", "in_progress", "done", "cancelled")


class ManufacturingOrder(db.Model):
    __tablename__ = "manufacturing_order"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True)
    status = db.Column(db.String(24), default="draft", nullable=False)
    finished_product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), default=0)
    bom_id = db.Column(db.Integer, db.ForeignKey("bom.id"))
    assignee_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    schedule_date = db.Column(db.DateTime)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)

    finished_product = db.relationship("Product", foreign_keys=[finished_product_id], lazy="joined")
    bom = db.relationship("Bom", lazy="joined")
    assignee = db.relationship("User", lazy="joined")
    components = db.relationship(
        "MoComponent", backref="order", cascade="all, delete-orphan", lazy="selectin"
    )
    work_orders = db.relationship(
        "WorkOrder", backref="order", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def component_status(self) -> str:
        """'Available' only if every component has enough free-to-use stock."""
        for c in self.components:
            if c.product.free_to_use_qty < Decimal(c.to_consume or 0):
                return "Not Available"
        return "Available"

    @property
    def all_work_orders_done(self) -> bool:
        """True when there are no WOs, or every WO is in `done` state. Produce gate."""
        return all(w.status == "done" for w in self.work_orders)

    @property
    def work_order_progress(self) -> str:
        """e.g. '2/5' — for the MO list view's at-a-glance progress."""
        total = len(self.work_orders)
        if not total:
            return "—"
        done = sum(1 for w in self.work_orders if w.status == "done")
        return f"{done}/{total}"

    def __repr__(self) -> str:
        return f"<ManufacturingOrder {self.reference} {self.status}>"


class MoComponent(db.Model):
    __tablename__ = "mo_component"

    id = db.Column(db.Integer, primary_key=True)
    mo_id = db.Column(db.Integer, db.ForeignKey("manufacturing_order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    to_consume = db.Column(db.Numeric(12, 2), default=0)
    consumed_qty = db.Column(db.Numeric(12, 2), default=0)
    unit = db.Column(db.String(20), default="Units")

    product = db.relationship("Product", lazy="joined")

    @property
    def availability(self) -> str:
        return "Available" if self.product.free_to_use_qty >= Decimal(self.to_consume or 0) \
            else "Not Available"


class WorkOrder(db.Model):
    __tablename__ = "work_order"

    id = db.Column(db.Integer, primary_key=True)
    mo_id = db.Column(db.Integer, db.ForeignKey("manufacturing_order.id"), nullable=False)
    operation = db.Column(db.String(120))
    work_center = db.Column(db.String(120))
    expected_duration = db.Column(db.Integer, default=0)   # minutes (scaled by MO qty)
    real_duration = db.Column(db.Integer, default=0)       # auto-captured at Finish

    # ---- per-WO operator routing (Finding D) ----
    status = db.Column(db.String(16), default="todo", nullable=False)  # todo/in_progress/done
    assignee_id = db.Column(db.Integer, db.ForeignKey("user.id"))      # operator (optional)
    started_at = db.Column(db.DateTime)                                # set on Start
    finished_at = db.Column(db.DateTime)                               # set on Finish

    assignee = db.relationship("User", lazy="joined")
