"""Free aggregator APIs: Adzuna, Jooble, JSearch (Google-for-Jobs).

Each issues ONE combined query per run to stay comfortably inside free tiers
(we recover precision later with our own title/keyword filter). JSearch is
`tier="deep"` because its free quota is ~200 calls/MONTH — it only runs in the
slower crawl.
"""
from __future__ import annotations

import logging

from ..config import env
from ..models import JobPosting
from ..util import parse_dt, strip_html
from .base import Source, http_get, http_post

log = logging.getLogger(__name__)


def _is_remote(*parts: str) -> bool | None:
    blob = " ".join(p for p in parts if p).lower()
    if "remote" in blob:
        return True
    return None


class Adzuna(Source):
    name = "adzuna"
    tier = "frequent"

    @property
    def enabled(self) -> bool:
        return bool(env("ADZUNA_APP_ID") and env("ADZUNA_APP_KEY"))

    def fetch(self, cfg):
        roles = cfg.get("roles", [])
        country = (cfg.get("location", {}).get("country") or "us").lower()
        max_age = int(cfg.get("filters", {}).get("max_age_hours", 6))
        days = max(1, round(max_age / 24))
        resp = http_get(
            f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
            params={
                "app_id": env("ADZUNA_APP_ID"),
                "app_key": env("ADZUNA_APP_KEY"),
                "results_per_page": 50,
                "what_or": " ".join(roles),
                "max_days_old": days,
                "sort_by": "date",
                "content-type": "application/json",
            },
        )
        if resp is None:
            log.warning("adzuna: request failed")
            return []
        try:
            results = resp.json().get("results", [])
        except ValueError:
            return []
        out = []
        for j in results:
            loc = (j.get("location") or {}).get("display_name", "")
            title = j.get("title", "")
            desc = strip_html(j.get("description", ""))
            out.append(JobPosting(
                company=(j.get("company") or {}).get("display_name", "") or "Unknown",
                title=title,
                url=j.get("redirect_url", ""),
                location=loc,
                source="adzuna",
                posted_at=parse_dt(j.get("created")),
                description=desc,
                remote=_is_remote(title, loc, desc),
            ))
        log.info("adzuna: %d results", len(out))
        return out


class Jooble(Source):
    name = "jooble"
    tier = "frequent"

    @property
    def enabled(self) -> bool:
        return bool(env("JOOBLE_KEY"))

    def fetch(self, cfg):
        roles = cfg.get("roles", [])
        resp = http_post(
            f"https://jooble.org/api/{env('JOOBLE_KEY')}",
            json={"keywords": ", ".join(roles), "location": "USA", "page": "1"},
        )
        if resp is None:
            log.warning("jooble: request failed")
            return []
        try:
            jobs = resp.json().get("jobs", [])
        except ValueError:
            return []
        out = []
        for j in jobs:
            title = j.get("title", "")
            loc = j.get("location", "")
            snippet = strip_html(j.get("snippet", ""))
            out.append(JobPosting(
                company=j.get("company", "") or "Unknown",
                title=title,
                url=j.get("link", ""),
                location=loc,
                source="jooble",
                posted_at=parse_dt(j.get("updated")),
                description=snippet,
                remote=_is_remote(title, loc, snippet),
            ))
        log.info("jooble: %d results", len(out))
        return out


class JSearch(Source):
    """Google-for-Jobs aggregator (indexes LinkedIn/Indeed/Glassdoor/etc).
    Free quota is tiny (~200/month) so this is deep-tier: one query, run only
    in the slow crawl."""

    name = "jsearch"
    tier = "deep"

    @property
    def enabled(self) -> bool:
        return bool(env("JSEARCH_KEY"))

    def fetch(self, cfg):
        roles = cfg.get("roles", [])
        # Keep the query short; JSearch parses it as natural language.
        query = " OR ".join(roles[:3]) + " in USA"
        resp = http_get(
            "https://jsearch.p.rapidapi.com/search",
            params={"query": query, "page": "1", "num_pages": "1",
                    "date_posted": "today", "country": "us"},
            headers={
                "X-RapidAPI-Key": env("JSEARCH_KEY"),
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            },
        )
        if resp is None:
            log.warning("jsearch: request failed")
            return []
        try:
            data = resp.json().get("data", []) or []
        except ValueError:
            return []
        out = []
        for j in data:
            city = j.get("job_city") or ""
            state = j.get("job_state") or ""
            country = j.get("job_country") or ""
            loc = ", ".join(p for p in (city, state) if p) or country
            out.append(JobPosting(
                company=j.get("employer_name", "") or "Unknown",
                title=j.get("job_title", ""),
                url=j.get("job_apply_link") or j.get("job_google_link", ""),
                location=loc,
                source=f"jsearch/{j.get('job_publisher', '') or 'web'}",
                posted_at=parse_dt(j.get("job_posted_at_datetime_utc")),
                description=strip_html(j.get("job_description", "")),
                remote=bool(j.get("job_is_remote")) or None,
            ))
        log.info("jsearch: %d results", len(out))
        return out
