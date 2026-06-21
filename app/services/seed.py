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
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
AVATAR_SRC_DIR = DATA_DIR / "avatars"
AVATAR_DST_DIR = STATIC_DIR / "uploads" / "avatars" / "seed"


def _install_seed_avatars() -> list[str]:
    """Copy data/avatars/avatar_*.jpg into static/uploads/avatars/seed/ exactly once.

    Returns the list of `photo_path` values (relative to /static/) ready to assign to users.
    If data/avatars/ is missing or empty (the user never ran fetch_avatars.py), returns [].
    """
    import shutil
    if not AVATAR_SRC_DIR.is_dir():
        return []
    sources = sorted(AVATAR_SRC_DIR.glob("avatar_*.jpg"))
    if not sources:
        return []
    AVATAR_DST_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for src in sources:
        dst = AVATAR_DST_DIR / src.name
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copyfile(src, dst)
        paths.append(f"uploads/avatars/seed/{src.name}")
    return paths

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


def _load_generated_list(name: str) -> list:
    """Return data/generated/<name> as a list, or [] if the file is missing/invalid."""
    p = DATA_DIR / "generated" / name
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []


def _load_with_generated(name: str, key: str = "name") -> list:
    """Anchor JSON + (optional) data/generated/<name> appended, de-duped by `key`.

    The seed is two-step (see services/gendata.py): generators write to data/generated/<name>.json,
    then this loader merges them with the hand-authored anchors. Anchors win on duplicates.
    """
    rows = _load(name)
    gen_path = DATA_DIR / "generated" / name
    if gen_path.exists():
        try:
            extra = json.loads(gen_path.read_text(encoding="utf-8"))
            seen = {r.get(key) for r in rows}
            rows = rows + [r for r in extra if r.get(key) not in seen]
        except (ValueError, OSError):
            pass
    return rows


def _days(offset):
    return datetime.utcnow() + timedelta(days=int(offset or 0))


def _tables_exist() -> bool:
    """True iff the core `user` table exists in the live DB."""
    from sqlalchemy import inspect
    return inspect(db.engine).has_table("user")


def has_data() -> bool:
    if not _tables_exist():
        return False
    return db.session.query(User).count() > 0


def reset() -> None:
    """Wipe all rows. If tables don't exist (fresh / corrupted DB), create them first."""
    if not _tables_exist():
        db.create_all()
        return
    for model in _RESET_ORDER:
        db.session.query(model).delete()
    db.session.commit()


def seed() -> dict:
    """Bulk-insert all seed data from data/*.json + data/generated/*.json. FAST."""
    import time
    _T = {"start": time.perf_counter()}
    def _tick(name):
        now = time.perf_counter()
        elapsed = now - _T.get("last", _T["start"])
        _T["last"] = now
        print(f"  [seed] {name:24} +{elapsed:6.2f}s  (total {now - _T['start']:6.2f}s)", flush=True)

    presets = _load("access_presets.json")
    _tick("load presets")

    # Seed passwords use a FAST hash method (pbkdf2:sha256:1 iteration). The default takes ~5s per
    # password on Windows for cryptographic safety — but for seed/demo passwords users will reset,
    # the security tradeoff is acceptable and turns a 3-minute seed into a sub-second one.
    from werkzeug.security import generate_password_hash
    _FAST_HASH = "pbkdf2:sha256:1"
    def _fast_set_password(user, raw: str) -> None:
        user.password_hash = generate_password_hash(raw, method=_FAST_HASH)

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
        _fast_set_password(user, u["password"])
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

    # 1) Hand-authored anchors (the 8 named users a judge will recognise).
    # 2) Generated team members (15 extra, inline — no separate JSON files, no two-step).
    from data import generators as gen
    for u in _load("users.json") + gen.generate_users():
        # avoid login_id collisions safely
        original = u["login_id"]
        suffix = 0
        while u["login_id"] in by_login:
            suffix += 1
            u["login_id"] = (original + str(suffix))[:12]
        _add_user(u)

    # Avatars: copy the 40 fetched portraits into static/ and round-robin them across users.
    # No-op if data/avatars/ is empty — users just keep the default smiley.
    avatar_paths = _install_seed_avatars()
    if avatar_paths:
        for i, user in enumerate(by_login.values()):
            user.photo_path = avatar_paths[i % len(avatar_paths)]

    db.session.flush(); _tick("users + rights")
    # --- partners: anchors + generated (compact demo: 20 vendors, ~300 customers) ---
    anchor_customers = _load("customers.json")
    extra_customers = gen.generate_customers(count=300)
    anchor_cnames = {c["name"] for c in anchor_customers}
    all_customers = anchor_customers + [c for c in extra_customers if c["name"] not in anchor_cnames]
    db.session.bulk_save_objects([Customer(name=c["name"], address=c.get("address"))
                                  for c in all_customers])

    anchor_vendors = _load("vendors.json")
    extra_vendors = gen.generate_vendors(count=20)
    anchor_vnames = {v["name"] for v in anchor_vendors}
    all_vendors = anchor_vendors + [v for v in extra_vendors if v["name"] not in anchor_vnames]
    db.session.bulk_save_objects([Vendor(name=v["name"], address=v.get("address"))
                                  for v in all_vendors])

    db.session.flush()
    by_customer = {row.name: row for row in Customer.query.all()}
    by_vendor = {row.name: row for row in Vendor.query.all()}

    _tick("partners")
    # --- products: anchors + ~50 generated (compact demo) ---
    pending_bom_link = []  # (product_name, bom_name)
    anchor_products = _load("products.json")
    extra_products = gen.generate_products(count=50)
    anchor_pnames = {p["name"] for p in anchor_products}
    products = anchor_products + [p for p in extra_products if p["name"] not in anchor_pnames]

    # Pre-allocate references in one batch — one sequence call instead of one-per-product.
    from app.models.sequence import Sequence
    seq = db.session.query(Sequence).filter_by(prefix="PRD").with_for_update().one_or_none()
    if seq is None:
        seq = Sequence(prefix="PRD", next_value=1); db.session.add(seq); db.session.flush()
    first_num = seq.next_value
    seq.next_value = first_num + len(products)
    db.session.flush()

    product_rows = []
    for i, p in enumerate(products):
        product_rows.append(Product(
            reference=f"PRD-{first_num + i:06d}", name=p["name"],
            sales_price=Decimal(str(p.get("sales_price", 0))),
            cost_price=Decimal(str(p.get("cost_price", 0))),
            on_hand_qty=Decimal(str(p.get("on_hand_qty", 0))),
            procure_on_demand=p.get("procure_on_demand", False),
            procure_method=p.get("procure_method"),
            vendor_id=by_vendor[p["vendor"]].id if p.get("vendor") else None,
        ))
        if p.get("bom"):
            pending_bom_link.append((p["name"], p["bom"]))
    db.session.bulk_save_objects(product_rows)
    db.session.flush()
    by_product = {row.name: row for row in Product.query.all()}

    _tick("products")
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

    _tick("boms")
    # --- sales orders ---
    n_so = 0
    # anchors (curated, with expected_date) + 25 inline-generated sales orders
    so_sources = _load("sales_orders.json") + gen.generate_sales_orders(
        count=25,
        customer_names=list(by_customer.keys()),
        product_names=list(by_product.keys()),
        salesperson_logins=[lid for lid, u in by_login.items()
                            if (u.role or "") == "sales" and u.status == "active"] or [next(iter(by_login))],
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

    _tick("sales orders")
    # --- purchase orders ---
    n_po = 0
    po_sources = _load("purchase_orders.json") + gen.generate_purchase_orders(
        count=15,
        vendor_names=list(by_vendor.keys()),
        product_names=list(by_product.keys()),
        responsible_logins=[lid for lid, u in by_login.items()
                            if (u.role or "") == "purchase" and u.status == "active"] or [next(iter(by_login))],
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

    _tick("purchase orders")
    # --- manufacturing orders (components + work orders derived from BoM x qty) ---
    n_mo = 0
    mo_sources = _load("manufacturing_orders.json") + gen.generate_manufacturing_orders(
        count=8,
        bom_names=list(by_bom.keys()),
        assignee_logins=[lid for lid, u in by_login.items()
                         if (u.role or "") == "manufacturing" and u.status == "active"] or [next(iter(by_login))],
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

    _tick("manufacturing orders")
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

    _tick("audit logs")
    db.session.commit()
    _tick("commit")
    return {
        "users": len(by_login), "customers": len(by_customer), "vendors": len(by_vendor),
        "products": len(by_product), "boms": len(by_bom),
        "sales_orders": n_so, "purchase_orders": n_po, "manufacturing_orders": n_mo,
        "audit_logs": n_audit,
    }
