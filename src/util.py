"""Small shared helpers: date parsing + HTML stripping."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Optional

from dateutil import parser as _dateparser


def parse_dt(value) -> Optional[datetime]:
    """Parse ISO strings or epoch (seconds/ms) into tz-aware UTC. None on failure."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)):
            ts = value / 1000 if value > 1e12 else value
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        s = str(value).strip()
        if s.isdigit():
            v = int(s)
            ts = v / 1000 if v > 1e12 else v
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        dt = _dateparser.parse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError, OSError, TypeError):
        return None


def strip_html(text: str, limit: int = 2500) -> str:
    if not text:
        return ""
    # Unescape FIRST so double-escaped markup (&lt;h2&gt;) becomes real tags we
    # can then strip — otherwise tag names leak into the text as noise words.
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def pretty_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()
