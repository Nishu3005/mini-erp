# Seeded profile avatars

40 portrait JPEGs (`avatar_01.jpg` … `avatar_40.jpg`) used by the seeder to give every demo
user a photo on the dashboard / profile / navigation avatar.

## How to (re)populate

The images are fetched from **pravatar.cc** (free, anonymous public faces — no auth needed).
Run **once** after cloning, or whenever you want a fresh set:

```bash
uv run python tools/fetch_avatars.py
```

The script writes `avatar_01.jpg` … `avatar_40.jpg` (~10–25 KB each) into this folder and
is **idempotent** (skips files that already exist; use `--force` to overwrite).

The seeder (`app/services/seed.py`) copies each one into
`app/static/uploads/avatars/seed/avatar_NN.jpg` and round-robin assigns them to users by
setting `user.photo_path = "uploads/avatars/seed/avatar_NN.jpg"`.
