"""Public ATS job-board adapters: Greenhouse, Lever, Ashby.

These are the legitimate, free, no-key way to read jobs straight off company
career pages (most modern companies host their board on one of these). A bad or
unknown slug just returns nothing and logs a warning — it never crashes the run.
"""
from __future__ import annotations

import logging

from ..models import JobPosting
from ..util import parse_dt, pretty_slug, strip_html
from .base import Source, http_get

log = logging.getLogger(__name__)


def _slugs(cfg: dict, platform: str) -> list[str]:
    return cfg.get("companies", {}).get(platform, []) or []


class Greenhouse(Source):
    name = "greenhouse"

    def fetch(self, cfg):
        out: list[JobPosting] = []
        for slug in _slugs(cfg, "greenhouse"):
            resp = http_get(
                f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                params={"content": "true"},
            )
            if resp is None:
                log.warning("greenhouse: skipping unresolved slug '%s'", slug)
                continue
            try:
                jobs = resp.json().get("jobs", [])
            except ValueError:
                continue
            for j in jobs:
                out.append(JobPosting(
                    company=j.get("company_name") or pretty_slug(slug),
                    title=j.get("title", ""),
                    url=j.get("absolute_url", ""),
                    location=(j.get("location") or {}).get("name", ""),
                    source="greenhouse",
                    posted_at=parse_dt(j.get("first_published") or j.get("updated_at")),
                    description=strip_html(j.get("content", "")),
                ))
            log.info("greenhouse/%s: %d jobs", slug, len(jobs))
        return out


class Lever(Source):
    name = "lever"

    def fetch(self, cfg):
        out: list[JobPosting] = []
        for slug in _slugs(cfg, "lever"):
            resp = http_get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
            if resp is None:
                log.warning("lever: skipping unresolved slug '%s'", slug)
                continue
            try:
                postings = resp.json()
            except ValueError:
                continue
            company = pretty_slug(slug)
            for j in postings:
                cats = j.get("categories") or {}
                loc = cats.get("location", "") or ""
                workplace = (cats.get("workplaceType") or "").lower()
                out.append(JobPosting(
                    company=company,
                    title=j.get("text", ""),
                    url=j.get("hostedUrl", ""),
                    location=loc,
                    source="lever",
                    posted_at=parse_dt(j.get("createdAt")),
                    description=strip_html(j.get("descriptionPlain") or j.get("description", "")),
                    remote=("remote" in workplace) or ("remote" in loc.lower()) or None,
                ))
            log.info("lever/%s: %d jobs", slug, len(postings))
        return out


class Ashby(Source):
    name = "ashby"

    def fetch(self, cfg):
        out: list[JobPosting] = []
        for slug in _slugs(cfg, "ashby"):
            resp = http_get(
                f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                params={"includeCompensation": "true"},
            )
            if resp is None:
                log.warning("ashby: skipping unresolved slug '%s'", slug)
                continue
            try:
                jobs = resp.json().get("jobs", [])
            except ValueError:
                continue
            company = pretty_slug(slug)
            for j in jobs:
                out.append(JobPosting(
                    company=company,
                    title=j.get("title", ""),
                    url=j.get("jobUrl") or j.get("applyUrl", ""),
                    location=j.get("location", "") or "",
                    source="ashby",
                    posted_at=parse_dt(j.get("publishedAt") or j.get("publishedDate")
                                       or j.get("updatedAt")),
                    description=strip_html(j.get("descriptionPlain") or j.get("descriptionHtml", "")),
                    remote=j.get("isRemote"),
                ))
            log.info("ashby/%s: %d jobs", slug, len(jobs))
        return out
