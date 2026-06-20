"""Purchase Order routes — thin controllers. State machine in app/services/purchase.py."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.extensions import db
from app.models.logs import AuditLog
from app.models.partner import Vendor
from app.models.product import Product
from app.models.purchase import PurchaseOrder, PurchaseOrderLine
from app.models.user import User
from app.services import access, sequences
from app.services import purchase as purchase_svc
from app.services.unitofwork import InputError, atomic, to_decimal, to_int

bp = Blueprint("purchase", __name__, url_prefix="/purchase")


@bp.route("/")
@login_required
@access.require("purchase", "view")
def list_view():
    status = request.args.get("status")
    mine = request.args.get("mine")
    view = "kanban" if request.args.get("view") == "kanban" else "list"
    search = (request.args.get("q") or "").strip()

    q = PurchaseOrder.query
    if mine:
        q = q.filter(PurchaseOrder.responsible_id == current_user.id)
    if status:
        q = q.filter_by(status=status)
    if request.args.get("filter") == "late":
        from datetime import datetime
        q = q.filter(PurchaseOrder.status.in_(("confirmed", "partially_received")),
                     PurchaseOrder.expected_date.isnot(None),
                     PurchaseOrder.expected_date < datetime.utcnow())
    if search:
        like = f"%{search}%"
        q = q.join(Vendor).filter(
            or_(PurchaseOrder.reference.ilike(like), Vendor.name.ilike(like)))
    orders = q.order_by(PurchaseOrder.creation_date.desc()).all()
    return render_template("purchase/list.html", orders=orders,
                           status=(request.args.get("filter") or status),
                           mine=mine, view=view, search=search)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@access.require("purchase", "create")
def create():
    if request.method == "POST":
        try:
            order = _create_order()
            flash(f"Purchase Order {order.reference} created.", "success")
            return redirect(url_for("purchase.form", order_id=order.id))
        except InputError as e:
            flash(str(e), "error")
    return render_template("purchase/form.html", order=None,
                           vendors=Vendor.query.all(), responsibles=User.query.all(),
                           products=Product.query.all(), logs=[])


@bp.route("/<int:order_id>")
@login_required
@access.require("purchase", "view")
def form(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    logs = (AuditLog.query.filter_by(module="purchase", record_ref=order.reference)
            .order_by(AuditLog.timestamp.desc()).all())
    return render_template("purchase/form.html", order=order,
                           vendors=Vendor.query.all(), responsibles=User.query.all(),
                           products=Product.query.all(), logs=logs)


@bp.route("/<int:order_id>/confirm", methods=["POST"])
@login_required
@access.require("purchase", "approve")
def confirm(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    try:
        purchase_svc.confirm(order)
        flash(f"{order.reference} confirmed.", "success")
    except purchase_svc.PurchaseError as e:
        flash(str(e), "error")
    return redirect(url_for("purchase.form", order_id=order.id))


@bp.route("/<int:order_id>/receive", methods=["POST"])
@login_required
@access.require("purchase", "edit")
def receive(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    receipts = {line.id: request.form.get(f"receive_{line.id}")
                for line in order.lines if request.form.get(f"receive_{line.id}")}
    try:
        purchase_svc.receive(order, receipts)
        flash(f"{order.reference}: receipt recorded (stock updated).", "success")
    except purchase_svc.PurchaseError as e:
        flash(str(e), "error")
    return redirect(url_for("purchase.form", order_id=order.id))


@bp.route("/<int:order_id>/cancel", methods=["POST"])
@login_required
@access.require("purchase", "edit")
def cancel(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    try:
        purchase_svc.cancel(order)
        flash(f"{order.reference} cancelled.", "info")
    except purchase_svc.PurchaseError as e:
        flash(str(e), "error")
    return redirect(url_for("purchase.form", order_id=order.id))


def _create_order():
    vendor = db.session.get(Vendor, to_int(request.form.get("vendor_id"), "Vendor"))
    if vendor is None:
        raise InputError("Select a valid vendor.")
    pairs = list(zip(request.form.getlist("product_id"), request.form.getlist("ordered_qty")))
    cleaned, seen = [], set()
    for pid, qty in pairs:
        if not pid or qty in (None, "", "0"):
            continue
        pid = to_int(pid, "Product")
        q = to_decimal(qty, "Ordered quantity", minimum=0, allow_zero=False)
        if pid in seen:
            raise InputError("The same product appears on more than one line.")
        product = db.session.get(Product, pid)
        if product is None:
            raise InputError("One of the selected products no longer exists.")
        seen.add(pid)
        cleaned.append((product, q))
    if not cleaned:
        raise InputError("Add at least one product line with a quantity.")

    with atomic():
        order = PurchaseOrder(
            reference=sequences.next_reference("PO"), status="draft",
            vendor_id=vendor.id, vendor_address=vendor.address,
            responsible_id=current_user.id,
        )
        db.session.add(order)
        db.session.flush()
        for product, q in cleaned:
            db.session.add(PurchaseOrderLine(
                purchase_order_id=order.id, product_id=product.id,
                ordered_qty=q, cost_price=product.cost_price))
    return order
