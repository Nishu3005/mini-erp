"""Application configuration. Reads from environment (.env via python-dotenv)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URI", f"sqlite:///{BASE_DIR / 'instance' / 'erp.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024          # 5 MB cap on uploads (photo)


class DevConfig(Config):
    DEBUG = True
    # Dev convenience only: a fixed key so sessions survive restarts locally.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")


class ProdConfig(Config):
    DEBUG = False
    # Prod MUST provide a real secret via the environment; no hardcoded fallback.
    # Enforced in the app factory (create_app) so a missing key fails fast at startup.
    SECRET_KEY = os.environ.get("SECRET_KEY")


config_by_name = {"dev": DevConfig, "prod": ProdConfig}
