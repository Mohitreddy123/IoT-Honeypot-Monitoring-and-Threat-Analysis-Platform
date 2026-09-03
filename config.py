"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_DB_PATH = INSTANCE_DIR / "iot_honeypot.db"


class Config:
    """Default configuration for local Windows development."""

    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 1024 * 1024))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    COWRIE_LOG_PATH = os.getenv(
        "COWRIE_LOG_PATH", str(BASE_DIR / "logs" / "cowrie.json")
    )
    SOCKETIO_ASYNC_MODE = os.getenv("SOCKETIO_ASYNC_MODE", "threading")
    RESET_DB_ON_STARTUP = os.getenv("RESET_DB_ON_STARTUP", "1") == "1"
    # Allow the frontend to request a reset when the dashboard is opened.
    RESET_ON_PAGE_LOAD = os.getenv("RESET_ON_PAGE_LOAD", "1") == "1"
