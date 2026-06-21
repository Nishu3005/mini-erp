"""Sales Order routes — thin controllers. State machine is in app/services/sales.py."""
from datetime import datetime

from flask import (Blueprint, flash, redirect, render_template, request, url_for)
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.models.logs import AuditLog
from app.models.partner import Customer
from app.models.product import Product
from app.models.sales import SalesOrder
from app.models.user import User
from app.services import access
from app.services import sales as sales_svc
from app.services.unitofwork import InputError

bp = Blueprint("sales", __name__, url_prefix="/sales")


@bp.route("/")
@login_required
@access.require("sales", "view")
def list_view():
    status = request.args.get("status")          # dashboard status pill
    flt = request.args.get("filter")             # derived pill: 'late'
    mine = request.args.get("mine")              # 'My' row pills
    view = "kanban" if request.args.get("view") == "kanban" else "list"
    search = (request.args.get("q") or "").strip()

    q = SalesOrder.query
    if mine:
        q = q.filter(SalesOrder.salesperson_id == current_user.id)
    if status:
        q = q.filter_by(status=status)
    if flt == "late":
        q = q.filter(
            SalesOrder.status.in_(("confirmed", "partially_delivered")),
            SalesOrder.expected_date.isnot(None),
            SalesOrder.expected_date < datetime.utcnow(),
        )
    if search:
        like = f"%{search}%"
        q = q.join(Customer).filter(
            or_(SalesOrder.reference.ilike(like), Customer.name.ilike(like)))
    from app.services.pagination import paginate
    page = request.args.get("page", type=int, default=1)
    orders, page_meta = paginate(q.order_by(SalesOrder.creation_date.desc()), page=page)
    return render_template("sales/list.html", orders=orders, status=(flt or status),
                           mine=mine, view=view, search=search, page_meta=page_meta)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@access.require("sales", "create")
def create():
    if request.method == "POST":
        line_inputs = list(zip(request.form.getlist("product_id"),
                               request.form.getlist("ordered_qty")))
        try:
            order = sales_svc.create_order(
                request.form.get("customer_id"), current_user.id, line_inputs)
            flash(f"Sales Order {order.reference} created.", "success")
            return redirect(url_for("sales.form", order_id=order.id))
        except (sales_svc.SalesError, InputError) as e:
            flash(str(e), "error")
    return render_template("sales/form.html", order=None,
                           customers=Customer.query.all(),
                           salespeople=User.query.all(),
                           products=Product.query.all(), logs=[])


@bp.route("/<int:order_id>")
@login_required
@access.require("sales", "view")
def form(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    logs = (AuditLog.query.filter_by(module="sales", record_ref=order.reference)
            .order_by(AuditLog.timestamp.desc()).all())
    return render_template("sales/form.html", order=order,
                           customers=Customer.query.all(),
                           salespeople=User.query.all(),
                           products=Product.query.all(), logs=logs)


@bp.route("/<int:order_id>/confirm", methods=["POST"])
@login_required
@access.require("sales", "approve")
def confirm(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    try:
        created = sales_svc.confirm(order)
        msg = f"{order.reference} confirmed."
        pos, mos = created["purchase_orders"], created["manufacturing_orders"]
        if pos or mos:
            parts = []
            if pos:
                parts.append("PO " + ", ".join(pos))
            if mos:
                parts.append("MO " + ", ".join(mos))
            msg += " Procurement auto-created: " + "; ".join(parts) + "."
        flash(msg, "success")
    except sales_svc.SalesError as e:
        flash(str(e), "error")
    return redirect(url_for("sales.form", order_id=order.id))


@bp.route("/<int:order_id>/deliver", methods=["POST"])
@login_required
@access.require("sales", "edit")
def deliver(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    deliveries = {}
    for line in order.lines:
        val = request.form.get(f"deliver_{line.id}")
        if val:
            deliveries[line.id] = val
    try:
        sales_svc.deliver(order, deliveries)
        flash(f"{order.reference}: delivery recorded.", "success")
    except sales_svc.SalesError as e:
        flash(str(e), "error")
    return redirect(url_for("sales.form", order_id=order.id))


@bp.route("/<int:order_id>/cancel", methods=["POST"])
@login_required
@access.require("sales", "edit")
def cancel(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    try:
        sales_svc.cancel(order)
        flash(f"{order.reference} cancelled.", "info")
    except sales_svc.SalesError as e:
        flash(str(e), "error")
    return redirect(url_for("sales.form", order_id=order.id))


