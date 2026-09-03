"""Flask application factory and entry point for the IoT Honeypot platform."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, jsonify

from config import Config
from database import csrf, db, socketio
from routes.api import api_bp
from routes.dashboard import dashboard_bp
from services.validation import ValidationError


def create_app(config_class: type[Config] = Config) -> Flask:
    """Create and configure the Flask application."""

    database_uri = config_class.SQLALCHEMY_DATABASE_URI
    if database_uri.startswith("sqlite:///"):
        Path(database_uri.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    csrf.init_app(app)
    socketio.init_app(app, async_mode=app.config["SOCKETIO_ASYNC_MODE"])

    _configure_logging(app)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    _register_error_handlers(app)
    _register_cli(app)

    return app


def _configure_logging(app: Flask) -> None:
    """Configure rotating logs for local lab observability."""

    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    handler = RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=5)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    handler.setLevel(app.config["LOG_LEVEL"])
    app.logger.addHandler(handler)
    app.logger.setLevel(app.config["LOG_LEVEL"])


def _register_error_handlers(app: Flask) -> None:
    """Return JSON errors for API clients without hiding server logs."""

    @app.errorhandler(ValidationError)
    def validation_error(error: ValidationError):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception("Unhandled server error: %s", error)
        return jsonify({"error": "internal server error"}), 500


def _register_cli(app: Flask) -> None:
    """Add CLI commands used during installation and demos."""

    @app.cli.command("init-db")
    def init_db() -> None:
        """Initialize all SQLite tables."""

        with app.app_context():
            db.create_all()
        print("Database initialized.")


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        if app.config.get("RESET_DB_ON_STARTUP", False):
            db.drop_all()
        db.create_all()
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=debug,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
