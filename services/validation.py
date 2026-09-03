"""Small JSON validation helpers for defensive API endpoints."""

from __future__ import annotations

import ipaddress
from datetime import datetime
from typing import Any

from flask import Request

ALLOWED_SEVERITIES = {"info", "low", "medium", "high", "critical", "warning", "error"}
ALLOWED_DEVICE_STATUSES = {"online", "offline", "unknown", "maintenance"}


class ValidationError(ValueError):
    """Raised when an API request contains invalid JSON or fields."""


def require_json(request: Request) -> dict[str, Any]:
    """Return a JSON object or raise a validation error."""

    if not request.is_json:
        raise ValidationError("Request must use application/json")
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("JSON body must be an object")
    return payload


def required_string(data: dict[str, Any], field: str, max_length: int = 255) -> str:
    """Read and validate a required non-empty string field."""

    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"'{field}' is required and must be a non-empty string")
    value = value.strip()
    if len(value) > max_length:
        raise ValidationError(f"'{field}' must be {max_length} characters or fewer")
    return value


def optional_string(
    data: dict[str, Any], field: str, max_length: int = 255, default: str | None = None
) -> str | None:
    """Read and validate an optional string field."""

    value = data.get(field, default)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"'{field}' must be a string")
    value = value.strip()
    if len(value) > max_length:
        raise ValidationError(f"'{field}' must be {max_length} characters or fewer")
    return value


def validate_ip(value: str | None, field: str = "source_ip") -> str | None:
    """Validate IPv4 or IPv6 text when a client provides an address."""

    if not value:
        return None
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValidationError(f"'{field}' must be a valid IP address") from exc
    return value


def validate_severity(value: str) -> str:
    """Normalize and validate event severity."""

    normalized = value.lower()
    if normalized not in ALLOWED_SEVERITIES:
        allowed = ", ".join(sorted(ALLOWED_SEVERITIES))
        raise ValidationError(f"'severity' must be one of: {allowed}")
    return normalized


def validate_status(value: str) -> str:
    """Normalize and validate device status."""

    normalized = value.lower()
    if normalized not in ALLOWED_DEVICE_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_DEVICE_STATUSES))
        raise ValidationError(f"'status' must be one of: {allowed}")
    return normalized


def parse_timestamp(value: Any) -> datetime | None:
    """Parse ISO 8601 timestamps while allowing defaults."""

    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("'timestamp' must be an ISO 8601 string")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("'timestamp' must be a valid ISO 8601 string") from exc
