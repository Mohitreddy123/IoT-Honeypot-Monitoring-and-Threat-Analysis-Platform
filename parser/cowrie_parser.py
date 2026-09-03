"""Cowrie JSON log parser and forwarder.

The module can be imported by the Flask app for one-shot ingestion, or executed
on a Kali VM to continuously follow ``cowrie.json`` and POST new JSON entries to
the Flask backend at ``/api/cowrie``.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def parse_cowrie_log_file(path: str | Path, api_url: str | None = None) -> dict[str, int]:
    """Read a Cowrie JSON-lines file and store or forward valid new records."""

    log_path = Path(path)
    summary = {"processed": 0, "inserted": 0, "duplicates": 0, "malformed": 0, "posted": 0}
    seen_fingerprints: set[str] = set()
    if not log_path.exists():
        raise FileNotFoundError(f"Cowrie log file not found: {log_path}")

    with log_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            result = _handle_line(line, line_number, seen_fingerprints, api_url)
            for key, value in result.items():
                summary[key] += value

    return summary


def monitor_cowrie_log(
    path: str | Path,
    api_url: str,
    poll_interval: float = 2.0,
    start_at_end: bool = True,
) -> None:
    """Continuously follow a Cowrie JSON log and POST new entries to Flask."""

    log_path = Path(path)
    seen_fingerprints: set[str] = set()
    logger.info("Monitoring Cowrie log %s and forwarding to %s", log_path, api_url)

    with log_path.open("r", encoding="utf-8") as handle:
        if start_at_end:
            handle.seek(0, 2)

        line_number = 0
        while True:
            line = handle.readline()
            if not line:
                time.sleep(poll_interval)
                continue
            line_number += 1
            _handle_line(line, line_number, seen_fingerprints, api_url)


def post_cowrie_event(api_url: str, record: dict[str, Any]) -> int:
    """POST one Cowrie event to the monitoring API using Python stdlib only."""

    body = json.dumps(record).encode("utf-8")
    request = Request(
        api_url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "cowrie-forwarder/1.0"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        response.read()
        return response.status


def _handle_line(
    line: str,
    line_number: int,
    seen_fingerprints: set[str],
    api_url: str | None,
) -> dict[str, int]:
    """Parse one JSON line, deduplicate it, and store or forward it."""

    summary = {"processed": 0, "inserted": 0, "duplicates": 0, "malformed": 0, "posted": 0}
    stripped = line.strip()
    if not stripped:
        return summary

    summary["processed"] = 1
    try:
        record: Any = json.loads(stripped)
        if not isinstance(record, dict):
            raise ValueError("Cowrie line must be a JSON object")
        fingerprint = json.dumps(record, sort_keys=True)
    except Exception as exc:
        summary["malformed"] = 1
        logger.warning("Skipped malformed Cowrie line %s: %s", line_number, exc)
        return summary

    if fingerprint in seen_fingerprints:
        summary["duplicates"] = 1
        return summary
    seen_fingerprints.add(fingerprint)

    try:
        if api_url:
            status = post_cowrie_event(api_url, record)
            if status in {200, 201}:
                summary["posted"] = 1
        else:
            from services.cowrie_service import create_cowrie_event

            _, created = create_cowrie_event(record)
            summary["inserted" if created else "duplicates"] = 1
    except (URLError, OSError, ValueError) as exc:
        summary["malformed"] = 1
        logger.warning("Failed to process Cowrie line %s: %s", line_number, exc)

    return summary


def main() -> None:
    """CLI entry point for Kali-side Cowrie forwarding."""

    parser = argparse.ArgumentParser(description="Forward Cowrie JSON logs to Flask.")
    parser.add_argument("--log", required=True, help="Path to cowrie.json")
    parser.add_argument(
        "--api",
        default="http://127.0.0.1:5000/api/cowrie",
        help="Flask /api/cowrie endpoint",
    )
    parser.add_argument("--follow", action="store_true", help="Continuously monitor the log")
    parser.add_argument("--from-start", action="store_true", help="Follow from the beginning")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.follow:
        monitor_cowrie_log(args.log, args.api, args.interval, not args.from_start)
    else:
        print(parse_cowrie_log_file(args.log, args.api))


if __name__ == "__main__":
    main()
