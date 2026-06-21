"""Admin bulk-import: upload a JSON file of customers, vendors or products.

Each entry is upserted by `name` — duplicates are skipped (idempotent). Products go through the
sequence service for auto-references; partner records (customers/vendors) just take name + address.

Schema (a JSON array of objects):
  customers / vendors: [{"name": "...", "address": "..."}, ...]
  products:            [{"name": "...", "sales_price": 0, "cost_price": 0, "on_hand_qty": 0,
                         "procure_on_demand": false}, ...]
"""
import json
from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.models.partner import Customer, Vendor
from app.models.product import Product
from app.services import audit, sequences
from app.services.unitofwork import InputError, atomic


SUPPORTED = {"customers", "vendors", "products"}


def import_json(dataset: str, payload: str | bytes) -> dict:
    """Parse + import a JSON payload for the given dataset. Returns counts: added/skipped/errors."""
    if dataset not in SUPPORTED:
        raise InputError(f"Unknown dataset '{dataset}'. Choose one of: {sorted(SUPPORTED)}.")
    try:
        rows = json.loads(payload)
    except (ValueError, TypeError):
        raise InputError("File is not valid JSON.")
    if not isinstance(rows, list):
        raise InputError("JSON must be an array of records.")
    if dataset == "customers":
        return _import_partners(rows, Customer, "customer")
    if dataset == "vendors":
        return _import_partners(rows, Vendor, "vendor")
    return _import_products(rows)


def _import_partners(rows, Model, label):
    """Upsert customers or vendors by name."""
    existing = {r.name for r in Model.query.all()}
    added = skipped = 0
    errors = []
    with atomic():
        for i, r in enumerate(rows, start=1):
            if not isinstance(r, dict) or not (r.get("name") or "").strip():
                errors.append(f"row {i}: missing 'name'"); continue
            name = r["name"].strip()
            if name in existing:
                skipped += 1; continue
            db.session.add(Model(name=name, address=(r.get("address") or "").strip() or None))
            existing.add(name)
            added += 1
        if added:
            audit.log("audit", f"bulk:{label}", "BulkImport", "create",
                      field=label, new_value=f"+{added}")
    return {"added": added, "skipped": skipped, "errors": errors[:20], "error_count": len(errors)}


def _import_products(rows):
    """Upsert products by name (refs auto-generated)."""
    existing = {p.name for p in Product.query.all()}
    added = skipped = 0
    errors = []
    with atomic():
        for i, r in enumerate(rows, start=1):
            if not isinstance(r, dict) or not (r.get("name") or "").strip():
                errors.append(f"row {i}: missing 'name'"); continue
            name = r["name"].strip()
            if name in existing:
                skipped += 1; continue
            try:
                p = Product(
                    reference=sequences.next_reference("PRD"),
                    name=name,
                    sales_price=_dec(r.get("sales_price", 0)),
                    cost_price=_dec(r.get("cost_price", 0)),
                    on_hand_qty=_dec(r.get("on_hand_qty", 0)),
                    procure_on_demand=bool(r.get("procure_on_demand", False)),
                    procure_method=r.get("procure_method"),
                )
            except InputError as e:
                errors.append(f"row {i} ({name}): {e}"); continue
            db.session.add(p)
            existing.add(name)
            added += 1
        if added:
            audit.log("audit", "bulk:product", "BulkImport", "create",
                      field="product", new_value=f"+{added}")
    return {"added": added, "skipped": skipped, "errors": errors[:20], "error_count": len(errors)}


def _dec(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        raise InputError(f"'{v}' is not a valid number")
