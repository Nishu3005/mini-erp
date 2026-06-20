"""Customer and Vendor reference tables. See spec/database-schema.md."""
from app.extensions import db


class Customer(db.Model):
    __tablename__ = "customer"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255))

    def __repr__(self) -> str:
        return f"<Customer {self.name}>"


class Vendor(db.Model):
    __tablename__ = "vendor"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255))

    def __repr__(self) -> str:
        return f"<Vendor {self.name}>"
