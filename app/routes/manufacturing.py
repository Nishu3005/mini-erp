"""Manufacturing Order routes — thin controllers. State machine in services/manufacturing.py."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.bom import Bom
from app.models.logs import AuditLog
from app.models.manufacturing import ManufacturingOrder, MoComponent, WorkOrder
from app.models.product import Product
from app.models.user import User
from app.services import access, sequences
from app.services import manufacturing as mfg_svc
from app.services.unitofwork import InputError, atomic, to_decimal, to_int

bp = Blueprint("manufacturing", __name__, url_prefix="/manufacturing")


@bp.route("/")
@login_required
@access.require("manufacturing", "view")
def list_view():
    status = request.args.get("status")
    mine = request.args.get("mine")
    view = "kanban" if request.args.get("view") == "kanban" else "list"
    search = (request.args.get("q") or "").strip()

    q = ManufacturingOrder.query
    if mine:
        q = q.filter(ManufacturingOrder.assignee_id == current_user.id)
    if status:
        q = q.filter_by(status=status)
    if request.args.get("filter") == "to_close":   # dashboard "To Close" pill = in_progress
        q = q.filter_by(status="in_progress")
    if search:
        q = q.filter(ManufacturingOrder.reference.ilike(f"%{search}%"))
    orders = q.order_by(ManufacturingOrder.creation_date.desc()).all()
    return render_template("manufacturing/list.html", orders=orders, status=status,
                           mine=mine, view=view, search=search)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@access.require("manufacturing", "create")
def create():
    if request.method == "POST":
        try:
            order = _create_order()
            flash(f"Manufacturing Order {order.reference} created.", "success")
            return redirect(url_for("manufacturing.form", order_id=order.id))
        except InputError as e:
            flash(str(e), "error")
    return render_template("manufacturing/form.html", order=None,
                           products=Product.query.all(), boms=Bom.query.all(),
                           assignees=User.query.all(), logs=[])


@bp.route("/<int:order_id>")
@login_required
@access.require("manufacturing", "view")
def form(order_id):
    order = ManufacturingOrder.query.get_or_404(order_id)
    logs = (AuditLog.query.filter_by(module="manufacturing", record_ref=order.reference)
            .order_by(AuditLog.timestamp.desc()).all())
    return render_template("manufacturing/form.html", order=order,
                           products=Product.query.all(), boms=Bom.query.all(),
                           assignees=User.query.all(), logs=logs)


@bp.route("/<int:order_id>/confirm", methods=["POST"])
@login_required
@access.require("manufacturing", "production_entry")
def confirm(order_id):
    order = ManufacturingOrder.query.get_or_404(order_id)
    _act(order, mfg_svc.confirm, f"{order.reference} confirmed.")
    return redirect(url_for("manufacturing.form", order_id=order.id))


@bp.route("/<int:order_id>/start", methods=["POST"])
@login_required
@access.require("manufacturing", "production_entry")
def start(order_id):
    order = ManufacturingOrder.query.get_or_404(order_id)
    _act(order, mfg_svc.start, f"{order.reference} started.")
    return redirect(url_for("manufacturing.form", order_id=order.id))


@bp.route("/<int:order_id>/produce", methods=["POST"])
@login_required
@access.require("manufacturing", "production_entry")
def produce(order_id):
    order = ManufacturingOrder.query.get_or_404(order_id)
    consumes = {c.id: request.form.get(f"consume_{c.id}")
                for c in order.components if request.form.get(f"consume_{c.id}") is not None}
    try:
        mfg_svc.produce(order, consumes)
        flash(f"{order.reference} produced — stock updated.", "success")
    except mfg_svc.ManufacturingError as e:
        flash(str(e), "error")
    return redirect(url_for("manufacturing.form", order_id=order.id))


@bp.route("/<int:order_id>/cancel", methods=["POST"])
@login_required
@access.require("manufacturing", "production_entry")
def cancel(order_id):
    order = ManufacturingOrder.query.get_or_404(order_id)
    _act(order, mfg_svc.cancel, f"{order.reference} cancelled.", category="info")
    return redirect(url_for("manufacturing.form", order_id=order.id))


def _act(order, fn, ok_msg, category="success"):
    try:
        fn(order)
        flash(ok_msg, category)
    except mfg_svc.ManufacturingError as e:
        flash(str(e), "error")


def _create_order():
    product = db.session.get(Product, to_int(request.form.get("finished_product_id"), "Product"))
    if product is None:
        raise InputError("Select a valid finished product.")
    qty = to_decimal(request.form.get("quantity"), "Quantity", minimum=0, allow_zero=False)
    bom = db.session.get(Bom, to_int(request.form["bom_id"], "BoM")) if request.form.get("bom_id") else None

    with atomic():
        order = ManufacturingOrder(
            reference=sequences.next_reference("MO"), status="draft",
            finished_product_id=product.id, quantity=qty,
            bom_id=bom.id if bom else None, assignee_id=current_user.id,
        )
        db.session.add(order)
        db.session.flush()
        # populate components + work orders from the BoM (x qty) if one was chosen
        if bom:
            for comp in bom.components:
                db.session.add(MoComponent(
                    mo_id=order.id, product_id=comp.product_id,
                    to_consume=to_decimal(comp.to_consume, "to_consume") * qty))
            for op in bom.operations:
                db.session.add(WorkOrder(
                    mo_id=order.id, operation=op.operation, work_center=op.work_center,
                    expected_duration=int((op.expected_duration or 0) * int(qty))))
    return order
