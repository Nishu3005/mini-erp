# Mini ERP — Shiv Furniture Works

A modular Mini ERP for a furniture manufacturer (Odoo × KAHE Coimbatore hackathon). The whole system
revolves around one idea: **every module moves stock**, with `Free To Use = On Hand − Reserved` and
automated MTS/MTO procurement.

Modules: **Products · Sales · Purchase · Manufacturing · Bill of Materials · Inventory**, plus
**Audit Logs** and per-module **Access Rights**.

## Stack
Python 3.11+ · Flask (app-factory + blueprints) · Flask-SQLAlchemy · SQLite · Flask-Migrate ·
Flask-Login · Flask-WTF. Server-rendered Jinja2 + hand-written CSS/vanilla JS — **no build step**.
Managed with **uv**.

## Architecture (the rules)
- **Routes are thin** — no DB access or business logic; they call **services**.
- **State machines live in services only** (SO/PO/MO statuses change via validated methods).
- **One write boundary** — `services/unitofwork.atomic()` commits on success / rolls back on error.
- **Audit everything** marked *(track logs)*; **stock movements** recorded in the stock ledger.
- **Authorization on every route** via `services/access.can()` (deny by default).

See `../../spec/` for the full specification and `../../spec/IMPLEMENTATION-STATUS.md` for what is
built vs. specced.

## Quick start
```bash
uv sync                          # create .venv from the lockfile
uv run flask db upgrade          # apply migrations
uv run flask seed-data --reset   # load believable demo data
uv run python run.py             # http://127.0.0.1:5000
```

Demo logins (from `data/users.json`): `admin1 / Admin@123` (system admin),
`owner.shiv / Owner@123` (full access), `sales.ravi / Sales@123`, `purchase.vijay / Purchase@123`,
`mfg.dinesh / Mfg@1234`.

## Tests & linting
```bash
uv run pytest                    # inventory, state machines, procurement, access
uv run ruff check .              # lint
```

## Layout
```
app/
  __init__.py        app factory + CLI (init-db, seed-admin, seed-data)
  extensions.py      db / migrate / login / csrf singletons
  models/            SQLAlchemy models (one concern per file)
  services/          ALL business logic + state machines + access checks
  routes/            blueprints (thin controllers)
  forms/             Flask-WTF forms (server-side validation + CSRF)
  templates/         Jinja2 (base, partials, per-module)
  static/            css/ (hand-written) + uploads/ (gitignored)
data/                editable JSON seed data
migrations/          Flask-Migrate (Alembic)
tests/               pytest
```

## Configuration
Environment via `.env` (gitignored). In **production** `SECRET_KEY` is **required** (the app refuses
to start without it); dev uses a fixed insecure key for convenience. Uploads are capped at 5 MB.
