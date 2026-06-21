"""Fetch 40 portrait JPEGs into mini-erp/data/avatars/ for the seeder to use.

Source: https://i.pravatar.cc  — anonymous public faces, no auth, 300x300 JPEGs.
Idempotent: skips files that already exist. Pass --force to re-fetch.

Usage:
    uv run python tools/fetch_avatars.py
    uv run python tools/fetch_avatars.py --force
    uv run python tools/fetch_avatars.py -n 50    # fetch a different count
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "avatars"
URL_TEMPLATE = "https://i.pravatar.cc/300?img={n}"   # img=1..70 are valid
TIMEOUT = 15


def _fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "mini-erp-seed/1.0"})
    with urlopen(req, timeout=TIMEOUT) as r:                # noqa: S310 (known host)
        return r.read()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", "--count", type=int, default=40, help="number of avatars (max 70)")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    count = max(1, min(args.count, 70))

    written = skipped = failed = 0
    for i in range(1, count + 1):
        target = OUT_DIR / f"avatar_{i:02d}.jpg"
        if target.exists() and not args.force:
            skipped += 1
            continue
        try:
            target.write_bytes(_fetch(URL_TEMPLATE.format(n=i)))
            written += 1
            print(f"  ok  avatar_{i:02d}.jpg")
        except (URLError, OSError) as e:
            failed += 1
            print(f"  ERR avatar_{i:02d}.jpg  ({e})", file=sys.stderr)

    print(f"\nDone — wrote {written}, skipped {skipped}, failed {failed}. -> {OUT_DIR}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
