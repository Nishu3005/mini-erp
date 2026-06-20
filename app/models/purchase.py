"""Purchase Order + lines. See spec/pages/user/purchase/purchase.md."""
from datetime import datetime
from decimal import Decimal

from app.extensions import db

PO_STATUSES = ("draft", "confirmed", "partially_received", "fully_received", "cancelled")


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_order"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True)
    status = db.Column(db.String(24), default="draft", nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor.id"), nullable=False)
    vendor_address = db.Column(db.String(255))
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_date = db.Column(db.DateTime)        # drives the dashboard "Late" derivation
    responsible_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    vendor = db.relationship("Vendor", lazy="joined")
    responsible = db.relationship("User", lazy="joined")
    lines = db.relationship(
        "PurchaseOrderLine", backref="order", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def total(self) -> Decimal:
        return sum((line.total for line in self.lines), Decimal(0))

    @property
    def is_late(self) -> bool:
        """Confirmed/partial with an expected date already in the past (dashboard 'Late')."""
        return (
            self.status in ("confirmed", "partially_received")
            and self.expected_date is not None
            and self.expected_date < datetime.utcnow()
        )

    def __repr__(self) -> str:
        return f"<PurchaseOrder {self.reference} {self.status}>"


class PurchaseOrderLine(db.Model):
    __tablename__ = "purchase_order_line"

    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    ordered_qty = db.Column(db.Numeric(12, 2), default=0)
    received_qty = db.Column(db.Numeric(12, 2), default=0)
    unit = db.Column(db.String(20), default="Units")
    cost_price = db.Column(db.Numeric(12, 2), default=0)

    product = db.relationship("Product", lazy="joined")

    @property
    def outstanding_qty(self) -> Decimal:
        return Decimal(self.ordered_qty or 0) - Decimal(self.received_qty or 0)

    @property
    def total(self) -> Decimal:
        qty = self.received_qty if self.order and self.order.status in (
            "partially_received", "fully_received") else self.ordered_qty
        return Decimal(qty or 0) * Decimal(self.cost_price or 0)
