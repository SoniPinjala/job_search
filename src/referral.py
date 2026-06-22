"""Personalized referral-message generator.

Uses Google Gemini (free tier) when GEMINI_API_KEY is set, otherwise falls back
to a smart template. If the LLM errors or hits its quota mid-run, the rest of the
run automatically uses templates so a job never goes without a message.
"""
from __future__ import annotations

import logging
import re

from .config import env
from .models import JobPosting

log = logging.getLogger(__name__)

_PROMPT = """Write a SHORT referral-request message (60-90 words) that a job seeker
would send to a current employee at {company} on LinkedIn or email, asking for a
referral to this specific role.

Role: {title} at {company}
Location: {location}

The job seeker's profile:
{profile}

Rules:
- 2 to 4 sentences, first person, warm and specific.
- Mention 1 or 2 concrete skills or achievements from the profile that fit the role.
- End with a clear, low-pressure ask for a referral or an intro to the hiring team.
- Do NOT invent facts not in the profile. Do not add a subject line. Plain text only.
"""

_llm_disabled = False  # flips to True for the rest of the run if the LLM fails


def _clean_profile(profile: str) -> str:
    """Drop markdown headers / divider lines so the blurb reads as plain prose."""
    kept = []
    for line in (profile or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("---"):
            continue
        kept.append(line)
    return re.sub(r"\s+", " ", " ".join(kept)).strip()


def _first_sentence(profile: str) -> str:
    text = re.sub(r"\s+", " ", (profile or "").strip())
    if not text:
        return "My background lines up closely with what this role needs."
    sentence = re.split(r"(?<=[.!?])\s", text)[0]
    return sentence[:240]


def _template(posting: JobPosting, profile: str) -> str:
    pitch = _first_sentence(profile)
    return (
        f"Hi! I came across the {posting.title} role at {posting.company} and it "
        f"strongly matches my background. {pitch} Would you be open to referring me "
        f"or connecting me with the hiring team? Happy to share my resume and more "
        f"details — thank you so much!"
    )


def _gemini(posting: JobPosting, profile: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=env("GEMINI_API_KEY"))
    model = genai.GenerativeModel(env("GEMINI_MODEL", "gemini-1.5-flash"))
    prompt = _PROMPT.format(
        company=posting.company,
        title=posting.title,
        location=posting.location or "the US",
        profile=profile.strip()[:1500],
    )
    resp = model.generate_content(prompt)
    return (getattr(resp, "text", "") or "").strip()


def generate_referral(posting: JobPosting, profile: str) -> str:
    global _llm_disabled
    profile = _clean_profile(profile)
    if profile and env("GEMINI_API_KEY") and not _llm_disabled:
        try:
            msg = _gemini(posting, profile)
            if msg:
                return msg
        except Exception as exc:  # quota, network, import, model 404...
            log.warning("gemini unavailable (%s) — using templates for the rest of this run", exc)
            _llm_disabled = True
    return _template(posting, profile)
