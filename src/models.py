"""Core data model."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .dedupe import dedupe_key

# Order of columns written to the Google Sheet.
SHEET_HEADERS = [
    "Date",
    "Company",
    "Role",
    "Location",
    "Link",
    "Source",
    "H1B Sponsor?",
    "Match",
    "Referral Message",
    "Applied?",
    "_key",  # hidden last column used for dedupe
]


@dataclass
class JobPosting:
    company: str
    title: str
    url: str
    location: str = ""
    source: str = ""
    posted_at: Optional[datetime] = None  # tz-aware UTC when known
    description: str = ""
    remote: Optional[bool] = None

    # Filled in by the pipeline.
    h1b_label: str = "⬜ Unknown"  # ⬜ Unknown
    h1b_count: int = 0
    match_score: float = 0.0
    referral_message: str = ""

    @property
    def key(self) -> str:
        return dedupe_key(self.company, self.title, self.url)

    def to_row(self, today: str | None = None) -> list:
        today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return [
            today,
            self.company,
            self.title,
            self.location,
            self.url,
            self.source,
            self.h1b_label,
            f"{self.match_score:.0%}" if self.match_score else "",
            self.referral_message,
            "Not applied",
            self.key,
        ]
