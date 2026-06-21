# Illustration generator

Generates per-page footer illustrations via the TokenRouter OpenAI-compatible API
(model: `bytedance-seed/seedream-4.5`). Writes images into `app/static/illustrations/<page>/`.

## One-time setup

```bash
# install the optional dependency (only needed when running the generator)
uv sync --group illustrations

# Provide the TokenRouter key in EITHER way:
#   (a) add it to mini-erp/.env (no need to export):
#       TOKENROUTER_API_KEY=tk_...
#   (b) or export it for the shell session:
#       export TOKENROUTER_API_KEY=tk_...
```

## Generate images

```bash
# 1 image for the sales page
uv run python -m tools.illustrations.generate sales

# 3 images for sales
uv run python -m tools.illustrations.generate sales -n 3

# 1 image for every page listed in prompts.py
uv run python -m tools.illustrations.generate --all-pages

# 1 image per page, twice round (e.g. 2 per page)
uv run python -m tools.illustrations.generate --all-pages -n 2
```

Each page folder keeps a `manifest.json` of prompts already used so re-running never picks the
same prompt twice (use `--force` to override).

## How the app uses them

`base.html` includes `partials/page_illustration.html` after every page. That partial reads
`illustration_page` set at the top of each page's `{% block content %}` (e.g.
`{% set illustration_page = "sales" %}`) and renders a banner with one random image from
`static/illustrations/<page>/`. If the folder is empty, nothing renders — the app stays clean
out-of-the-box.

## Style

Edit `prompts.py` to change the **shared `STYLE` brief** (line art, yellow accent, landscape)
or the **per-page scene seeds**. The generator combines the seed with a small twist + the brief
to produce the final prompt.

## Pages with seeds

`dashboard, sales, purchase, manufacturing, bom, product, audit, admin, profile, auth,
landing, errors` — see `prompts.SCENES`.
