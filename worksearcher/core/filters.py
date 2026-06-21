import re

from worksearcher.core.models import Job

# Matches "3-5 years", "3–5 years" — capture both bounds to take the minimum
_RANGE_PATTERN = re.compile(r'(\d+)\s*[-–]\s*(\d+)\s*(?:years?|yrs?|años?)', re.IGNORECASE)

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
    if not job.is_remote:
        return False
    searchable = f"{job.title} {job.description}".lower()
    return any(kw.lower() in searchable for kw in keywords)


def filter_jobs(jobs: list[Job], keywords: list[str], max_years_experience: int | None = None) -> list[Job]:
    filtered = [j for j in jobs if is_relevant(j, keywords)]
    if max_years_experience is not None:
        filtered = [j for j in filtered if meets_experience_requirement(j, max_years_experience)]
    return filtered
