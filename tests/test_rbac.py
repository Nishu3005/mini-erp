"""RBAC role-default resolution + override precedence + status gating (spec/rbac-redesign.md)."""
from app.models.user import AccessRight, User
from app.services import access


def _user(db, **kw):
    u = User(login_id=kw.pop("login_id"), email=kw.pop("email"), **kw)
    u.set_password("X")
    db.session.add(u)
    db.session.commit()
    return u


def test_role_default_fallback(db):
    u = _user(db, login_id="po1", email="po1@x.com", role="purchase", status="active")
    assert access.can(u, "purchase", "view")
    assert access.can(u, "purchase", "create")
    assert access.can(u, "purchase", "approve")
    assert access.can(u, "product", "view")        # purchase gets product view
    assert not access.can(u, "product", "create")
    assert not access.can(u, "sales", "view")      # no sales access


def test_owner_read_only_everywhere(db):
    u = _user(db, login_id="own1", email="own1@x.com", role="owner", status="active")
    for m in ("sales", "purchase", "manufacturing", "product"):
        assert access.can(u, m, "view")
        assert not access.can(u, m, "create")
        assert not access.can(u, m, "edit")
        assert not access.can(u, m, "delete")


def test_pending_user_denied(db):
    u = _user(db, login_id="pend1", email="pend1@x.com", role="sales", status="pending")
    assert not access.can(u, "sales", "view")


def test_rejected_user_denied(db):
    u = _user(db, login_id="rej1", email="rej1@x.com", role="sales", status="rejected")
    assert not access.can(u, "sales", "create")


def test_admin_bypass_via_role(db):
    u = _user(db, login_id="adm2", email="adm2@x.com", role="admin", status="active",
              is_admin=True)
    assert access.can(u, "manufacturing", "edit_bom")
    assert access.can(u, "sales", "delete")


def test_override_row_beats_role_default(db):
    # role=sales would deny purchase, but an explicit override row grants purchase view
    u = _user(db, login_id="ovr1", email="ovr1@x.com", role="sales", status="active")
    db.session.add(AccessRight(user_id=u.id, module="purchase", role="user",
                               can_view=True, can_create=False))
    db.session.commit()
    assert access.can(u, "purchase", "view")        # override grants it
    assert not access.can(u, "purchase", "create")  # override denies create
    # and where there's NO override, role default still applies
    assert access.can(u, "sales", "view")
