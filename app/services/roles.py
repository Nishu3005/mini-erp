"""Named roles + their DEFAULT per-module permissions (RBAC).

Source of truth for role defaults (spec/rbac-redesign.md §2). A user's effective permission is:
  admin            -> everything
  status != active -> nothing (pending / rejected)
  else             -> per-user access_right override row if present, else this role default.

Actions: view, create, edit, delete, approve, production_entry, edit_bom.
"""

# the six roles (excluding the implicit "unassigned" of a pending user)
ROLES = ("admin", "sales", "inventory", "manufacturing", "purchase", "owner")

# roles a self-signup user may request (admin is never self-assignable)
REQUESTABLE_ROLES = ("sales", "inventory", "manufacturing", "purchase", "owner")

ROLE_LABELS = {
    "admin": "System Administrator",
    "sales": "Sales Team Member",
    "inventory": "Inventory Manager",
    "manufacturing": "Manufacturing Team Member",
    "purchase": "Purchase Team Member",
    "owner": "Business Owner",
}

_FULL = {"view", "create", "edit", "delete"}

# role -> {module: set(actions)}. Missing module => no access on it.
ROLE_DEFAULTS = {
    "admin": {  # admin is handled by bypass; listed for completeness
        "sales": _FULL | {"approve"},
        "purchase": _FULL | {"approve"},
        "manufacturing": _FULL | {"production_entry", "edit_bom"},
        "product": _FULL,
    },
    "sales": {
        "sales": {"view", "create", "edit"},
        "product": {"view"},
    },
    "inventory": {  # Inventory Manager / Product team
        "product": _FULL,
        "sales": {"view"},
        "purchase": {"view"},
        "manufacturing": {"view"},
    },
    "manufacturing": {
        "manufacturing": {"view", "create", "edit", "production_entry"},
        "product": {"view"},
    },
    "purchase": {
        "purchase": {"view", "create", "edit", "approve"},
        "product": {"view"},
    },
    "owner": {  # Business Owner — read-only everywhere
        "sales": {"view"},
        "purchase": {"view"},
        "manufacturing": {"view"},
        "product": {"view"},
    },
}


def role_allows(role: str, module: str, action: str) -> bool:
    """True if `role`'s DEFAULTS permit `action` on `module` (before per-user overrides)."""
    if not role:
        return False
    return action in ROLE_DEFAULTS.get(role, {}).get(module, set())
