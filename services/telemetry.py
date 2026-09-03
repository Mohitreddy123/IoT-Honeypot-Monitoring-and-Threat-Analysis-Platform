"""Telemetry services for ESP32 devices, dashboard searches, and statistics."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func

from database import db
from models import CowrieEvent, Device, Event, utc_now
from services.validation import (
    ValidationError,
    optional_string,
    parse_timestamp,
    required_string,
    validate_ip,
    validate_severity,
    validate_status,
)


def create_event(data: dict[str, Any], remote_addr: str | None = None) -> Event:
    """Validate and persist an ESP32 telemetry event.

    The endpoint accepts simple event payloads, such as boot messages, and
    sensor-style heartbeat payloads with fields like temperature and humidity.
    Non-core telemetry fields are stored as a JSON payload for later analysis.
    """

    event_type = required_string(data, "event_type", 80)
    severity = validate_severity(optional_string(data, "severity", 30, "info") or "info")
    device_name = required_string(data, "device_name", 120)
    source_ip = validate_ip(optional_string(data, "source_ip", 45) or remote_addr)
    timestamp = parse_timestamp(data.get("timestamp")) or utc_now()
    payload_text = _normalize_payload(data)

    event = Event(
        timestamp=timestamp,
        source_ip=source_ip,
        event_type=event_type,
        severity=severity,
        payload=payload_text,
        device_name=device_name,
    )
    db.session.add(event)
    _upsert_device_from_event(device_name, source_ip, event_type, payload_text)
    db.session.commit()
    return event


def create_device(data: dict[str, Any]) -> tuple[Device, bool]:
    """Create or update a device registration from validated JSON."""

    device_name = required_string(data, "device_name", 120)
    device_ip = validate_ip(required_string(data, "device_ip", 45), "device_ip")
    status = validate_status(optional_string(data, "status", 30, "unknown") or "unknown")

    device = Device.query.filter_by(device_name=device_name).first()
    created = device is None
    if created:
        device = Device(device_name=device_name, device_ip=device_ip or "", status=status)
        db.session.add(device)
    else:
        device.device_ip = device_ip or device.device_ip
        device.status = status

    db.session.commit()
    return device, created


def list_events(
    limit: int = 100,
    source_ip: str | None = None,
    device_name: str | None = None,
    event_type: str | None = None,
) -> list[Event]:
    """Return recent telemetry events with optional dashboard/API filters."""

    query = Event.query
    if source_ip:
        query = query.filter(Event.source_ip == validate_ip(source_ip))
    if device_name:
        query = query.filter(Event.device_name.ilike(f"%{device_name}%"))
    if event_type:
        query = query.filter(Event.event_type.ilike(f"%{event_type}%"))
    return query.order_by(Event.timestamp.desc(), Event.id.desc()).limit(limit).all()


def list_devices() -> list[Device]:
    """Return all registered IoT devices."""

    return Device.query.order_by(Device.created_at.desc(), Device.id.desc()).all()


def dashboard_stats() -> dict[str, Any]:
    """Aggregate dashboard counters, chart series, and recent activity."""

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    total_events = Event.query.count()
    total_devices = Device.query.count()
    cowrie_events = CowrieEvent.query.count()
    last_24h = Event.query.filter(Event.timestamp >= since).count()

    recent_events = [event.to_dict() for event in list_events(10)]
    recent_cowrie = [
        event.to_dict()
        for event in CowrieEvent.query.order_by(
            CowrieEvent.timestamp.desc(), CowrieEvent.id.desc()
        )
        .limit(10)
        .all()
    ]

    hour_labels = [(since + timedelta(hours=i)).strftime("%H:00") for i in range(25)]
    hour_counts = dict.fromkeys(hour_labels, 0)
    for event in Event.query.filter(Event.timestamp >= since).all():
        label = event.timestamp.strftime("%H:00")
        hour_counts[label] = hour_counts.get(label, 0) + 1

    severity_rows = db.session.query(Event.severity, func.count(Event.id)).group_by(Event.severity)
    type_rows = db.session.query(Event.event_type, func.count(Event.id)).group_by(Event.event_type)

    return {
        "total_events": total_events,
        "total_devices": total_devices,
        "cowrie_events": cowrie_events,
        "last_24h": last_24h,
        "recent_events": recent_events,
        "recent_cowrie": recent_cowrie,
        "events_by_hour": {
            "labels": list(hour_counts.keys()),
            "values": list(hour_counts.values()),
        },
        "events_by_severity": _rows_to_chart(severity_rows),
        "events_by_type": _rows_to_chart(type_rows),
    }


def _normalize_payload(data: dict[str, Any]) -> str:
    """Store explicit payload text or JSON sensor fields as the event payload."""

    if "payload" in data:
        payload = data["payload"]
        payload_text = payload if isinstance(payload, str) else json.dumps(payload)
    else:
        excluded = {"device_name", "source_ip", "event_type", "severity", "timestamp"}
        telemetry_fields = {key: value for key, value in data.items() if key not in excluded}
        if not telemetry_fields:
            raise ValidationError("'payload' or telemetry fields are required")
        payload_text = json.dumps(telemetry_fields, sort_keys=True)

    if len(payload_text) > 10000:
        raise ValidationError("'payload' must be 10000 characters or fewer")
    return payload_text


def _upsert_device_from_event(
    device_name: str, source_ip: str | None, event_type: str, payload_text: str
) -> None:
    """Keep the device registry current as telemetry arrives."""

    device = Device.query.filter_by(device_name=device_name).first()
    if device is None:
        device = Device(
            device_name=device_name,
            device_ip=source_ip or "0.0.0.0",
            status="online",
        )
        db.session.add(device)
        return

    if source_ip:
        device.device_ip = source_ip
    if event_type in {"boot", "heartbeat", "device_status"}:
        if payload_text.lower() in {"online", "offline", "maintenance"}:
            device.status = payload_text.lower()
        else:
            device.status = "online"


def _rows_to_chart(rows: Any) -> dict[str, list[Any]]:
    """Convert aggregate SQL rows into Chart.js data arrays."""

    counter = Counter({label or "unknown": count for label, count in rows})
    return {"labels": list(counter.keys()), "values": list(counter.values())}
