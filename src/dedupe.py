"""Stable dedupe key so the same job is never written twice across runs/sources."""
from __future__ import annotations

import hashlib
import re


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_url(url: str) -> str:
    # Drop query string / fragment + trailing slash so tracking params don't
    # create phantom duplicates.
    url = (url or "").split("?")[0].split("#")[0].strip().lower()
    return url.rstrip("/")


def dedupe_key(company: str, title: str, url: str) -> str:
    base = f"{normalize(company)}|{normalize(title)}|{strip_url(url)}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
