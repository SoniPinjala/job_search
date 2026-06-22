#!/usr/bin/env python3
"""Check which company slugs in config.yaml actually resolve on their ATS.

    python scripts/verify_companies.py

Reports a job count per slug, or FAIL if the board/slug doesn't exist. Use it
when curating the `companies:` list so you don't silently miss a company.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.config import load_config  # noqa: E402
from src.sources.base import http_get, http_post  # noqa: E402


def greenhouse(slug):
    r = http_get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    return None if r is None else len(r.json().get("jobs", []))


def lever(slug):
    r = http_get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    return None if r is None else len(r.json())


def ashby(slug):
    r = http_get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    return None if r is None else len(r.json().get("jobs", []))


CHECKERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}


def main() -> None:
    companies = load_config().get("companies", {})
    bad = 0
    for platform, slugs in companies.items():
        checker = CHECKERS.get(platform)
        if not checker:
            print(f"⚠️  unknown platform '{platform}' — skipping")
            continue
        for slug in slugs or []:
            try:
                count = checker(slug)
            except Exception as exc:
                count, exc_msg = None, str(exc)
            else:
                exc_msg = ""
            if count is None:
                bad += 1
                print(f"❌ {platform:11} {slug:20} FAILED {exc_msg}")
            else:
                print(f"✅ {platform:11} {slug:20} {count} jobs")
    print(f"\n{bad} slug(s) failed." if bad else "\nAll slugs resolved. 🎉")


if __name__ == "__main__":
    main()
