"""Two-step seed workflow — STEP 1: generate JSON into `data/generated/`.

`flask gen-data` runs this. `flask seed-data` then bulk-inserts those JSON files into the DB.
Splitting the slow programmatic generation from the fast bulk-insert keeps demos snappy and the
generated rows inspectable / editable / committable on disk.

Counts are deliberately modest so this completes in <1s (no need to wait when reseeding).
"""
import json
from pathlib import Path

from data import generators as gen

OUT = Path(__file__).resolve().parents[2] / "data" / "generated"

# tunable in one place
COUNTS = {
    "customers": 100,
    "vendors":   20,
    "products":  60,
    "sales_orders":         20,
    "purchase_orders":      15,
    "manufacturing_orders": 10,
}


def _anchors():
    """Read the hand-authored anchor JSON to know which users/customers/products/boms exist."""
    base = OUT.parent
    def L(name): return json.loads((base / name).read_text(encoding="utf-8"))
    return {
        "users":     L("users.json"),
        "customers": L("customers.json"),
        "vendors":   L("vendors.json"),
        "products":  L("products.json"),
        "boms":      L("boms.json"),
    }


def _write(name: str, rows: list) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return len(rows)


def generate_all() -> dict:
    anchors = _anchors()
    anchor_customer_names = [c["name"] for c in anchors["customers"]]
    anchor_vendor_names   = [v["name"] for v in anchors["vendors"]]
    anchor_product_names  = [p["name"] for p in anchors["products"]]
    bom_names             = [b["finished_product"] for b in anchors["boms"]]

    extra_users = gen.generate_users()
    user_logins = [u["login_id"] for u in anchors["users"]] + [u["login_id"] for u in extra_users]
    # active sales / purchase / manufacturing user logins (for order ownership)
    def _logins_for(role: str) -> list:
        return [u["login_id"] for u in extra_users
                if u.get("role") == role and u.get("status") == "active"] \
               + [u["login_id"] for u in anchors["users"]
                  if u.get("rights") == role]

    extra_customers = gen.generate_customers(count=COUNTS["customers"])
    extra_vendors   = gen.generate_vendors(count=COUNTS["vendors"])
    extra_products  = gen.generate_products(count=COUNTS["products"])

    # de-dup by name against anchors
    extra_customers = [c for c in extra_customers if c["name"] not in set(anchor_customer_names)]
    extra_vendors   = [v for v in extra_vendors   if v["name"] not in set(anchor_vendor_names)]
    extra_products  = [p for p in extra_products  if p["name"] not in set(anchor_product_names)]

    # orders reference real names; sample from anchors+generated
    all_customer_names = anchor_customer_names + [c["name"] for c in extra_customers]
    all_product_names  = anchor_product_names  + [p["name"] for p in extra_products]
    all_vendor_names   = anchor_vendor_names   + [v["name"] for v in extra_vendors]

    so = gen.generate_sales_orders(
        count=COUNTS["sales_orders"],
        customer_names=all_customer_names, product_names=all_product_names,
        salesperson_logins=_logins_for("sales") or user_logins[:1])
    po = gen.generate_purchase_orders(
        count=COUNTS["purchase_orders"],
        vendor_names=all_vendor_names, product_names=all_product_names,
        responsible_logins=_logins_for("purchase") or user_logins[:1])
    mo = gen.generate_manufacturing_orders(
        count=COUNTS["manufacturing_orders"],
        bom_names=bom_names, assignee_logins=_logins_for("manufacturing") or user_logins[:1])

    return {
        "users":               _write("users", extra_users),
        "customers":           _write("customers", extra_customers),
        "vendors":             _write("vendors", extra_vendors),
        "products":            _write("products", extra_products),
        "sales_orders":        _write("sales_orders", so),
        "purchase_orders":     _write("purchase_orders", po),
        "manufacturing_orders":_write("manufacturing_orders", mo),
    }
