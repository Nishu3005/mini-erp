"""Product service: create/update with procurement-config validation + audit.

See spec/pages/user/product/product.md and spec/inventory-and-stock-ledger.md §6.
Business rules (validation) live here, not in routes.
"""
from decimal import Decimal

from app.extensions import db
from app.models.product import Product
from app.services import audit, sequences


class ProductError(ValueError):
    """Raised on invalid product data; routes turn this into a flash message."""


def _validate(data: dict) -> None:
    if not (data.get("name") or "").strip():
        raise ProductError("Product name is required.")
    for field in ("sales_price", "cost_price", "on_hand_qty"):
        if Decimal(str(data.get(field) or 0)) < 0:
            raise ProductError(f"{field.replace('_', ' ').title()} cannot be negative.")
    if data.get("procure_on_demand"):
        method = data.get("procure_method")
        if method not in ("purchase", "manufacturing"):
            raise ProductError("Choose a procurement method (Purchase or Manufacturing).")
        if method == "purchase" and not data.get("vendor_id"):
            raise ProductError("Vendor is required when procurement method is Purchase.")
        if method == "manufacturing" and not data.get("bom_id"):
            raise ProductError("BoM is required when procurement method is Manufacturing.")


def create(data: dict) -> Product:
    _validate(data)
    p = Product(
        reference=sequences.next_reference("PRD"),
        name=data["name"].strip(),
        sales_price=Decimal(str(data.get("sales_price") or 0)),
        cost_price=Decimal(str(data.get("cost_price") or 0)),
        on_hand_qty=Decimal(str(data.get("on_hand_qty") or 0)),
        procure_on_demand=bool(data.get("procure_on_demand")),
        procure_method=data.get("procure_method") if data.get("procure_on_demand") else None,
        vendor_id=data.get("vendor_id") if data.get("procure_method") == "purchase" else None,
        bom_id=data.get("bom_id") if data.get("procure_method") == "manufacturing" else None,
    )
    db.session.add(p)
    db.session.flush()
    audit.log("product", p.reference, "Product", "create")
    db.session.commit()
    return p


def update(product: Product, data: dict) -> Product:
    _validate(data)
    tracked = {
        "name": data["name"].strip(),
        "sales_price": Decimal(str(data.get("sales_price") or 0)),
        "cost_price": Decimal(str(data.get("cost_price") or 0)),
        "on_hand_qty": Decimal(str(data.get("on_hand_qty") or 0)),
        "procure_on_demand": bool(data.get("procure_on_demand")),
    }
    for field, new in tracked.items():
        old = getattr(product, field)
        if str(old) != str(new):
            audit.log("product", product.reference, "Product", "write",
                      field=field, old_value=old, new_value=new)
            setattr(product, field, new)

    product.procure_method = data.get("procure_method") if product.procure_on_demand else None
    product.vendor_id = data.get("vendor_id") if product.procure_method == "purchase" else None
    product.bom_id = data.get("bom_id") if product.procure_method == "manufacturing" else None

    db.session.commit()
    return product
