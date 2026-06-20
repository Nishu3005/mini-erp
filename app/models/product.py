"""Product — the central inventory model.

On Hand is stored (cached, reconciled from stock_ledger). Reserved and Free-To-Use are computed.
See spec/inventory-and-stock-ledger.md and spec/pages/user/product/product.md.
"""
from decimal import Decimal

from app.extensions import db


class Product(db.Model):
    __tablename__ = "product"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(120), nullable=False)
    sales_price = db.Column(db.Numeric(12, 2), default=0)
    cost_price = db.Column(db.Numeric(12, 2), default=0)
    on_hand_qty = db.Column(db.Numeric(12, 2), default=0, nullable=False)

    procure_on_demand = db.Column(db.Boolean, default=False)
    procure_method = db.Column(db.String(20))                 # purchase / manufacturing
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor.id"))
    # use_alter breaks the product<->bom circular FK so DDL can be ordered/created cleanly.
    bom_id = db.Column(db.Integer, db.ForeignKey("bom.id", use_alter=True, name="fk_product_bom"))
    photo_path = db.Column(db.String(255))

    vendor = db.relationship("Vendor", lazy="joined")
    bom = db.relationship("Bom", foreign_keys=[bom_id], lazy="joined")

    @property
    def reserved_qty(self) -> Decimal:
        """Outstanding commitments from open SO lines and MO components.

        Computed lazily via the inventory service to keep the model free of query logic.
        """
        from app.services import inventory
        return inventory.reserved_qty(self)

    @property
    def free_to_use_qty(self) -> Decimal:
        return Decimal(self.on_hand_qty or 0) - self.reserved_qty

    def __repr__(self) -> str:
        return f"<Product {self.reference} {self.name}>"
