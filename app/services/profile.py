"""Profile (User Login Detail Management) service.

Enforces the field-edit rules from the wireframe:
  - Name / Address / Mobile : user-editable
  - Email                   : immutable (identity; never changed here)
  - Position                : read-only here (admin-only)
  - Photo                   : upload/replace, saved to disk; path stored on the user row.
See spec/pages/user/profile.md.
"""
import os
import uuid
from pathlib import Path

from werkzeug.utils import secure_filename

from app.extensions import db
from app.services import audit

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _upload_dir() -> Path:
    # app/static/uploads/avatars
    d = Path(__file__).resolve().parents[1] / "static" / "uploads" / "avatars"
    d.mkdir(parents=True, exist_ok=True)
    return d


def update_self(user, data: dict, photo_file=None) -> None:
    """Apply a user's edits to their OWN profile. Email/Position are ignored if sent."""
    tracked = {
        "name": (data.get("name") or "").strip() or None,
        "address": (data.get("address") or "").strip() or None,
        "mobile": (data.get("mobile") or "").strip() or None,
    }
    for field, new in tracked.items():
        old = getattr(user, field)
        if (old or None) != new:
            audit.log("audit", user.login_id, "User", "write",
                      field=field, old_value=old, new_value=new)
            setattr(user, field, new)

    if photo_file and photo_file.filename:
        _save_photo(user, photo_file)

    db.session.commit()


# magic-byte signatures for the formats we accept (defense beyond extension).
_MAGIC = {
    b"\x89PNG\r\n\x1a\n": {".png"},
    b"\xff\xd8\xff": {".jpg", ".jpeg"},
    b"GIF87a": {".gif"}, b"GIF89a": {".gif"},
    b"RIFF": {".webp"},   # RIFF....WEBP
}


def _sniff_ok(head: bytes, ext: str) -> bool:
    for sig, exts in _MAGIC.items():
        if head.startswith(sig) and ext in exts:
            if sig == b"RIFF":
                return head[8:12] == b"WEBP"
            return True
    return False


def _save_photo(user, photo_file) -> None:
    ext = os.path.splitext(secure_filename(photo_file.filename))[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("Photo must be an image (png/jpg/jpeg/gif/webp).")
    # Verify the actual file content matches the claimed type (not just the extension).
    head = photo_file.stream.read(12)
    photo_file.stream.seek(0)
    if not _sniff_ok(head, ext):
        raise ValueError("That file does not look like a valid image.")
    fname = f"{user.id}_{uuid.uuid4().hex[:8]}{ext}"
    photo_file.save(_upload_dir() / fname)
    # store a path relative to /static for url_for('static', filename=...)
    user.photo_path = f"uploads/avatars/{fname}"
    audit.log("audit", user.login_id, "User", "write", field="photo", new_value=fname)
