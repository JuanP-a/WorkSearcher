import re
from datetime import UTC, datetime

from langdetect import DetectorFactory, detect_langs

DetectorFactory.seed = 0  # make language detection deterministic across runs

from worksearcher.core.models import Job

# Matches "3-5 years", "3–5 years", "3‒5 years", "3—5 years", "3−5 years"
# Covers: hyphen-minus, figure dash, en dash, em dash, minus sign (U+2212)
_RANGE_PATTERN = re.compile(r'(\d+)\s*[-‒–—−]\s*(\d+)\s*(?:years?|yrs?|años?)', re.IGNORECASE)

# Matches "5 years", "5+ years", "5 años de experiencia"
_YEARS_PATTERN = re.compile(r'(\d+)\+?\s*(?:years?|yrs?|años?)', re.IGNORECASE)

# Entry-level signals → treat as 0 years required
_ENTRY_LEVEL_PATTERN = re.compile(
    r'\b(?:entry[\s-]?level|junior|no experience required|recent graduate'
    r'|recién egresado|sin experiencia)\b',
    re.IGNORECASE,
)


def extract_min_years_required(text: str) -> int | None:
    """Return the minimum years of experience a job requires, or None if not mentioned."""
    if not text:
        return None
    if _ENTRY_LEVEL_PATTERN.search(text):
        return 0
    range_match = _RANGE_PATTERN.search(text)
    if range_match:
        return int(range_match.group(1))  # lower bound of range
    year_match = _YEARS_PATTERN.search(text)
    if year_match:
        return int(year_match.group(1))
    return None


def meets_experience_requirement(job: Job, max_years: int) -> bool:
    """Return True if job does not require more than max_years of experience.

    Jobs with no experience requirement mentioned are assumed accessible.
    """
    searchable = f"{job.title} {job.description or ''}"
    min_years = extract_min_years_required(searchable)
    if min_years is None:
        return True
    return min_years <= max_years


def is_relevant(job: Job, keywords: list[str]) -> bool:
    """Return True if job is remote and title or description contains a keyword."""
    if not job.is_remote:
        return False
    searchable = f"{job.title} {job.description}".lower()
    return any(kw.lower() in searchable for kw in keywords)


def is_recent(job: Job, max_days: int) -> bool:
    """Return True if job was posted within max_days. Jobs without posted_at always pass."""
    if job.posted_at is None:
        return True
    delta = datetime.now(UTC) - job.posted_at.astimezone(UTC)
    return delta.total_seconds() <= max_days * 86400


def is_not_blacklisted(job: Job, blacklist: list[str]) -> bool:
    """Return True if no blacklist keyword appears in title or description."""
    if not blacklist:
        return True
    searchable = f"{job.title} {job.description}".lower()
    return not any(kw in searchable for kw in blacklist)


def is_language_allowed(job: Job, allowed_langs: list[str]) -> bool:
    """Return True if job language is in allowed_langs.

    Uses langdetect on first 500 chars of title+description.
    Passes through if text is empty, detection fails, or top confidence < 0.8.
    """
    text = f"{job.title} {job.description}".strip()[:500]
    if not text:
        return True
    try:
        langs = detect_langs(text)
        top = langs[0]
        if top.prob < 0.8:
            return True  # not confident enough — let it through
        return top.lang in allowed_langs
    except Exception:
        return True


def has_minimum_salary(job: Job, min_usd_monthly: float) -> bool:
    """Return True if job meets minimum salary. Jobs without salary always pass."""
    if job.min_salary_usd_monthly is None:
        return True
    return job.min_salary_usd_monthly >= min_usd_monthly


def filter_jobs(
    jobs: list[Job],
    keywords: list[str],
    max_years_experience: int | None = None,
    max_job_age_days: int | None = None,
    blacklist: list[str] | None = None,
    allowed_languages: list[str] | None = None,
    min_salary_usd_monthly: float | None = None,
) -> list[Job]:
    filtered = [j for j in jobs if is_relevant(j, keywords)]
    if max_years_experience is not None:
        filtered = [j for j in filtered if meets_experience_requirement(j, max_years_experience)]
    if max_job_age_days is not None:
        filtered = [j for j in filtered if is_recent(j, max_job_age_days)]
    if blacklist is not None:
        filtered = [j for j in filtered if is_not_blacklisted(j, blacklist)]
    if allowed_languages is not None:
        filtered = [j for j in filtered if is_language_allowed(j, allowed_languages)]
    if min_salary_usd_monthly is not None:
        filtered = [j for j in filtered if has_minimum_salary(j, min_salary_usd_monthly)]
    return filtered
