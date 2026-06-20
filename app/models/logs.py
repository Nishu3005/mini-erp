"""Audit log (who changed what) and stock ledger (physical movements).

Both are append-only. See spec/pages/user/audit-logs.md and spec/inventory-and-stock-ledger.md.
"""
from datetime import datetime

from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    module = db.Column(db.String(20), index=True)
    record_ref = db.Column(db.String(40))
    record_type = db.Column(db.String(40))
    field = db.Column(db.String(60))
    old_value = db.Column(db.String(255))
    new_value = db.Column(db.String(255))
    action = db.Column(db.String(20))

    user = db.relationship("User", lazy="joined")


class StockLedger(db.Model):
    __tablename__ = "stock_ledger"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    qty_delta = db.Column(db.Numeric(12, 2))
    balance_after = db.Column(db.Numeric(12, 2))
    source = db.Column(db.String(20))                  # purchase/manufacturing/sales/adjustment
    source_ref = db.Column(db.String(40))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    product = db.relationship("Product", lazy="joined")
