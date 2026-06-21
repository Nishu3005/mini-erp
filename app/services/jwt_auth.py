"""JWT auth for the /api/v1 surface (see spec/jwt-api.md).

Symmetric HS256 signed with app.config["SECRET_KEY"] — same secret the session cookies use, so
there's one source of truth. The browser flow (Flask-Login + sessions) is untouched.
"""
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from app.extensions import db
from app.models.user import User


ALGORITHM = "HS256"
DEFAULT_EXPIRES_SECONDS = 3600
TOKEN_VERSION = 1


def encode_for(user) -> tuple[str, int]:
    """Mint a JWT for `user`. Returns (token_string, expires_in_seconds)."""
    expires_in = int(current_app.config.get("JWT_EXPIRES_SECONDS", DEFAULT_EXPIRES_SECONDS))
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user.id),         # JWT RFC 7519: 'sub' MUST be a string; PyJWT 2.13+ enforces.
        "login": user.login_id,
        "role": "admin" if user.is_admin else (user.role or None),
        "is_admin": bool(user.is_admin),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
        "v": TOKEN_VERSION,
    }
    token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=ALGORITHM)
    return token, expires_in


def decode(token: str) -> dict:
    """Decode + verify a JWT; raises jwt.PyJWTError on any failure."""
    return jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=[ALGORITHM])


def _err(msg: str, status: int):
    return jsonify({"error": msg}), status


def require_token(view):
    """Decorator: 401 unless a valid Bearer token is present. Sets g.api_user."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return _err("missing bearer token", 401)
        token = auth.split(" ", 1)[1].strip()
        try:
            claims = decode(token)
        except jwt.ExpiredSignatureError:
            return _err("token expired", 401)
        except jwt.PyJWTError:
            return _err("invalid token", 401)

        user = db.session.get(User, int(claims.get("sub")))
        if user is None:
            return _err("invalid token", 401)
        if not user.is_admin and user.status != "active":
            return _err("account pending approval", 403)

        g.api_user = user
        g.api_claims = claims
        return view(*args, **kwargs)
    return wrapped
