#!/usr/bin/env python3
"""Orchestrator: fetch -> filter/score -> dedupe -> H1B -> referral -> Sheet.

  python main.py --mode frequent     # the 30-min run (Adzuna, Jooble, ATS)
  python main.py --mode deep         # the slow run (+ JSearch)
  python main.py --dry-run           # print results, write nothing (no Sheet needed)
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone

from src import h1b
from src.config import env, get_profile, load_config
from src.matching import filter_and_score
from src.referral import generate_referral
from src.skills import extract_skills, skill_gap
from src.sources.aggregators import Adzuna, JSearch, Jooble
from src.sources.ats import Ashby, Greenhouse, Lever

log = logging.getLogger("job-search")

ALL_SOURCES = [Greenhouse(), Lever(), Ashby(), Adzuna(), Jooble(), JSearch()]


def select_sources(mode: str):
    selected = []
    for s in ALL_SOURCES:
        if not s.enabled:
            log.info("skip %s (missing config/secrets)", s.name)
            continue
        if mode == "frequent" and s.tier != "frequent":
            continue
        selected.append(s)
    return selected


def dedupe_keep_best(postings):
    best = {}
    for p in postings:
        cur = best.get(p.key)
        if cur is None or p.match_score > cur.match_score:
            best[p.key] = p
    return list(best.values())


def sort_postings(postings, cfg):
    prioritize = cfg.get("h1b", {}).get("prioritize", True)
    floor = datetime.min.replace(tzinfo=timezone.utc)

    def sort_key(p):
        sponsor = 1 if (prioritize and p.h1b_count > 0) else 0
        return (sponsor, p.match_score, p.posted_at or floor)

    return sorted(postings, key=sort_key, reverse=True)


def _preflight() -> None:
    """Fail fast with a clear list of every missing required secret (not one at
    a time). Also report which optional sources are configured."""
    missing = []
    if not env("GOOGLE_SHEET_ID"):
        missing.append("GOOGLE_SHEET_ID")
    have_creds = env("GOOGLE_SERVICE_ACCOUNT_JSON") or os.path.exists(
        env("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json"))
    if not have_creds:
        missing.append("GOOGLE_SERVICE_ACCOUNT_JSON")
    if missing:
        log.error("Missing required secret(s): %s", ", ".join(missing))
        log.error("Add them in repo Settings > Secrets and variables > Actions "
                  "(Repository secrets, exact names above).")
        raise SystemExit(1)

    configured = [name for name, present in {
        "Adzuna": env("ADZUNA_APP_ID") and env("ADZUNA_APP_KEY"),
        "Jooble": env("JOOBLE_KEY"),
        "JSearch": env("JSEARCH_KEY"),
        "Gemini referral messages": env("GEMINI_API_KEY"),
        "Profile (PROFILE_BLURB)": env("PROFILE_BLURB"),
    }.items() if present]
    log.info("optional configured: %s", ", ".join(configured) or "none (ATS boards only)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["frequent", "deep"], default="frequent")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print results instead of writing to the Sheet.")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = load_config()
    profile = get_profile()
    h1b_cfg = cfg.get("h1b", {})

    # 1. Fetch.
    raw = []
    for src in select_sources(args.mode):
        try:
            raw.extend(list(src.fetch(cfg)))
        except Exception:
            log.exception("source %s failed", src.name)
    log.info("fetched %d raw postings", len(raw))

    # 2. Filter + score, then collapse duplicates across sources.
    matched = dedupe_keep_best(filter_and_score(raw, cfg))
    log.info("%d postings after match + cross-source dedupe", len(matched))

    # 3. Annotate H1B (optionally hard-filter).
    for p in matched:
        p.h1b_label, p.h1b_count = h1b.lookup(p.company)
    if h1b_cfg.get("require", False):
        floor = int(h1b_cfg.get("min_recent_filings", 1))
        matched = [p for p in matched if p.h1b_count >= floor]
        log.info("%d postings after H1B hard filter", len(matched))

    matched = sort_postings(matched, cfg)
    cap = int(cfg.get("filters", {}).get("max_new_per_run", 60))

    # 4. Output.
    if args.dry_run:
        for p in matched[:cap]:
            print(f"- [{p.h1b_label}] {p.company} — {p.title} "
                  f"({p.location or 'n/a'}) [{p.match_score:.0%}] {p.url}")
        log.info("dry-run: %d postings shown, nothing written", min(len(matched), cap))
        return

    _preflight()
    from src.sheets import JobSheet  # lazy: dry-run needs no Google creds
    sheet = JobSheet()
    existing = sheet.existing_keys()
    fresh = [p for p in matched if p.key not in existing][:cap]
    log.info("%d new postings after Sheet dedupe (cap %d)", len(fresh), cap)

    profile_skills = set(extract_skills(profile))
    for p in fresh:
        have, gap = skill_gap(f"{p.title} {p.description}", profile_skills)
        p.skills_have = ", ".join(have[:10])
        p.skills_gap = ", ".join(gap[:10])
        p.referral_message = generate_referral(p, profile)
    wrote = sheet.append(fresh)
    log.info("done — wrote %d new jobs to the Sheet", wrote)


if __name__ == "__main__":
    main()
