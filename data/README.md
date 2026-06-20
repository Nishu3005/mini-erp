# Seed Data

Believable starter data for "Shiv Furniture Works" so the app feels real on first run.
Loaded by `flask seed-data` (see `app/services/seed.py`). Plain JSON — edit freely.

## Files (loaded in this order)
1. `users.json` — admin + owner + manager + 3 sales + purchase + manufacturing users.
   `rights` names an access preset; `is_admin: true` bypasses all checks.
2. `access_presets.json` — maps each `rights` preset to per-module access_right rows.
3. `customers.json`, `vendors.json` — reference partners.
4. `products.json` — raw materials + finished goods. `vendor`/`bom` referenced by name.
5. `boms.json` — components + operations referenced by product name.
6. `sales_orders.json`, `purchase_orders.json`, `manufacturing_orders.json` — orders across every
   status so the dashboard is populated.

## Conventions
- **References are by name**, not id (e.g. a sales line's `"product": "Office Chair"`). The loader
  resolves names to rows.
- **Dates are relative**: `created_offset_days` / `schedule_offset_days` are integers added to *now*
  at load time (negative = past). This keeps "Late" / recent ordering realistic on any run day.
- Quantities/prices are plain numbers.

## Reload
`flask seed-data` is idempotent-ish: it **skips** if data already exists unless you pass `--reset`,
which wipes transactional + master tables first (users included) and reloads from scratch.
