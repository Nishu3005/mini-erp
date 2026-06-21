# Demo Script — Shiv Furniture Works Mini ERP

*Odoo × KAHE Coimbatore Hackathon · 6-minute walkthrough · 4 acts*

> **Run before demo (once):**
> ```powershell
> uv run flask reset-db        # fresh, ~0.2s
> uv run python run.py
> ```
> Open `http://127.0.0.1:5000` in a clean browser window.

The thesis to keep saying out loud:

> **Every module moves stock. The whole system revolves around one number:
> `Free To Use = On Hand − Reserved`. Procurement and manufacturing automate themselves around it.**

---

## Act 1 — Landing & Login (45 sec)

**You're at `/`.**

- *"This is a Mini ERP for Shiv Furniture Works — a real furniture manufacturer's workflow:
  sales orders, purchase orders, manufacturing, bill of materials, inventory, audit. Built in
  24 hours with Flask + SQLite + hand-written CSS — no React, no Tailwind, no build step."*
- Point to the marketing landing illustration. *"Every page has a footer illustration we
  generated through TokenRouter — Seedream 4.5 — we'll show that in action at the end."*
- Click **Sign In** → land on `/login`.
- **Login as `owner.shiv` / `Owner@123`** — *"This is the owner. He sees everything."*

You arrive at the **dashboard**. Pause here.

---

## Act 2 — The Free-To-Use story (2 min, the core)

**This is the demo. Spend the most time here.**

### 2a. Show the dashboard

- *"This is the Owner's dashboard. Every module shows what's open and what's mine."*
- Point to one of the pills — say *Sales: 12 Open*. *"These pills are live counts and they link
  straight into the filtered list view."*
- Click the **(i) info button** on the dashboard. *"Every list page in the app has one — a
  one-paragraph purpose plus a numbered how-to. New users don't need a manual."* Close it.

### 2b. Create a Sales Order that *can't* be fulfilled

Open **Master Menu → Sale Orders → New**.

- Customer: pick any existing customer (e.g. *Acme*).
- Product line: **Wooden Table** — *because we know it has a BoM and procures via Manufacturing.*
- Ordered qty: **50**.   (We have 28 on hand; that creates a shortage.)
- Click **Create**, then **Confirm**.

**Show the flash banner**: *"Sales Order SO-…confirmed."* and *"Manufacturing Order MO-… auto-created."*

Now say the magic sentence:

> *"That MO didn't appear because a human pressed a button. The product 'Wooden Table' has
> Procure-on-Demand turned on with method = Manufacturing. When we confirmed the SO, the
> service layer checked **Free To Use** — `on_hand − reserved` — saw a 22-unit shortage,
> and auto-created an MO to cover the gap. The reservation also flows back into the
> product so any other module can see the constraint."*

### 2c. Show that Free-To-Use dropped

Open **Master Menu → Products** in a new tab.

- Find **Wooden Table**.
- Point to **On Hand: 28** and **Free To Use: 0** (or negative).
- *"On Hand didn't move — the goods are physically still here. But Free To Use dropped to zero
  because the order reserved them. This is the **one number** the whole system pivots on."*

### 2d. Walk into the auto-created MO

Open **Master Menu → Manufacturing Orders**.

- The newest MO at the top is the one our SO just spawned. Open it.
- Show that the **Components** section is pre-filled from the BoM × the MO quantity (e.g.
  4 legs × 22 tables = 88 legs).
- Show the **Work Orders** section: each operation (Cut, Sand, Assemble) has its own
  todo → in_progress → done state machine.

This is the second key sentence:

> *"This is full operator routing. Each work order has its own assignee, its own clock, and
> its own state. Real Duration is auto-captured as the time between Start and Finish. The
> MO's **Produce** button is **blocked** until every work order is Done — operators have to
> walk through the floor, they can't fake it."*

### 2e. Hand off to manufacturing — log in as the floor lead

Log out (top-right avatar → Logout). Log in as **`mfg.dinesh` / `Mfg@1234`**.

- Notice the **scoped URL**: `/manufacturing/mfg.dinesh/…`. *"Every page in the app lives
  under a role + username prefix. The role and username on the path are display-only —
  identity comes from the session — but it gives every operator a 'this is mine' feeling
  the moment they look at the URL bar."*
- Dinesh's dashboard only shows what manufacturing can act on. *"Sales, Purchase, Admin —
  he can't even see those modules. Per-module, per-action permissions."*
- Open the MO from earlier. Click **Start** on the first work order → status flips to
  in_progress, Started At is stamped. Click **Finish** → Real Duration is auto-captured.
- *"In a real shop, this is a tablet on the workbench."*

(For the demo, you can skip ahead — leave one WO un-finished to prove the gate.)

- Try to click **Produce** while a WO is still pending. **Flash error**: *"Cannot produce:
  1 work order(s) still pending."* Show the error.
- Finish the last WO, click **Produce** → flash success, MO status flips to Done.

### 2f. Show the stock ledger reacted

Back to **Products → Wooden Table**.

- On Hand jumped up by 22. Free To Use back to positive.
- *"The Produce step did two stock movements: minus components, plus finished good. Every
  movement is in the stock ledger; the SO can now be delivered."*

---

## Act 3 — Audit, RBAC, the boring-but-important stuff (1 min)

### 3a. Audit Logs

Log back in as **admin1 / Admin@123**.

Master Menu → **Audit Logs**.

- *"Every tracked field change in the system writes here. Admin-only screen, full filterable
  history. The four cards at the top are live counts."*
- Filter to **module = manufacturing** to see the trail of the MO we just finished:
  status changes, work-order starts/finishes, the produce event.

### 3b. Access Rights

Master Menu → click an active user (e.g. `sales.ravi`).

- Show the 7-column access matrix per module: view / create / edit / delete / approve /
  production_entry / edit_bom.
- *"Permissions are checked on every route. We added a pending-signup queue at the top —
  new signups can't log in until an admin approves them."*

---

## Act 4 — The "and we also did this" speed run (1 min 15 sec)

This is where you pile on the wow without dwelling:

### Things to mention while clicking through

| Click | What to say |
|------|------|
| **/api/v1** in URL bar via curl/Postman | *"JWT API for external automation — login, list products, place orders. Same RBAC checks."* |
| The footer illustration on any page | *"AI-generated banners — Seedream 4.5 via TokenRouter, one prompt per page, ~12 images at ~$0.04 each."* |
| Avatar in top-right | *"40 seeded profile photos so the demo data feels real."* |
| Open **Bill of Materials** list | *"Per-product recipes — components + operations, drives every Manufacturing Order."* |
| Open a **Purchase Order** | *"Same lifecycle as sales but inbound: Draft → Confirmed → Received. Receive is the only manual stock-in path."* |
| `flask reset-db` in the terminal | *"One command, 0.2 seconds — drops all tables, recreates schema, reseeds 23 users / 300 customers / 50 products / 60 orders. So a judge can hand the laptop to the next person."* |
| `pytest` summary screen | *"43 unit tests — covers the inventory engine, state machines, the four harsh findings we caught and fixed in review, the JWT API."* |

---

## Closing — 30 sec

> *"What we built isn't a CRUD app with five screens. It's an inventory engine — every module
> moves stock through a single ledger, free-to-use drives every procurement decision, and
> work orders gate every produce. We covered every spec'd module in 24 hours, with 43 passing
> tests and no build step."*

> *"Thank you."*

---

## Demo cast (cheat sheet — keep this open)

| Login | Password | Role | Use for |
|-------|----------|------|---------|
| `admin1` | `Admin@123` | Admin | Audit Logs, User Management, anything cross-module |
| `owner.shiv` | `Owner@123` | Owner | Dashboard overview, "sees everything" framing |
| `sales.ravi` | `Sales@123` | Sales | Creating + confirming the demo SO |
| `purchase.vijay` | `Purchase@123` | Purchase | Show the PO lifecycle (Act 4 cameo) |
| `mfg.dinesh` | `Mfg@1234` | Manufacturing | Operator routing — start/finish work orders |

## Demo product (the one to use)

- **Wooden Table** (`PRD-000006`) — has a BoM, `procure_method = manufacturing`,
  `procure_on_demand = True`. Order 50 (we have 28) and the MO auto-spawns.

## What to do if something goes sideways

| Symptom | Recovery |
|---------|----------|
| `no such table: user` 500 | `uv run flask reset-db` in another terminal, then reload — `load_user` self-heals |
| Audit Update card shows `<built-in method…>` | Hard-refresh — the template fix is `stats['update']` (cached) |
| Illustration banner missing | Hard-refresh; check `app/static/illustrations/<page>/` has files |
| Login redirects in a loop | The scoped-URL dispatcher needs a fresh session — close all tabs, reopen |
| Browser cache | Open in **Incognito** — the cleanest possible demo state |

## Time budget

| Act | Target | Hard cap |
|-----|--------|----------|
| 1 — Landing | 0:45 | 1:00 |
| 2 — Free-To-Use story | 2:00 | 3:00 |
| 3 — Audit + RBAC | 1:00 | 1:30 |
| 4 — Speed run | 1:15 | 1:30 |
| Closing | 0:30 | 0:30 |
| **Total** | **5:30** | **7:30** |

Save 1 minute for judges' questions.
