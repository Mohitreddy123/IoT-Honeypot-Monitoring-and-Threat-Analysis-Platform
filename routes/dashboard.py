"""HTML dashboard and health-check routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template

from services.event_service import dashboard_stats

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index():
    """Render the real-time monitoring dashboard."""

    return render_template("dashboard.html", stats=dashboard_stats())


@dashboard_bp.get("/health")
def health():
    """Expose a simple readiness endpoint for local checks."""

    return jsonify({"status": "ok", "service": "iot-honeypot-monitor"}), 200
