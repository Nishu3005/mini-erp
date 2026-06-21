"""Illustration generator — calls TokenRouter (bytedance-seed/seedream-4.5) and writes images
into app/static/illustrations/<page>/.

Usage examples (from the mini-erp/ folder):
    uv run python -m tools.illustrations.generate sales          # 1 new image for the sales page
    uv run python -m tools.illustrations.generate sales -n 3     # 3 new images
    uv run python -m tools.illustrations.generate --all-pages    # 1 image per page in prompts.py

Environment:
    TOKENROUTER_API_KEY   required (also read from mini-erp/.env if present)
    TOKENROUTER_BASE_URL  optional, defaults to https://api.tokenrouter.com

The endpoint returns base64-encoded image content OR a URL inside an OpenAI-compatible message.
This script handles both shapes. Images are stored as .webp where possible (smaller), .png otherwise.
A small manifest.json per page tracks which prompts have been used, so re-running never produces
a duplicate prompt unless --force is passed.
"""
import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from openai import OpenAI  # uses OpenAI-compatible TokenRouter API

from tools.illustrations.prompts import SCENES, build_prompt


def _load_dotenv() -> None:
    """Load mini-erp/.env into os.environ if present (no python-dotenv dependency)."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # don't clobber values already set in the real environment
        os.environ.setdefault(key, value)


_load_dotenv()


ROOT = Path(__file__).resolve().parents[2]                # mini-erp/
OUT_ROOT = ROOT / "app" / "static" / "illustrations"
DEFAULT_MODEL = "bytedance-seed/seedream-4.5"
DEFAULT_BASE = "https://api.tokenrouter.com"


def _client() -> OpenAI:
    key = os.environ.get("TOKENROUTER_API_KEY")
    if not key:
        sys.exit("Set TOKENROUTER_API_KEY in the environment.")
    return OpenAI(base_url=os.environ.get("TOKENROUTER_BASE_URL", DEFAULT_BASE), api_key=key)


def _slug(s: str, n: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:n] or "img"


def _page_dir(page: str) -> Path:
    d = OUT_ROOT / page
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manifest(page_dir: Path) -> dict:
    p = page_dir / "manifest.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"prompts_used": [], "files": []}


def _save_manifest(page_dir: Path, m: dict) -> None:
    (page_dir / "manifest.json").write_text(
        json.dumps(m, indent=2), encoding="utf-8")


def _extract_image(content: str) -> tuple[bytes, str]:
    """Pull bytes + extension from a model reply that may contain a URL or base64 data URI.

    Returns (image_bytes, file_extension_with_dot).
    """
    # data:image/<ext>;base64,<b64...>
    m = re.search(r"data:image/(\w+);base64,([A-Za-z0-9+/=]+)", content)
    if m:
        return base64.b64decode(m.group(2)), "." + m.group(1).lower()
    # bare http(s) URL to an image
    m = re.search(r"https?://\S+\.(?:webp|png|jpg|jpeg|gif)", content, flags=re.I)
    if m:
        url = m.group(0)
        with urlopen(url, timeout=60) as resp:
            data = resp.read()
        ext = os.path.splitext(urlparse(url).path)[1].lower() or ".png"
        return data, ext
    raise RuntimeError(f"Could not parse an image from model reply: {content[:200]}…")


def _generate_one(client: OpenAI, model: str, prompt: str) -> tuple[bytes, str]:
    """One round-trip to TokenRouter's chat/completions; returns (image_bytes, ext).

    TokenRouter routes image models through /v1/chat/completions (not /v1/images/generations
    — that endpoint returns 404). The image comes back in a non-standard `message.images[]`
    field as a data: URL; we also fall back to scanning `message.content` for embedded URLs/b64.
    """
    # Skip the OpenAI SDK entirely — it strips the non-standard `images[]` field and
    # TokenRouter's response body has leading whitespace that breaks SDK parsing anyway.
    import urllib.request, urllib.error
    key = os.environ["TOKENROUTER_API_KEY"]
    base = os.environ.get("TOKENROUTER_BASE_URL", DEFAULT_BASE).rstrip("/")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        f"{base}/v1/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:    # noqa: S310 (known host)
        text = r.read().decode("utf-8", errors="replace")
    brace = text.find("{")
    if brace > 0:
        text = text[brace:]
    payload = json.loads(text)
    msg = payload.get("choices", [{}])[0].get("message", {}) or {}
    images = msg.get("images") or []
    if images:
        url = (images[0].get("image_url") or {}).get("url", "")
        if url:
            return _extract_image(url)
    # Some providers return the data URL inline in content
    content = msg.get("content") or ""
    if content:
        return _extract_image(content)
    raise RuntimeError(f"No image in reply: {str(payload)[:300]}")


def generate_for_page(page: str, n: int = 1, *, model: str = DEFAULT_MODEL,
                      force: bool = False) -> list[str]:
    """Generate `n` new images for `page`. Returns the relative filenames written."""
    page_dir = _page_dir(page)
    manifest = _manifest(page_dir)
    used = set(manifest["prompts_used"])
    client = _client()
    written = []

    next_index = len(manifest["files"])
    attempts = 0
    while len(written) < n and attempts < n * 4:
        attempts += 1
        prompt = build_prompt(page, next_index + attempts)
        if prompt in used and not force:
            continue
        try:
            data, ext = _generate_one(client, model, prompt)
        except Exception as e:
            print(f"[warn] {page} prompt-{next_index + attempts}: {e}", file=sys.stderr)
            time.sleep(1); continue
        fname = f"{next_index + len(written) + 1:03d}-{_slug(prompt)}{ext}"
        (page_dir / fname).write_bytes(data)
        manifest["files"].append(fname)
        manifest["prompts_used"].append(prompt)
        used.add(prompt)
        _save_manifest(page_dir, manifest)
        written.append(fname)
        print(f"  + {page}/{fname}")
    return written


def main():
    ap = argparse.ArgumentParser(description="Generate footer illustrations via TokenRouter.")
    ap.add_argument("page", nargs="?", help="page key (sales, purchase, ...). Omit with --all-pages.")
    ap.add_argument("-n", type=int, default=1, help="how many new images for this page (default 1)")
    ap.add_argument("--all-pages", action="store_true",
                    help="generate 1 image for every page listed in prompts.SCENES")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--force", action="store_true",
                    help="allow re-using a prompt that's already in the manifest")
    args = ap.parse_args()

    if args.all_pages:
        for page in SCENES:
            print(f"[{page}]")
            generate_for_page(page, n=args.n, model=args.model, force=args.force)
    else:
        if not args.page:
            ap.error("provide a page name or --all-pages")
        if args.page not in SCENES:
            ap.error(f"unknown page '{args.page}'. Known: {sorted(SCENES)}")
        generate_for_page(args.page, n=args.n, model=args.model, force=args.force)


if __name__ == "__main__":
    main()
