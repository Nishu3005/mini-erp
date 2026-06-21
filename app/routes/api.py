"""JSON API surface — /api/v1. Bearer-token auth via app.services.jwt_auth.

Read-only in v1. The browser flow (Flask-Login, CSRF, scoped URLs) is unaffected. CSRF protection
is disabled for this blueprint at registration time — the JWT supplants it for these endpoints.
"""
from flask import Blueprint, g, jsonify, request

from app.models.product import Product
from app.models.sales import SalesOrder
from app.models.user import User
from app.services import access
from app.services.jwt_auth import encode_for, require_token
from app.services.pagination import paginate


bp = Blueprint("api", __name__, url_prefix="/api/v1")


# ---------- auth ----------
@bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    login_id = (data.get("login_id") or "").strip()
    password = data.get("password") or ""
    if not login_id or not password:
        return jsonify({"error": "missing login_id or password"}), 400

    user = User.query.filter_by(login_id=login_id).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "invalid credentials"}), 401
    if not user.is_admin and user.status != "active":
        return jsonify({"error": "account pending approval"}), 403

    token, expires_in = encode_for(user)
    return jsonify({
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "user": _user_brief(user),
    })


@bp.route("/me", methods=["GET"])
@require_token
def me():
    return jsonify(_user_brief(g.api_user))


# ---------- products ----------
@bp.route("/products", methods=["GET"])
@require_token
def products():
    if not access.can(g.api_user, "product", "view"):
        return jsonify({"error": "forbidden"}), 403
    q = Product.query.order_by(Product.name)
    page = request.args.get("page", type=int, default=1)
    rows, meta = paginate(q, page=page)
    return jsonify({"page": meta, "items": [_product_brief(p) for p in rows]})


@bp.route("/products/<int:product_id>", methods=["GET"])
@require_token
def product_one(product_id):
    if not access.can(g.api_user, "product", "view"):
        return jsonify({"error": "forbidden"}), 403
    p = Product.query.get(product_id)
    if p is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(_product_detail(p))


# ---------- sales orders ----------
@bp.route("/sales-orders", methods=["GET"])
@require_token
def sales_orders():
    if not access.can(g.api_user, "sales", "view"):
        return jsonify({"error": "forbidden"}), 403
    q = SalesOrder.query
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    q = q.order_by(SalesOrder.creation_date.desc())
    page = request.args.get("page", type=int, default=1)
    rows, meta = paginate(q, page=page)
    return jsonify({"page": meta, "items": [_so_brief(o) for o in rows]})


@bp.route("/sales-orders/<int:order_id>", methods=["GET"])
@require_token
def sales_order_one(order_id):
    if not access.can(g.api_user, "sales", "view"):
        return jsonify({"error": "forbidden"}), 403
    o = SalesOrder.query.get(order_id)
    if o is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(_so_detail(o))


# ---------- serializers (kept inline; tiny; no third-party schema lib) ----------
def _user_brief(u):
    return {"id": u.id, "login_id": u.login_id, "email": u.email, "name": u.name,
            "role": "admin" if u.is_admin else u.role, "status": u.status,
            "position": u.position}


def _product_brief(p):
    return {"id": p.id, "reference": p.reference, "name": p.name,
            "sales_price": float(p.sales_price or 0),
            "on_hand_qty": float(p.on_hand_qty or 0)}


def _product_detail(p):
    out = _product_brief(p)
    out.update({
        "cost_price": float(p.cost_price or 0),
        "reserved_qty": float(p.reserved_qty),
        "free_to_use_qty": float(p.free_to_use_qty),
        "procure_on_demand": bool(p.procure_on_demand),
        "procure_method": p.procure_method,
    })
    return out


def _so_brief(o):
    return {"id": o.id, "reference": o.reference, "status": o.status,
            "customer": o.customer.name if o.customer else None,
            "salesperson": o.salesperson.name if o.salesperson else None,
            "creation_date": o.creation_date.isoformat() if o.creation_date else None,
            "total": float(o.total)}


def _so_detail(o):
    out = _so_brief(o)
    out["lines"] = [
        {"id": ln.id, "product": ln.product.name,
         "ordered_qty": float(ln.ordered_qty or 0),
         "delivered_qty": float(ln.delivered_qty or 0),
         "unit_price": float(ln.sales_price or 0),
         "total": float(ln.total)}
        for ln in o.lines
    ]
    return out
