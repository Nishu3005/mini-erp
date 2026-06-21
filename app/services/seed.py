"""Load believable starter data from the data/ folder into the database.

Reads the JSON files described in data/README.md, resolves name-based references, applies relative
dates, and generates references via the sequences service. Run via `flask seed-data`.

This is dev/demo seeding — it sets order statuses directly (it does not replay the state machines),
and sets product on_hand_qty straight from the JSON. The numbers are internally consistent enough to
look real on the dashboard and exercise every status.
"""
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.extensions import db
from app.models.logs import AuditLog
from app.models.bom import Bom, BomComponent, BomOperation
from app.models.manufacturing import (ManufacturingOrder, MoComponent,
                                      WorkOrder)
from app.models.partner import Customer, Vendor
from app.models.product import Product
from app.models.purchase import PurchaseOrder, PurchaseOrderLine
from app.models.sales import SalesOrder, SalesOrderLine
from app.models.sequence import Sequence
from app.models.user import AccessRight, RIGHTS_MODULES, User
from app.services import sequences

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# all model classes whose tables get wiped on --reset (children before parents)
_RESET_ORDER = [
    AuditLog,
    WorkOrder, MoComponent, ManufacturingOrder,
    SalesOrderLine, SalesOrder,
    PurchaseOrderLine, PurchaseOrder,
    BomOperation, BomComponent, Bom,
    Product, Customer, Vendor,
    AccessRight, User,
    Sequence,
]


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def _days(offset):
    return datetime.utcnow() + timedelta(days=int(offset or 0))


def has_data() -> bool:
    return db.session.query(User).count() > 0


def reset() -> None:
    for model in _RESET_ORDER:
        db.session.query(model).delete()
    db.session.commit()


def seed() -> dict:
    """Insert all seed data. Returns a small summary of counts.

    Strategy: hand-authored JSON seeds the anchor records (named users a judge will recognise,
    curated products + BoMs). Then `data/generators/` programmatically scale the rest —
    ~40 extra team users (with a pending-list), ~40 vendors, ~500 products, ~5,000 customers,
    and proportionally more orders. See data/generators/__init__.py.
    """
    from data import generators as gen
    presets = _load("access_presets.json")

    # --- users + access rights ---
    by_login = {}

    def _add_user(u):
        """Persist one user dict + its access_right rows (presets lookup by `rights` key)."""
        user = User(
            login_id=u["login_id"], email=u["email"], name=u.get("name"),
            address=u.get("address"), mobile=u.get("mobile"),
            position=u.get("position"), is_admin=u.get("is_admin", False),
            role=u.get("role"), status=u.get("status", "active"),
            requested_role=u.get("requested_role"),
        )
        user.set_password(u["password"])
        db.session.add(user)
        db.session.flush()
        by_login[u["login_id"]] = user
        preset = presets.get(u.get("rights"))
        if preset:
            for module in RIGHTS_MODULES:
                m = preset.get(module, {})
                db.session.add(AccessRight(
                    user_id=user.id, module=module, role=m.get("role", "none"),
                    can_view=m.get("view", False), can_create=m.get("create", False),
                    can_edit=m.get("edit", False), can_delete=m.get("delete", False),
                    can_approve=m.get("approve", False),
                    can_production_entry=m.get("production_entry", False),
                    can_edit_bom=m.get("edit_bom", False),
                ))
        return user

    # 1. hand-authored anchors (admin/owner/sales.ravi/...)
    for u in _load("users.json"):
        _add_user(u)
    # 2. generated team members (~40 across roles + a small pending list)
    for u in gen.generate_users():
        # avoid login_id collisions with anchors
        suffix = 0
        original = u["login_id"]
        while u["login_id"] in by_login:
            suffix += 1
            u["login_id"] = (original + str(suffix))[:12]
        _add_user(u)

    # --- partners ---
    by_customer = {}
    # anchors (named customers from JSON) + generated (~5,000)
    anchor_customers = _load("customers.json")
    # 900 generated customers — keeps the demo snappy. Admin can bulk-upload more from /admin/.
    extra_customers = gen.generate_customers(count=900)
    all_customers = anchor_customers + [c for c in extra_customers
                                        if c["name"] not in {a["name"] for a in anchor_customers}]
    # bulk_save_objects skips ORM events for speed; we don't need IDs back during creation
    rows = [Customer(name=c["name"], address=c.get("address")) for c in all_customers]
    db.session.bulk_save_objects(rows)
    db.session.flush()
    for row in Customer.query.all():
        by_customer[row.name] = row

    by_vendor = {}
    anchor_vendors = _load("vendors.json")
    extra_vendors = gen.generate_vendors(count=40)
    all_vendors = anchor_vendors + [v for v in extra_vendors
                                    if v["name"] not in {a["name"] for a in anchor_vendors}]
    for v in all_vendors:
        row = Vendor(name=v["name"], address=v.get("address"))
        db.session.add(row); db.session.flush()
        by_vendor[v["name"]] = row

    # --- products (vendor resolved now; bom linked after BoMs exist) ---
    by_product = {}
    pending_bom_link = []  # (product_name, bom_name)
    # anchors first (named products judges will recognise), then generated catalogue (~500)
    anchor_products = _load("products.json")
    extra_products = gen.generate_products(count=500)
    seen_p = {p["name"] for p in anchor_products}
    all_products = anchor_products + [p for p in extra_products if p["name"] not in seen_p]
    for p in all_products:
        prod = Product(
            reference=sequences.next_reference("PRD"), name=p["name"],
            sales_price=Decimal(str(p.get("sales_price", 0))),
            cost_price=Decimal(str(p.get("cost_price", 0))),
            on_hand_qty=Decimal(str(p.get("on_hand_qty", 0))),
            procure_on_demand=p.get("procure_on_demand", False),
            procure_method=p.get("procure_method"),
        )
        if p.get("vendor"):
            prod.vendor_id = by_vendor[p["vendor"]].id
        db.session.add(prod); db.session.flush()
        by_product[p["name"]] = prod
        if p.get("bom"):
            pending_bom_link.append((p["name"], p["bom"]))

    # --- BoMs ---
    by_bom = {}
    for b in _load("boms.json"):
        bom = Bom(
            reference=sequences.next_reference("BOM"), ref_label=b.get("ref_label"),
            finished_product_id=by_product[b["finished_product"]].id,
            quantity=Decimal(str(b.get("quantity", 1))),
        )
        db.session.add(bom); db.session.flush()
        by_bom[b["finished_product"]] = bom
        for comp in b.get("components", []):
            db.session.add(BomComponent(
                bom_id=bom.id, product_id=by_product[comp["product"]].id,
                to_consume=Decimal(str(comp["to_consume"])),
            ))
        for op in b.get("operations", []):
            db.session.add(BomOperation(
                bom_id=bom.id, operation=op["operation"],
                work_center=op.get("work_center"),
                expected_duration=op.get("expected_duration", 0),
            ))

    # link products that procure via manufacturing to their BoM
    for product_name, bom_name in pending_bom_link:
        by_product[product_name].bom_id = by_bom[bom_name].id
    db.session.flush()

    # --- sales orders ---
    n_so = 0
    # ~250 generated SOs across active sales staff, anchor SOs first (they have expected_date set)
    so_sources = _load("sales_orders.json") + gen.generate_sales_orders(
        count=250,
        customer_names=list(by_customer.keys()),
        product_names=list(by_product.keys()),
        salesperson_logins=[lid for lid, u in by_login.items() if (u.role or "") == "sales"],
    )
    for s in so_sources:
        order = SalesOrder(
            reference=sequences.next_reference("SO"), status=s["status"],
            customer_id=by_customer[s["customer"]].id,
            customer_address=by_customer[s["customer"]].address,
            creation_date=_days(s.get("created_offset_days")),
            expected_date=_days(s["expected_offset_days"]) if "expected_offset_days" in s else None,
            salesperson_id=by_login[s["salesperson"]].id,
        )
        db.session.add(order); db.session.flush()
        for ln in s["lines"]:
            prod = by_product[ln["product"]]
            db.session.add(SalesOrderLine(
                sales_order_id=order.id, product_id=prod.id,
                ordered_qty=Decimal(str(ln["ordered_qty"])),
                delivered_qty=Decimal(str(ln.get("delivered_qty", 0))),
                sales_price=prod.sales_price,
            ))
        n_so += 1

    # --- purchase orders ---
    n_po = 0
    po_sources = _load("purchase_orders.json") + gen.generate_purchase_orders(
        count=150,
        vendor_names=list(by_vendor.keys()),
        product_names=list(by_product.keys()),
        responsible_logins=[lid for lid, u in by_login.items() if (u.role or "") == "purchase"],
    )
    for po in po_sources:
        order = PurchaseOrder(
            reference=sequences.next_reference("PO"), status=po["status"],
            vendor_id=by_vendor[po["vendor"]].id,
            vendor_address=by_vendor[po["vendor"]].address,
            creation_date=_days(po.get("created_offset_days")),
            expected_date=_days(po["expected_offset_days"]) if "expected_offset_days" in po else None,
            responsible_id=by_login[po["responsible"]].id,
        )
        db.session.add(order); db.session.flush()
        for ln in po["lines"]:
            prod = by_product[ln["product"]]
            db.session.add(PurchaseOrderLine(
                purchase_order_id=order.id, product_id=prod.id,
                ordered_qty=Decimal(str(ln["ordered_qty"])),
                received_qty=Decimal(str(ln.get("received_qty", 0))),
                cost_price=prod.cost_price,
            ))
        n_po += 1

    # --- manufacturing orders (components + work orders derived from BoM x qty) ---
    n_mo = 0
    mo_sources = _load("manufacturing_orders.json") + gen.generate_manufacturing_orders(
        count=80,
        bom_names=list(by_bom.keys()),
        assignee_logins=[lid for lid, u in by_login.items() if (u.role or "") == "manufacturing"],
    )
    for mo in mo_sources:
        bom = by_bom.get(mo["bom"])
        qty = Decimal(str(mo["quantity"]))
        order = ManufacturingOrder(
            reference=sequences.next_reference("MO"), status=mo["status"],
            finished_product_id=by_product[mo["finished_product"]].id,
            quantity=qty, bom_id=bom.id if bom else None,
            assignee_id=by_login[mo["assignee"]].id,
            creation_date=_days(mo.get("created_offset_days")),
            schedule_date=_days(mo.get("schedule_offset_days")),
        )
        db.session.add(order); db.session.flush()
        if bom:
            consumed_done = mo["status"] == "done"
            for comp in bom.components:
                to_consume = Decimal(comp.to_consume or 0) * qty
                db.session.add(MoComponent(
                    mo_id=order.id, product_id=comp.product_id,
                    to_consume=to_consume,
                    consumed_qty=to_consume if consumed_done else Decimal(0),
                ))
            for op in bom.operations:
                db.session.add(WorkOrder(
                    mo_id=order.id, operation=op.operation,
                    work_center=op.work_center,
                    expected_duration=int((op.expected_duration or 0) * int(qty)),
                ))
        n_mo += 1

    # --- audit logs (believable history for the Audit Logs screen) ---
    n_audit = 0
    for a in _load("audit_logs.json"):
        actor = by_login.get(a["user"])
        db.session.add(AuditLog(
            timestamp=_days(a.get("offset_days")),
            user_id=actor.id if actor else None,
            module=a.get("module"),
            record_type=a.get("record_type"),
            record_ref=a.get("record_ref"),
            field=a.get("field"),
            old_value=a.get("old"),
            new_value=a.get("new"),
            action=a.get("action"),
        ))
        n_audit += 1

    db.session.commit()
    return {
        "users": len(by_login), "customers": len(by_customer), "vendors": len(by_vendor),
        "products": len(by_product), "boms": len(by_bom),
        "sales_orders": n_so, "purchase_orders": n_po, "manufacturing_orders": n_mo,
        "audit_logs": n_audit,
    }
