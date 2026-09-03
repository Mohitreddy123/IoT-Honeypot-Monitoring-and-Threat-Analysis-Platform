"""Business logic for ingesting Cowrie honeypot JSON events."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from database import db
from models import CowrieEvent, utc_now
from services.validation import (
    ValidationError,
    optional_string,
    parse_timestamp,
    required_string,
    validate_ip,
)


def create_cowrie_event(data: dict[str, Any]) -> tuple[CowrieEvent, bool]:
    """Create a Cowrie event, ignoring an existing duplicate."""

    eventid = required_string(data, "eventid", 120)
    timestamp = _cowrie_timestamp(data) or utc_now()
    source_ip = _cowrie_source_ip(data)
    username = optional_string(data, "username", 120)
    raw_json = json.dumps(data, sort_keys=True)

    existing = CowrieEvent.query.filter_by(
        timestamp=timestamp,
        source_ip=source_ip,
        eventid=eventid,
        raw_json=raw_json,
    ).first()
    if existing:
        return existing, False

    event = CowrieEvent(
        timestamp=timestamp,
        source_ip=source_ip,
        username=username,
        eventid=eventid,
        raw_json=raw_json,
    )
    db.session.add(event)
    db.session.commit()
    return event, True


def recent_cowrie_events(limit: int = 100, source_ip: str | None = None) -> list[CowrieEvent]:
    """Return recent Cowrie events for API consumers, optionally filtered by IP."""

    query = CowrieEvent.query
    if source_ip:
        query = query.filter(CowrieEvent.source_ip == validate_ip(source_ip))
    return query.order_by(CowrieEvent.timestamp.desc(), CowrieEvent.id.desc()).limit(limit).all()


def _cowrie_timestamp(data: dict[str, Any]) -> datetime | None:
    """Cowrie commonly sends 'timestamp', but keep the parser tolerant."""

    return parse_timestamp(data.get("timestamp"))


def _cowrie_source_ip(data: dict[str, Any]) -> str | None:
    """Read Cowrie source IP from common field names."""

    value = data.get("src_ip") or data.get("source_ip") or data.get("peerIP")
    if value is not None and not isinstance(value, str):
        raise ValidationError("'src_ip' must be a string when provided")
    return validate_ip(value, "src_ip")
