"""Timestamp normalization helpers shared by desktop controllers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_utc_datetime(value: Any) -> datetime | None:
    """Return an aware UTC datetime from API ISO strings or Firestore-like values."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        elif callable(getattr(value, "to_datetime", None)):
            parsed = value.to_datetime()
        else:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None
