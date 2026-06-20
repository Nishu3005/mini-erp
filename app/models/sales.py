"""Sales Order + lines. See spec/pages/user/sales/sales.md."""
from datetime import datetime
from decimal import Decimal

from app.extensions import db

SO_STATUSES = ("draft", "confirmed", "partially_delivered", "fully_delivered", "cancelled")


class SalesOrder(db.Model):
    __tablename__ = "sales_order"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True)
    status = db.Column(db.String(24), default="draft", nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    customer_address = db.Column(db.String(255))
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_date = db.Column(db.DateTime)        # drives the dashboard "Late" derivation
    salesperson_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    customer = db.relationship("Customer", lazy="joined")
    salesperson = db.relationship("User", lazy="joined")
    lines = db.relationship(
        "SalesOrderLine", backref="order", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def total(self) -> Decimal:
        return sum((line.total for line in self.lines), Decimal(0))

    @property
    def is_late(self) -> bool:
        """Confirmed/partial with an expected date already in the past (dashboard 'Late')."""
        return (
            self.status in ("confirmed", "partially_delivered")
            and self.expected_date is not None
            and self.expected_date < datetime.utcnow()
        )

    def __repr__(self) -> str:
        return f"<SalesOrder {self.reference} {self.status}>"


class SalesOrderLine(db.Model):
    __tablename__ = "sales_order_line"

    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey("sales_order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    ordered_qty = db.Column(db.Numeric(12, 2), default=0)
    delivered_qty = db.Column(db.Numeric(12, 2), default=0)
    unit = db.Column(db.String(20), default="Units")
    sales_price = db.Column(db.Numeric(12, 2), default=0)

    product = db.relationship("Product", lazy="joined")

    @property
    def outstanding_qty(self) -> Decimal:
        return Decimal(self.ordered_qty or 0) - Decimal(self.delivered_qty or 0)

    @property
    def total(self) -> Decimal:
        qty = self.delivered_qty if self.order and self.order.status in (
            "partially_delivered", "fully_delivered") else self.ordered_qty
        return Decimal(qty or 0) * Decimal(self.sales_price or 0)

    @property
    def availability(self) -> bool:
        """True when there is a shortage (ordered > free-to-use)."""
        return Decimal(self.ordered_qty or 0) > self.product.free_to_use_qty
