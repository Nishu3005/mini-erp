"""Field metadata for the admin User-Management 4-tab permission grid.

The wireframes show a row PER FIELD with Create/View/Edit/Delete cells. The effective permission is
stored PER MODULE (one access_right row, CRUD flags) — the field rows visualise that, with the
wireframe's special cells rendered as fixed/disabled. See spec/pages/system-adminstrator/.

Each field entry: (label, {action: cell}) where cell is one of:
  "grid"  -> a normal checkbox bound to the module's CRUD flag for that action
  True    -> always-on, shown ticked + disabled
  False   -> never (shown ✗, disabled)
  "note:<text>" -> a fixed label (e.g. "Auto Compute", "Recomputed", "Not possible")
"""

ACTIONS = ("create", "view", "edit", "delete")

# module -> ordered list of (field_label, cells)
TABS = {
    "sales": [
        ("Customer",          {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Customer Address",  {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Sales Person",      {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Product",           {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Ordered Quantity",  {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Delivered Quantity",{"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Sales Price",       {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Status",            {"create": "grid", "view": "grid", "edit": "grid", "delete": False}),
        ("Total",             {"create": "grid", "view": "grid", "edit": "note:Recomputed", "delete": "note:Recomputed"}),
        ("Creation Date",     {"create": "note:Auto Compute", "view": "grid", "edit": False, "delete": False}),
    ],
    "purchase": [
        ("Vendor",            {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Vendor Address",    {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Responsible Person",{"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Product",           {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Ordered Quantity",  {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Received Quantity", {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Cost Price",        {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Total",             {"create": "grid", "view": "grid", "edit": "note:Auto Recomputed", "delete": "note:Auto Recomputed"}),
        ("Creation Date",     {"create": "note:Auto Compute", "view": "grid", "edit": False, "delete": False}),
    ],
    "manufacturing": [
        ("Product to Manufacture", {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Product Quantity",  {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("BoM",               {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Responsible Person",{"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Finished Quantity", {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Creation Date",     {"create": "note:Auto Compute", "view": "grid", "edit": False, "delete": False}),
    ],
    "product": [
        ("Product",           {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Sales Price",       {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Cost Price",        {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("On Hand Qty",       {"create": "grid", "view": "grid", "edit": "grid", "delete": False}),
        ("Free To Use Qty",   {"create": "grid", "view": "grid", "edit": "note:System Computed", "delete": False}),
        ("Procure On Demand", {"create": "note:Not possible", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Procurement Method",{"create": "note:Not possible", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Vendor",            {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
        ("Bill of Materials (BoM)", {"create": "grid", "view": "grid", "edit": "grid", "delete": "grid"}),
    ],
}

MODULES = ("sales", "purchase", "manufacturing", "product")
