"""Role-scoped URL scheme: dispatcher + identity guard + route_for (Phase 4)."""
from app.models.user import User
from app.services.urlscheme import route_for


def _login(client, db, login_id, role="sales", is_admin=False):
    u = User(login_id=login_id, email=f"{login_id}@x.com", role=role,
             is_admin=is_admin, status="active")
    u.set_password("Strong@1pass"); db.session.add(u); db.session.commit()
    client.post("/login", data={"login_id": login_id, "password": "Strong@1pass"})
    return u


def test_scoped_matches_user_renders_in_place(client, db):
    """Scoped URL is canonical — it renders the view directly (no further redirect)."""
    _login(client, db, "scope1", role="sales")
    r = client.get("/sales/scope1/sales/", follow_redirects=False)
    assert r.status_code == 200   # rendered in place, URL bar stays scoped


def test_flat_url_redirects_to_scoped(client, db):
    """Logged-in user hitting a flat in-app URL is canonicalized to the scoped equivalent.
    `/<role>/` for the user's own role collapses to `/<role>/<username>/` (no double-prefix)."""
    _login(client, db, "scopeR", role="purchase")
    r = client.get("/purchase/", follow_redirects=False)
    assert r.status_code in (301, 302)
    assert r.headers["Location"] == "/purchase/scopeR/"


def test_scoped_wrong_username_403(client, db):
    _login(client, db, "scope2", role="sales")
    assert client.get("/sales/someone-else/sales/").status_code == 403


def test_scoped_wrong_role_403(client, db):
    _login(client, db, "scope3", role="sales")
    assert client.get("/purchase/scope3/sales/").status_code == 403


def test_scoped_unknown_role_404(client, db):
    """An unknown role at position-0 isn't a scoped URL — falls through. The path has no matching
    flat route either, so following redirects ends at 404."""
    _login(client, db, "scope4", role="sales")
    r = client.get("/bogus/scope4/sales/", follow_redirects=True)
    assert r.status_code == 404


def test_route_for_injects_role_and_username(app, db):
    from flask_login import login_user
    u = User(login_id="rf1", email="rf1@x.com", role="purchase", status="active")
    u.set_password("X"); db.session.add(u); db.session.commit()
    with app.test_request_context("/"):
        login_user(u)
        url = route_for("purchase.list_view")
        assert url == "/purchase/rf1/purchase/"


def test_route_for_passes_through_auth_routes(app, db):
    from flask_login import login_user
    u = User(login_id="rf2", email="rf2@x.com", role="sales", status="active")
    u.set_password("X"); db.session.add(u); db.session.commit()
    with app.test_request_context("/"):
        login_user(u)
        # logout/login/static must stay flat (no scoping)
        assert route_for("auth.logout") == "/logout"
