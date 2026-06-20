"""Product routes — thin controllers. Logic is in app/services/product.py."""
from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import login_required

from app.models.bom import Bom
from app.models.logs import AuditLog
from app.models.product import Product
from app.models.partner import Vendor
from app.services import access, inventory
from app.services import product as product_svc

bp = Blueprint("product", __name__, url_prefix="/products")


def _form_data():
    """Pull and coerce the product form payload."""
    f = request.form
    return {
        "name": f.get("name", ""),
        "sales_price": f.get("sales_price") or 0,
        "cost_price": f.get("cost_price") or 0,
        "on_hand_qty": f.get("on_hand_qty") or 0,
        "procure_on_demand": f.get("procure_on_demand") == "on",
        "procure_method": f.get("procure_method") or None,
        "vendor_id": int(f["vendor_id"]) if f.get("vendor_id") else None,
        "bom_id": int(f["bom_id"]) if f.get("bom_id") else None,
    }


@bp.route("/")
@login_required
@access.require("product", "view")
def list_view():
    products = Product.query.order_by(Product.name).all()
    reserved = inventory.reserved_qty_map()   # single aggregated query (no N+1)
    return render_template("product/list.html", products=products, reserved=reserved)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@access.require("product", "create")
def create():
    if request.method == "POST":
        try:
            p = product_svc.create(_form_data())
            flash(f"Product {p.reference} created.", "success")
            return redirect(url_for("product.form", product_id=p.id))
        except product_svc.ProductError as e:
            flash(str(e), "error")
    return render_template("product/form.html", product=None,
                           vendors=Vendor.query.all(), boms=Bom.query.all(), logs=[])


@bp.route("/<int:product_id>", methods=["GET", "POST"])
@login_required
@access.require("product", "view")
def form(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        if not access.can_current("product", "edit"):
            abort(403)
        try:
            product_svc.update(product, _form_data())
            flash("Product saved.", "success")
            return redirect(url_for("product.form", product_id=product.id))
        except product_svc.ProductError as e:
            flash(str(e), "error")
    logs = (AuditLog.query.filter_by(module="product", record_ref=product.reference)
            .order_by(AuditLog.timestamp.desc()).all())
    return render_template("product/form.html", product=product,
                           vendors=Vendor.query.all(), boms=Bom.query.all(), logs=logs)
