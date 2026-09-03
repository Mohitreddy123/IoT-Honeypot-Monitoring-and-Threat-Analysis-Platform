"""JSON REST API routes for telemetry, devices, Cowrie, and statistics."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from database import csrf, socketio, db
from flask import current_app
from parser.cowrie_parser import parse_cowrie_log_file
from services.cowrie_service import create_cowrie_event, recent_cowrie_events
from services.telemetry import (
    create_device,
    create_event,
    dashboard_stats,
    list_devices,
    list_events,
)
from services.validation import ValidationError, optional_string, require_json

api_bp = Blueprint("api", __name__, url_prefix="/api")
csrf.exempt(api_bp)


@api_bp.errorhandler(ValidationError)
def handle_validation_error(error: ValidationError):
    """Return consistent 400 responses for invalid JSON bodies."""

    return jsonify({"error": str(error)}), 400


@api_bp.errorhandler(FileNotFoundError)
def handle_missing_file(error: FileNotFoundError):
    """Return a clear 404 when a requested Cowrie log file does not exist."""

    return jsonify({"error": str(error)}), 404


@api_bp.post("/log")
def post_log():
    """Accept ESP32 telemetry and broadcast it in real time."""

    data = require_json(request)
    event = create_event(data, request.remote_addr)
    socketio.emit("new_event", event.to_dict())
    socketio.emit("stats_update", dashboard_stats())
    return jsonify({"message": "event stored", "event": event.to_dict()}), 201


@api_bp.get("/logs")
def get_logs():
    """Return recent ESP32 telemetry events."""

    limit = _query_limit()
    source_ip = request.args.get("source_ip") or None
    device_name = request.args.get("device_name") or None
    event_type = request.args.get("event_type") or None
    events = list_events(limit, source_ip, device_name, event_type)
    return jsonify({"logs": [event.to_dict() for event in events]}), 200


@api_bp.post("/device")
def post_device():
    """Register or update an ESP32 device."""

    data = require_json(request)
    device, created = create_device(data)
    socketio.emit("stats_update", dashboard_stats())
    return (
        jsonify({"message": "device stored", "device": device.to_dict()}),
        201 if created else 200,
    )


@api_bp.get("/devices")
def get_devices():
    """Return all registered devices."""

    return jsonify({"devices": [device.to_dict() for device in list_devices()]}), 200


@api_bp.get("/device")
def get_device_alias():
    """Return devices through the singular endpoint requested by the project spec."""

    return get_devices()


@api_bp.post("/cowrie")
def post_cowrie():
    """Accept a Cowrie JSON event or ingest a configured Cowrie log file."""

    data = require_json(request)
    log_path = optional_string(data, "log_path", 500)
    if log_path:
        summary = parse_cowrie_log_file(log_path)
        socketio.emit("stats_update", dashboard_stats())
        return jsonify({"message": "cowrie file parsed", "summary": summary}), 200

    event, created = create_cowrie_event(data)
    if created:
        socketio.emit("new_cowrie", event.to_dict())
        socketio.emit("stats_update", dashboard_stats())
    return (
        jsonify(
            {
                "message": "cowrie event stored" if created else "duplicate ignored",
                "cowrie_event": event.to_dict(),
            }
        ),
        201 if created else 200,
    )


@api_bp.get("/cowrie")
def get_cowrie():
    """Return recent Cowrie activity."""

    limit = _query_limit()
    source_ip = request.args.get("source_ip") or None
    events = recent_cowrie_events(limit, source_ip)
    return jsonify({"cowrie": [event.to_dict() for event in events]}), 200


@api_bp.get("/stats")
def get_stats():
    """Return dashboard counters and chart data."""

    return jsonify(dashboard_stats()), 200


@api_bp.post("/reset")
def reset_db():
    """Reset the SQLite schema when requested by the dashboard (development only)."""

    if not current_app.config.get("RESET_ON_PAGE_LOAD", False):
        return jsonify({"error": "reset disabled"}), 403

    from flask import current_app as app

    with app.app_context():
        db.drop_all()
        db.create_all()
    return jsonify({"message": "database reset"}), 200


def _query_limit(default: int = 100, maximum: int = 500) -> int:
    """Clamp optional limit query parameters to protect the app."""

    try:
        value = int(request.args.get("limit", default))
    except ValueError:
        raise ValidationError("'limit' must be an integer") from None
    return max(1, min(value, maximum))
