"""Dashboard: All/My status counts per module. See spec/pages/user/dashboard.md.

Thin controller — count logic lives in app/services/dashboard.py.
"""
from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.services import access
from app.services import dashboard as dash_svc

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@bp.route("/")
@login_required
def index():
    cards = []
    if access.can(current_user, "sales", "view"):
        cards.append({
            "title": "Sale Orders", "endpoint": "sales.list_view",
            "data": dash_svc.sales_card(current_user),
        })
    if access.can(current_user, "purchase", "view"):
        cards.append({
            "title": "Purchase Orders", "endpoint": "purchase.list_view",
            "data": dash_svc.purchase_card(current_user),
        })
    if access.can(current_user, "manufacturing", "view"):
        cards.append({
            "title": "Manufacturing Orders", "endpoint": "manufacturing.list_view",
            "data": dash_svc.manufacturing_card(current_user),
        })
    return render_template("dashboard/index.html", cards=cards)
