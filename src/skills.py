"""Lightweight skills extraction + gap analysis (no API needed).

Pulls known skills out of a job description and out of your profile by matching
a curated vocabulary, then splits a job's skills into "you have" vs "to learn".
Keyword-based, so it's a quick guide — not a substitute for reading the JD.
"""
from __future__ import annotations

import re

# (display name, regex). Ordered roughly by signal so the most relevant skills
# survive truncation. Patterns are matched case-insensitively.
_SKILL_PATTERNS: list[tuple[str, str]] = [
    ("Python", r"\bpython\b"),
    ("SQL", r"\bsql\b"),
    ("R", r"\br\b(?=\s*[,/)]|\s+and\b)|\brstudio\b|\br/python\b|\bpython/r\b|\br shiny\b"),
    ("Java", r"\bjava\b"),
    ("JavaScript", r"\bjavascript\b"),
    ("TypeScript", r"\btypescript\b"),
    ("C++", r"c\+\+"),
    ("Go", r"\bgolang\b"),
    ("Scala", r"\bscala\b"),
    ("MATLAB", r"\bmatlab\b"),
    ("Machine Learning", r"\bmachine learning\b|\bml\b"),
    ("Deep Learning", r"\bdeep learning\b|\bneural network"),
    ("NLP", r"\bnlp\b|\bnatural language processing\b"),
    ("Computer Vision", r"\bcomputer vision\b|\bopencv\b"),
    ("LLMs", r"\bllms?\b|\blarge language models?\b"),
    ("RAG", r"\brag\b|\bretrieval[- ]augmented\b"),
    ("Transformers", r"\btransformers?\b|\bhugging ?face\b"),
    ("Generative AI", r"\bgenerative ai\b|\bgen ?ai\b"),
    ("PyTorch", r"\bpytorch\b"),
    ("TensorFlow", r"\btensorflow\b"),
    ("scikit-learn", r"\bscikit[- ]?learn\b|\bsklearn\b"),
    ("Keras", r"\bkeras\b"),
    ("pandas", r"\bpandas\b"),
    ("NumPy", r"\bnumpy\b"),
    ("LangChain", r"\blangchain\b"),
    ("Vector DBs", r"\bvector (db|database)\b|\bmilvus\b|\bpinecone\b|\bweaviate\b|\bfaiss\b|\bchroma\b"),
    ("MLOps", r"\bmlops\b"),
    ("Spark", r"\b(apache )?spark\b|\bpyspark\b"),
    ("Hadoop", r"\bhadoop\b"),
    ("Kafka", r"\bkafka\b"),
    ("Airflow", r"\bairflow\b"),
    ("dbt", r"\bdbt\b"),
    ("Snowflake", r"\bsnowflake\b"),
    ("Databricks", r"\bdatabricks\b"),
    ("BigQuery", r"\bbigquery\b"),
    ("Redshift", r"\bredshift\b"),
    ("ETL", r"\betl\b|\belt\b|\bdata pipelines?\b"),
    ("AWS", r"\baws\b|\bamazon web services\b"),
    ("Azure", r"\bazure\b"),
    ("GCP", r"\bgcp\b|\bgoogle cloud\b"),
    ("Docker", r"\bdocker\b"),
    ("Kubernetes", r"\bkubernetes\b|\bk8s\b"),
    ("Terraform", r"\bterraform\b"),
    ("CI/CD", r"\bci/?cd\b"),
    ("Git", r"\bgit\b|\bgithub\b|\bgitlab\b"),
    ("REST APIs", r"\brest\b|\brestful\b"),
    ("GraphQL", r"\bgraphql\b"),
    ("FastAPI", r"\bfastapi\b"),
    ("Flask", r"\bflask\b"),
    ("Streamlit", r"\bstreamlit\b"),
    ("Jenkins", r"\bjenkins\b"),
    ("Matplotlib", r"\bmatplotlib\b"),
    ("Django", r"\bdjango\b"),
    ("React", r"\breact\b"),
    ("Node.js", r"\bnode\.?js\b"),
    ("Microservices", r"\bmicroservices?\b"),
    ("Tableau", r"\btableau\b"),
    ("Power BI", r"\bpower ?bi\b"),
    ("Statistics", r"\bstatistics\b|\bstatistical\b"),
    ("A/B Testing", r"\ba/?b test|\bexperimentation\b"),
    ("Time Series", r"\btime series\b"),
    ("Recommender Systems", r"\brecommendation\b|\brecommender\b"),
]

_COMPILED = [(name, re.compile(pat, re.IGNORECASE)) for name, pat in _SKILL_PATTERNS]


def extract_skills(text: str) -> list[str]:
    """Skills found in text, in vocabulary (priority) order, de-duplicated."""
    if not text:
        return []
    return [name for name, rx in _COMPILED if rx.search(text)]


def skill_gap(jd_text: str, profile_skills: set[str]) -> tuple[list[str], list[str]]:
    """Return (skills_you_have, skills_to_learn) for a job description."""
    jd = extract_skills(jd_text)
    have = [s for s in jd if s in profile_skills]
    gap = [s for s in jd if s not in profile_skills]
    return have, gap
