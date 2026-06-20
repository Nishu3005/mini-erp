"""Bill of Materials template + components + operations. See spec/pages/user/bom/bom.md."""
from app.extensions import db


class Bom(db.Model):
    __tablename__ = "bom"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True)
    ref_label = db.Column(db.String(8))                  # user-entered, max 8 chars
    finished_product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), default=1)

    finished_product = db.relationship("Product", foreign_keys=[finished_product_id], lazy="joined")
    components = db.relationship(
        "BomComponent", backref="bom", cascade="all, delete-orphan", lazy="selectin"
    )
    operations = db.relationship(
        "BomOperation", backref="bom", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Bom {self.reference}>"


class BomComponent(db.Model):
    __tablename__ = "bom_component"

    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, db.ForeignKey("bom.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    to_consume = db.Column(db.Numeric(12, 2), default=0)
    unit = db.Column(db.String(20), default="Units")

    product = db.relationship("Product", lazy="joined")


class BomOperation(db.Model):
    __tablename__ = "bom_operation"

    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, db.ForeignKey("bom.id"), nullable=False)
    operation = db.Column(db.String(120))
    work_center = db.Column(db.String(120))
    expected_duration = db.Column(db.Integer, default=0)   # minutes per 1 unit
