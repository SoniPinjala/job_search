"""Config + secrets loading.

config.yaml holds non-secret settings (roles, description, companies...).
Secrets come from environment variables (GitHub Secrets in CI, a local .env
or your shell for local runs). Nothing secret is ever read from the repo.
"""
from __future__ import annotations

import os
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_config(path: str | os.PathLike | None = None) -> dict:
    path = pathlib.Path(path) if path else ROOT / "config.yaml"
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    cfg.setdefault("roles", [])
    cfg.setdefault("description", "")
    cfg.setdefault("location", {})
    cfg.setdefault("filters", {})
    cfg.setdefault("h1b", {})
    cfg.setdefault("companies", {})
    return cfg


def env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def get_profile() -> str:
    """Profile blurb for referral messages: env first (CI Secret), then a local
    git-ignored profile.md, then the committed template as a last resort."""
    blurb = env("PROFILE_BLURB")
    if blurb:
        return blurb
    for fname in ("profile.md", "profile.example.md"):
        p = ROOT / fname
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""
