"""Role/description matching, freshness proxy, and US-location filtering.

Why a freshness proxy: real applicant counts aren't available for free or in a
ToS-compliant way (LinkedIn gates them; Indeed/company sites don't expose them).
A posting first seen within `max_age_hours` is the best free signal for "few
applicants so far". Dedupe guarantees each job is only ever counted as new once.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .models import JobPosting

_STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will", "have",
    "this", "that", "from", "all", "who", "has", "able", "etc", "join", "team",
    "work", "working", "role", "job", "looking", "experience", "years", "year",
    "skills", "strong", "build", "building", "using", "use", "across", "into",
    "new", "world", "help", "make", "want", "open", "based", "including", "like",
}


def _tokens(text: str) -> list[str]:
    raw = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.]{1,}", (text or "").lower())
    return [w for w in raw if len(w) > 2 and w not in _STOPWORDS]


def keyword_set(text: str) -> set[str]:
    return set(_tokens(text))


def title_matches_roles(title: str, roles: Iterable[str]) -> bool:
    t = (title or "").lower()
    return any(r.lower() in t for r in roles)


def title_excluded(title: str, exclude: Iterable[str]) -> bool:
    t = (title or "").lower()
    return any(str(k).lower() in t for k in (exclude or []))


def match_score(text: str, desc_keywords: set[str]) -> float:
    """Fraction of the description's keywords that appear in the posting."""
    if not desc_keywords:
        return 0.0
    words = keyword_set(text)
    return len(words & desc_keywords) / len(desc_keywords)


def is_fresh(posting: JobPosting, max_age_hours: int, now: datetime | None = None) -> bool:
    if posting.posted_at is None:
        return True  # unknown date -> dedupe makes it "new to us" exactly once
    now = now or datetime.now(timezone.utc)
    pa = posting.posted_at
    if pa.tzinfo is None:
        pa = pa.replace(tzinfo=timezone.utc)
    return (now - pa) <= timedelta(hours=max_age_hours)


# --- US location detection -------------------------------------------------
_US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "ohio", "oklahoma", "oregon",
    "pennsylvania", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "wisconsin", "wyoming",
}
_US_ABBR = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id",
    "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms",
    "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok",
    "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv",
    "wi", "wy", "dc",
}
_US_KEYWORDS = ("united states", "usa", "u.s.", "u.s", "remote - us", "remote (us")
# Country/region names that mean a posting is NOT US (kills "Remote - Canada" etc).
_NON_US = {
    "canada", "united kingdom", "england", "scotland", "uk", "ireland", "india",
    "germany", "france", "spain", "netherlands", "poland", "romania", "portugal",
    "brazil", "mexico", "argentina", "australia", "singapore", "japan", "china",
    "israel", "emea", "apac", "latam", "europe", "european", "dubai", "uae",
    "philippines", "ukraine", "sweden", "switzerland", "italy", "austria",
    "belgium", "denmark", "norway", "finland", "czechia", "czech", "hungary",
    "bulgaria", "greece", "turkey", "new zealand", "colombia", "chile", "peru",
    "costa rica", "kenya", "nigeria", "egypt", "vietnam", "thailand", "indonesia",
    "malaysia", "korea", "taiwan", "hong kong", "south africa", "lithuania",
}


def in_us(location: str, remote: bool | None, places: list[str] | None = None) -> bool:
    loc = (location or "").lower()
    places = [p.lower() for p in (places or [])]

    if places:  # explicit whitelist takes precedence
        return any(p in loc for p in places)

    if not loc:
        # Unknown location: keep remote-flagged jobs, drop the rest as too risky.
        return bool(remote)

    tokens = set(re.findall(r"[a-z.]+", loc))
    has_us = (
        any(k in loc for k in _US_KEYWORDS)
        or bool(tokens & _US_STATES)
        or bool({t.strip(".") for t in tokens} & _US_ABBR)
        or "us" in tokens or "usa" in tokens
    )
    if has_us:
        return True
    if any(c in loc for c in _NON_US):
        return False
    # Bare "Remote" with no country at all -> treat as US-eligible (our sources
    # query US); anything else with a real place name but no US signal is dropped.
    return "remote" in loc


def filter_and_score(postings: Iterable[JobPosting], cfg: dict,
                     now: datetime | None = None) -> list[JobPosting]:
    roles = cfg.get("roles", [])
    f = cfg.get("filters", {})
    loc_cfg = cfg.get("location", {})
    places = loc_cfg.get("places") or []
    min_score = float(f.get("min_match_score", 0.0))
    max_age = int(f.get("max_age_hours", 6))
    exclude = f.get("exclude_title_keywords", [])

    # Keywords that describe the user, minus the role words themselves.
    desc_kw = keyword_set(cfg.get("description", "")) - keyword_set(" ".join(roles))

    kept: list[JobPosting] = []
    for p in postings:
        if not title_matches_roles(p.title, roles):
            continue
        if title_excluded(p.title, exclude):
            continue
        if loc_cfg.get("country", "us") == "us" and not in_us(p.location, p.remote, places):
            continue
        if not is_fresh(p, max_age, now):
            continue
        score = match_score(f"{p.title} {p.description}", desc_kw)
        # Only enforce the score gate when there's enough text to judge.
        if len(p.description or "") >= 40 and score < min_score:
            continue
        p.match_score = round(score, 3)
        kept.append(p)
    return kept
