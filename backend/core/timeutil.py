"""One UTC time semantics for the whole product backend.

The database persists NAIVE datetimes (SQLite has no time zone), and the product's
convention is that a naive persisted value is a UTC wall-clock. Python disagrees:
``naive_dt.timestamp()`` interprets a naive datetime as SERVER-LOCAL time, so the same
stored fact turns into a different epoch on every host with a non-UTC offset (8 hours on
UTC+8, invisible on a UTC host).

Every persist -> epoch conversion therefore goes through this module. Callers must not
call ``datetime.timestamp()`` on a value that came back from the database.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone


def as_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime. A naive input is READ AS UTC, never as local time."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_epoch(value) -> float | None:
    """UTC epoch seconds for an aware/naive datetime, ISO-8601 string, or epoch number.

    Naive datetimes and ISO strings without an offset are interpreted as UTC. ``None``
    and ``""`` yield ``None``; a malformed string raises ``ValueError``.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"invalid datetime {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        return as_utc(value).timestamp()
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid datetime {value!r}") from exc
    return as_utc(parsed).timestamp()


def to_epoch_or_now(value) -> float:
    """``to_epoch`` with a real-wall-clock fallback for a missing timestamp."""
    epoch = to_epoch(value)
    return time.time() if epoch is None else epoch
