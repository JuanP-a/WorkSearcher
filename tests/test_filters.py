from worksearcher.core.filters import (
    extract_min_years_required,
    filter_jobs,
    is_relevant,
    meets_experience_requirement,
)
from worksearcher.core.models import Job, JobSource

KEYWORDS = ["python", "backend", "cybersecurity", "security engineer", "soc", "pentester"]


def _job(title: str, description: str = "", is_remote: bool = True) -> Job:
    return Job(
        title=title,
        company="Test Co",
        location="Remote" if is_remote else "Mexico City",
        url=f"https://example.com/{title.replace(' ', '-')}",
        source=JobSource.REMOTEOK,
        is_remote=is_remote,
        description=description,
    )


# --- is_relevant ---

def test_relevant_by_title_keyword():
    assert is_relevant(_job("Python Developer"), KEYWORDS) is True


def test_relevant_by_description_keyword():
    job = _job("Software Engineer", description="We need cybersecurity experience")
    assert is_relevant(job, KEYWORDS) is True


def test_irrelevant_job_no_keyword_match():
    assert is_relevant(_job("Marketing Manager"), KEYWORDS) is False


def test_non_remote_job_is_irrelevant():
    assert is_relevant(_job("Python Developer", is_remote=False), KEYWORDS) is False


def test_case_insensitive_match():
    assert is_relevant(_job("BACKEND ENGINEER"), KEYWORDS) is True


def test_filter_jobs_returns_only_relevant():
    jobs = [
        _job("Python Developer"),
        _job("Marketing Manager"),
        _job("SOC Analyst"),
        _job("HR Specialist", is_remote=False),
    ]
    result = filter_jobs(jobs, KEYWORDS)
    assert len(result) == 2
    titles = {j.title for j in result}
    assert "Python Developer" in titles
    assert "SOC Analyst" in titles


def test_filter_jobs_empty_list():
    assert filter_jobs([], KEYWORDS) == []


# --- extract_min_years_required ---

def test_no_experience_mention_returns_none():
    assert extract_min_years_required("Great company, exciting role") is None


def test_empty_text_returns_none():
    assert extract_min_years_required("") is None


def test_exact_years_english():
    assert extract_min_years_required("Requires 5 years of experience") == 5


def test_plus_years():
    assert extract_min_years_required("5+ years required") == 5


def test_range_returns_minimum():
    assert extract_min_years_required("3-5 years of experience") == 3


def test_range_with_dash_em():
    assert extract_min_years_required("2–4 years experience") == 2


def test_entry_level_returns_zero():
    assert extract_min_years_required("Entry level position, no experience required") == 0


def test_junior_returns_zero():
    assert extract_min_years_required("Junior backend developer") == 0


def test_spanish_years():
    assert extract_min_years_required("5 años de experiencia requerida") == 5


def test_spanish_entry_level():
    assert extract_min_years_required("Recién egresado, sin experiencia") == 0


def test_one_year():
    assert extract_min_years_required("1 year of experience preferred") == 1


# --- meets_experience_requirement ---

def test_no_mention_passes():
    job = _job("Backend Dev", description="Exciting startup")
    assert meets_experience_requirement(job, max_years=3) is True


def test_within_limit_passes():
    job = _job("Backend Dev", description="2 years of experience required")
    assert meets_experience_requirement(job, max_years=3) is True


def test_at_limit_passes():
    job = _job("Backend Dev", description="3 years of experience required")
    assert meets_experience_requirement(job, max_years=3) is True


def test_over_limit_fails():
    job = _job("Senior Dev", description="5+ years of experience")
    assert meets_experience_requirement(job, max_years=3) is False


def test_entry_level_passes():
    job = _job("Junior Python Dev", description="Entry level, no experience required")
    assert meets_experience_requirement(job, max_years=3) is True


def test_range_min_within_limit_passes():
    job = _job("Dev", description="2-5 years of experience")
    assert meets_experience_requirement(job, max_years=3) is True


def test_experience_in_title_detected():
    job = _job("Senior Dev 7 years exp", description="")
    assert meets_experience_requirement(job, max_years=3) is False


# --- filter_jobs with experience cap ---

def test_filter_jobs_applies_experience_cap():
    jobs = [
        _job("Python Dev", description="2 years experience"),
        _job("Python Dev Senior", description="7+ years experience"),
        _job("Backend Dev", description="No experience mentioned"),
    ]
    result = filter_jobs(jobs, KEYWORDS, max_years_experience=3)
    titles = {j.title for j in result}
    assert "Python Dev" in titles
    assert "Backend Dev" in titles
    assert "Python Dev Senior" not in titles


def test_filter_jobs_no_experience_cap_keeps_all_relevant():
    jobs = [
        _job("Python Dev", description="10 years experience"),
        _job("Backend Dev", description="junior"),
    ]
    result = filter_jobs(jobs, KEYWORDS, max_years_experience=None)
    assert len(result) == 2


# --- Unicode dash variants in range pattern (BACK-3) ---

def test_range_figure_dash():
    # U+2012 figure dash — common in copy-pasted PDF text
    assert extract_min_years_required("3‒5 years of experience") == 3


def test_range_em_dash():
    # U+2014 em dash
    assert extract_min_years_required("2—4 years experience") == 2


def test_range_minus_sign():
    # U+2212 minus sign — different from ASCII hyphen
    assert extract_min_years_required("4−6 years experience") == 4


def test_range_unicode_takes_lower_bound():
    # Ensures we don't accidentally pick the upper bound (e.g. 8) and reject valid job
    assert extract_min_years_required("1−8 years experience") == 1
