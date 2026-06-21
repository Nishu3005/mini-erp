"""Waiting-list signup flow: signup -> pending -> admin approve/reject (RBAC Phase 2)."""
from app.models.user import User
from app.services import admin as admin_svc
from app.services import access


def _admin(db):
    u = User(login_id="admin99", email="adm99@x.com", is_admin=True, role="admin", status="active")
    u.set_password("X"); db.session.add(u); db.session.commit()
    return u


def test_signup_creates_pending_user(client, db):
    r = client.post("/signup", data={
        "login_id": "wlnewbie1", "email": "wl1@x.com",
        "password": "Strong@1pass", "confirm": "Strong@1pass",
        "requested_role": "purchase",
    }, follow_redirects=True)
    assert b"awaiting administrator approval" in r.data
    u = User.query.filter_by(login_id="wlnewbie1").first()
    assert u.status == "pending"
    assert u.requested_role == "purchase"
    assert u.role is None


def test_pending_user_login_lands_on_pending_screen(client, db):
    u = User(login_id="wlpend1", email="pend1@x.com", status="pending", requested_role="sales")
    u.set_password("Strong@1pass"); db.session.add(u); db.session.commit()
    r = client.post("/login", data={"login_id": "wlpend1", "password": "Strong@1pass"},
                    follow_redirects=True)
    assert b"Awaiting Approval" in r.data


def test_pending_user_denied_module_access(client, db):
    u = User(login_id="wlpend2", email="pend2@x.com", status="pending", requested_role="sales")
    u.set_password("Strong@1pass"); db.session.add(u); db.session.commit()
    client.post("/login", data={"login_id": "wlpend2", "password": "Strong@1pass"})
    # any module path should 403 (pending users have no access)
    assert client.get("/sales/").status_code == 403
    assert client.get("/profile/").status_code in (200, 302)  # profile is identity-scoped, allowed


def test_admin_approve_activates_user_and_grants_role_default(client, db):
    admin = _admin(db)
    u = User(login_id="wlapp1", email="app1@x.com", status="pending", requested_role="sales")
    u.set_password("Strong@1pass"); db.session.add(u); db.session.commit()

    client.post("/login", data={"login_id": "admin99", "password": "X"})
    r = client.post(f"/admin/users/{u.id}/approve", data={"role": "sales"}, follow_redirects=True)
    assert b"approved as" in r.data
    db.session.refresh(u)
    assert u.status == "active" and u.role == "sales"
    # role default applies (no override rows yet) -> sales view/create/edit
    assert access.can(u, "sales", "view")
    assert access.can(u, "sales", "create")
    assert not access.can(u, "purchase", "view")


def test_admin_reject_sets_rejected(client, db):
    admin = _admin(db)
    u = User(login_id="wlrej1", email="rej1@x.com", status="pending", requested_role="manufacturing")
    u.set_password("X"); db.session.add(u); db.session.commit()
    client.post("/login", data={"login_id": "admin99", "password": "X"})
    client.post(f"/admin/users/{u.id}/reject")
    db.session.refresh(u)
    assert u.status == "rejected"
    assert not access.can(u, "manufacturing", "view")
