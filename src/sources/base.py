"""Base class + shared HTTP helper for job sources."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Iterable

import requests

from ..models import JobPosting

USER_AGENT = "job-search-automation/1.0 (+https://github.com/)"
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


def http_get(url: str, *, params: dict | None = None, headers: dict | None = None,
             timeout: int = 20, retries: int = 2) -> requests.Response | None:
    """GET with light retry/backoff. Returns None on persistent failure or 404
    so a single bad source/slug never crashes the whole run."""
    for attempt in range(retries + 1):
        try:
            resp = _session.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:  # rate limited — back off and retry
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == retries:
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def http_post(url: str, *, json: dict | None = None, headers: dict | None = None,
              timeout: int = 20, retries: int = 2) -> requests.Response | None:
    """POST with the same forgiving retry behaviour as http_get."""
    for attempt in range(retries + 1):
        try:
            resp = _session.post(url, json=json, headers=headers, timeout=timeout)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == retries:
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


class Source(ABC):
    """A job source.

    `enabled` lets the orchestrator skip sources whose secrets/config are
    missing (so the system still runs with zero API keys, on ATS alone).
    `tier` controls cadence: "frequent" sources run every 30 min; "deep"
    sources (rate-limited ones like JSearch) only run in the slower crawl.
    """

    name: str = "base"
    tier: str = "frequent"

    @property
    def enabled(self) -> bool:
        return True

    @abstractmethod
    def fetch(self, cfg: dict) -> Iterable[JobPosting]:
        """Return raw postings. Central filtering/scoring happens later."""
        raise NotImplementedError
