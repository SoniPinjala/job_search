"""H1B sponsor lookup.

Cross-references a posting's company against a table of known H1B sponsors
(data/h1b_sponsors.csv). Ships with a curated seed list so the column works
immediately; run scripts/build_h1b_dataset.py to replace it with the full
official USCIS/DOL dataset.

Caveats baked into the labels: matching is fuzzy (legal entity names differ
from brand names) and past sponsorship never guarantees a given role sponsors.
Treat it as a strong signal, not a promise.
"""
from __future__ import annotations

import csv
import logging
import pathlib
import re
from functools import lru_cache

from rapidfuzz import fuzz, process

log = logging.getLogger(__name__)

DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "h1b_sponsors.csv"
UNKNOWN = "⬜ Unknown"

_LEGAL_SUFFIXES = {
    "inc", "llc", "ltd", "corp", "corporation", "co", "company", "incorporated",
    "limited", "plc", "gmbh", "technologies", "technology", "labs", "lab",
    "group", "holdings", "solutions", "systems", "software", "international",
    "usa", "the", "and",
}


def normalize_company(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    tokens = [t for t in s.split() if t and t not in _LEGAL_SUFFIXES]
    return " ".join(tokens).strip()


class H1BIndex:
    def __init__(self, path: pathlib.Path = DATA_PATH):
        self.by_norm: dict[str, tuple[int, str]] = {}
        self.by_token: dict[str, list[str]] = {}
        self._load(path)

    def _load(self, path: pathlib.Path) -> None:
        if not path.exists():
            log.warning("h1b: no sponsor data at %s — all companies will be Unknown", path)
            return
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                norm = normalize_company(row.get("employer", ""))
                if not norm:
                    continue
                try:
                    filings = int(float(row.get("filings", 0) or 0))
                except ValueError:
                    filings = 0
                source = row.get("source", "") or ""
                prev = self.by_norm.get(norm)
                if prev is None or filings > prev[0]:
                    self.by_norm[norm] = (filings, source)
                self.by_token.setdefault(norm.split()[0], []).append(norm)
        log.info("h1b: loaded %d sponsor entries", len(self.by_norm))

    def lookup(self, company: str) -> tuple[str, int]:
        norm = normalize_company(company)
        if not norm:
            return (UNKNOWN, 0)
        hit = self.by_norm.get(norm)
        if hit is None:
            # Fuzzy fallback, scoped to the same first token for speed/precision.
            candidates = self.by_token.get(norm.split()[0], [])
            if candidates:
                match = process.extractOne(
                    norm, candidates, scorer=fuzz.token_sort_ratio, score_cutoff=88
                )
                if match:
                    hit = self.by_norm.get(match[0])
        if hit is None:
            return (UNKNOWN, 0)
        filings, source = hit
        return (self._label(filings, source), filings)

    @staticmethod
    def _label(filings: int, source: str) -> str:
        if filings >= 100:
            tier = "✅ Strong sponsor"
        elif filings >= 10:
            tier = "✅ Sponsor"
        else:
            tier = "🟡 Some H1B history"
        if source.startswith("seed"):
            return f"{tier} (known)"
        return f"{tier} ({filings:,} filings)"


@lru_cache(maxsize=1)
def _index() -> H1BIndex:
    return H1BIndex()


def lookup(company: str) -> tuple[str, int]:
    """Return (label, filings_count) for a company name."""
    return _index().lookup(company)
