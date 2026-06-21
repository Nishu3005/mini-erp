"""JWT API endpoint tests — login, /me, products, sales-orders, RBAC + pending gating.

See spec/jwt-api.md.
"""
from app.models.user import AccessRight, User


def _make_user(db, login_id, role="sales", status="active", grants=("sales", "product")):
    u = User(login_id=login_id, email=f"{login_id}@x.com", role=role, status=status,
             name=login_id.title())
    u.set_password("Strong@1pass")
    db.session.add(u); db.session.flush()
    for module in grants:
        db.session.add(AccessRight(user_id=u.id, module=module, role="user", can_view=True))
    db.session.commit()
    return u


def test_login_returns_jwt_and_user_brief(client, db):
    _make_user(db, "jwt.user1")
    r = client.post("/api/v1/auth/login",
                    json={"login_id": "jwt.user1", "password": "Strong@1pass"})
    assert r.status_code == 200, r.data
    body = r.get_json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] > 0
    assert body["access_token"].count(".") == 2     # header.payload.sig
    assert body["user"]["login_id"] == "jwt.user1"
    assert body["user"]["role"] == "sales"


def test_login_missing_field_400(client, db):
    r = client.post("/api/v1/auth/login", json={"login_id": "jwt.user1"})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_login_wrong_password_401(client, db):
    _make_user(db, "jwt.user2")
    r = client.post("/api/v1/auth/login",
                    json={"login_id": "jwt.user2", "password": "WRONG"})
    assert r.status_code == 401


def test_login_pending_user_403(client, db):
    u = User(login_id="jwt.pend", email="p@x.com", status="pending", requested_role="sales")
    u.set_password("Strong@1pass"); db.session.add(u); db.session.commit()
    r = client.post("/api/v1/auth/login",
                    json={"login_id": "jwt.pend", "password": "Strong@1pass"})
    assert r.status_code == 403


def test_me_requires_token(client, db):
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me",
                      headers={"Authorization": "Bearer nope.nope.nope"}).status_code == 401


def test_me_returns_caller_brief(client, db):
    _make_user(db, "jwt.user3")
    r = client.post("/api/v1/auth/login",
                    json={"login_id": "jwt.user3", "password": "Strong@1pass"})
    tok = r.get_json()["access_token"]
    r = client.get("/api/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.get_json()["login_id"] == "jwt.user3"


def test_products_listing_paginated(client, db):
    _make_user(db, "jwt.user4", grants=("product",))
    r = client.post("/api/v1/auth/login",
                    json={"login_id": "jwt.user4", "password": "Strong@1pass"})
    tok = r.get_json()["access_token"]
    r = client.get("/api/v1/products", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.get_json()
    assert "page" in body and "items" in body
    assert "total" in body["page"]


def test_rbac_blocks_module_without_view(client, db):
    # role=manufacturing has no sales default; explicit overrides only grant product:view ->
    # /sales-orders should 403 via the RBAC layer.
    _make_user(db, "jwt.user5", role="manufacturing", grants=("product",))
    tok = client.post("/api/v1/auth/login",
                      json={"login_id": "jwt.user5", "password": "Strong@1pass"}
                      ).get_json()["access_token"]
    r = client.get("/api/v1/sales-orders", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_csrf_not_required_on_api(client, db):
    """JWT replaces session CSRF — login must work as a plain JSON POST."""
    _make_user(db, "jwt.user6")
    # The conftest disables CSRF anyway, but the api blueprint is csrf.exempt'd in case prod
    # config differs. This test exists as a guard.
    r = client.post("/api/v1/auth/login",
                    json={"login_id": "jwt.user6", "password": "Strong@1pass"})
    assert r.status_code == 200
