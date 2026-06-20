"""Bill of Materials routes. BoM is a reusable template (no order state machine)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models.bom import Bom, BomComponent, BomOperation
from app.models.logs import AuditLog
from app.models.product import Product
from app.services import access, audit, sequences
from app.services.unitofwork import InputError, atomic, to_decimal, to_int

bp = Blueprint("bom", __name__, url_prefix="/bom")


@bp.route("/")
@login_required
@access.require("manufacturing", "view")
def list_view():
    search = (request.args.get("q") or "").strip()
    q = Bom.query
    if search:
        q = q.filter(Bom.reference.ilike(f"%{search}%"))
    boms = q.order_by(Bom.reference.desc()).all()
    return render_template("bom/list.html", boms=boms, search=search)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@access.require("manufacturing", "edit_bom")
def create():
    if request.method == "POST":
        try:
            bom = _save_bom(None)
            flash(f"Bill of Materials {bom.reference} created.", "success")
            return redirect(url_for("bom.form", bom_id=bom.id))
        except InputError as e:
            flash(str(e), "error")
    return render_template("bom/form.html", bom=None, products=Product.query.all(), logs=[])


@bp.route("/<int:bom_id>", methods=["GET", "POST"])
@login_required
@access.require("manufacturing", "view")
def form(bom_id):
    bom = Bom.query.get_or_404(bom_id)
    if request.method == "POST":
        if not access.can_current("manufacturing", "edit_bom"):
            flash("You don't have permission to edit BoMs.", "error")
        else:
            try:
                _save_bom(bom)
                flash("Bill of Materials saved.", "success")
                return redirect(url_for("bom.form", bom_id=bom.id))
            except InputError as e:
                flash(str(e), "error")
    logs = (AuditLog.query.filter_by(module="bom", record_ref=bom.reference)
            .order_by(AuditLog.timestamp.desc()).all())
    return render_template("bom/form.html", bom=bom, products=Product.query.all(), logs=logs)


def _save_bom(bom):
    fp = db.session.get(Product, to_int(request.form.get("finished_product_id"), "Finished product"))
    if fp is None:
        raise InputError("Select a valid finished product.")
    ref_label = (request.form.get("ref_label") or "").strip()
    if len(ref_label) > 8:
        raise InputError("Reference label must be 8 characters or fewer.")
    qty = to_decimal(request.form.get("quantity") or 1, "Quantity", minimum=0, allow_zero=False)

    comp_pairs = list(zip(request.form.getlist("comp_product_id"),
                          request.form.getlist("comp_to_consume")))

    with atomic():
        creating = bom is None
        if creating:
            bom = Bom(reference=sequences.next_reference("BOM"))
            db.session.add(bom)
        bom.ref_label = ref_label or None
        bom.finished_product_id = fp.id
        bom.quantity = qty
        db.session.flush()

        # replace components
        BomComponent.query.filter_by(bom_id=bom.id).delete()
        seen = set()
        for pid, tc in comp_pairs:
            if not pid or tc in (None, "", "0"):
                continue
            pid = to_int(pid, "Component")
            if pid in seen:
                raise InputError("A component appears more than once.")
            seen.add(pid)
            db.session.add(BomComponent(
                bom_id=bom.id, product_id=pid,
                to_consume=to_decimal(tc, "To consume", minimum=0, allow_zero=False)))

        audit.log("bom", bom.reference, "Bom", "create" if creating else "write")
    return bom
