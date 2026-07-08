from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from langdetect import DetectorFactory

from worksearcher.core.filters import (
    extract_min_years_required,
    filter_jobs,
    has_minimum_salary,
    is_language_allowed,
    is_not_blacklisted,
    is_recent,
    is_relevant,
    meets_experience_requirement,
    title_implies_senior,
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


def _fake_lang(lang: str, prob: float) -> MagicMock:
    m = MagicMock()
    m.lang = lang
    m.prob = prob
    return m


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


# --- title_implies_senior ---


def test_title_senior_word_detected():
    assert title_implies_senior("Senior Backend Engineer") is True


def test_title_sr_abbreviation_detected():
    assert title_implies_senior("Sr. Software Engineer") is True


def test_title_staff_detected():
    assert title_implies_senior("Staff Engineer") is True


def test_title_principal_detected():
    assert title_implies_senior("Principal Security Engineer") is True


def test_title_lead_detected():
    assert title_implies_senior("Lead Developer") is True


def test_title_lider_spanish_detected():
    assert title_implies_senior("Líder Técnico") is True


def test_title_arquitecto_spanish_detected():
    assert title_implies_senior("Arquitecto de Software") is True


def test_title_mid_level_not_detected():
    assert title_implies_senior("Backend Developer") is False


def test_title_junior_not_detected():
    assert title_implies_senior("Junior Python Developer") is False


# --- meets_experience_requirement: senior title without explicit years ---


def test_senior_title_without_years_fails_low_cap():
    job = _job("Senior Backend Engineer", description="Join our growing team")
    assert meets_experience_requirement(job, max_years=3) is False


def test_senior_title_without_years_passes_high_cap():
    job = _job("Senior Backend Engineer", description="Join our growing team")
    assert meets_experience_requirement(job, max_years=5) is True


def test_senior_title_with_explicit_years_uses_explicit_value():
    job = _job("Senior Backend Engineer", description="2+ years of experience required")
    assert meets_experience_requirement(job, max_years=3) is True


def test_senior_title_with_explicit_entry_level_passes():
    job = _job("Senior Backend Engineer", description="Entry level, no experience required")
    assert meets_experience_requirement(job, max_years=3) is True


def test_non_senior_title_without_years_still_passes():
    job = _job("Backend Developer", description="Join our growing team")
    assert meets_experience_requirement(job, max_years=3) is True


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


def test_filter_jobs_excludes_senior_title_with_no_explicit_years():
    jobs = [
        _job("Python Dev", description="2 years experience"),
        _job("Senior Python Backend Engineer", description="Join our growing team"),
    ]
    result = filter_jobs(jobs, KEYWORDS, max_years_experience=3)
    titles = {j.title for j in result}
    assert "Python Dev" in titles
    assert "Senior Python Backend Engineer" not in titles


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


def test_fake_settings_has_filter_fields(fake_settings):
    assert hasattr(fake_settings, "MAX_JOB_AGE_DAYS")
    assert hasattr(fake_settings, "blacklist_list")
    assert hasattr(fake_settings, "filter_languages_list")
    assert hasattr(fake_settings, "MIN_SALARY_USD_MONTHLY")


def _job_with_date(days_ago: int) -> Job:
    posted = datetime.now(UTC) - timedelta(days=days_ago)
    return Job(
        title="Python Developer",
        company="Co",
        location="Remote",
        url=f"https://example.com/{days_ago}",
        source=JobSource.REMOTEOK,
        is_remote=True,
        posted_at=posted,
    )


def _job_with_salary(salary) -> Job:
    return Job(
        title="Python Developer",
        company="Co",
        location="Remote",
        url="https://example.com/salary",
        source=JobSource.REMOTEOK,
        is_remote=True,
        min_salary_usd_monthly=salary,
    )


# --- is_recent ---


def test_recent_job_passes():
    assert is_recent(_job_with_date(days_ago=5), max_days=30) is True


def test_old_job_fails():
    assert is_recent(_job_with_date(days_ago=31), max_days=30) is False


def test_job_within_limit_passes():
    assert is_recent(_job_with_date(days_ago=29), max_days=30) is True


def test_job_without_posted_at_passes():
    assert is_recent(_job("Python Developer"), max_days=30) is True


# --- is_not_blacklisted ---


def test_clean_job_passes_blacklist():
    assert is_not_blacklisted(_job("Python Developer"), ["security clearance"]) is True


def test_blacklisted_title_fails():
    assert is_not_blacklisted(_job("Security Clearance Required"), ["security clearance"]) is False


def test_blacklisted_description_fails():
    job = _job("Backend Engineer", description="Must have TS/SCI clearance")
    assert is_not_blacklisted(job, ["ts/sci"]) is False


def test_blacklist_is_case_insensitive():
    assert is_not_blacklisted(_job("TOP SECRET project"), ["top secret"]) is False


def test_empty_blacklist_always_passes():
    assert is_not_blacklisted(_job("Any Title"), []) is True


# --- is_language_allowed ---


def test_english_job_passes():
    with patch("worksearcher.core.filters.detect_langs", return_value=[_fake_lang("en", 0.99)]):
        assert is_language_allowed(_job("Python Developer"), ["en", "es"]) is True


def test_spanish_job_passes():
    with patch("worksearcher.core.filters.detect_langs", return_value=[_fake_lang("es", 0.95)]):
        assert is_language_allowed(_job("Desarrollador Python"), ["en", "es"]) is True


def test_french_job_fails():
    with patch("worksearcher.core.filters.detect_langs", return_value=[_fake_lang("fr", 0.92)]):
        assert is_language_allowed(_job("Développeur Python"), ["en", "es"]) is False


def test_low_confidence_passes_language_filter():
    # Confidence below 0.8 → pass through regardless of language
    with patch("worksearcher.core.filters.detect_langs", return_value=[_fake_lang("fr", 0.6)]):
        assert is_language_allowed(_job("ambiguous text"), ["en", "es"]) is True


def test_language_passes_on_detection_error():
    with patch("worksearcher.core.filters.detect_langs", side_effect=Exception("undetectable")):
        assert is_language_allowed(_job("???"), ["en", "es"]) is True


def test_empty_text_passes_language_filter():
    job = _job("", description="")
    assert is_language_allowed(job, ["en", "es"]) is True


# --- has_minimum_salary ---


def test_salary_above_minimum_passes():
    assert has_minimum_salary(_job_with_salary(1500.0), min_usd_monthly=1200.0) is True


def test_salary_below_minimum_fails():
    assert has_minimum_salary(_job_with_salary(1000.0), min_usd_monthly=1200.0) is False


def test_salary_exactly_at_minimum_passes():
    assert has_minimum_salary(_job_with_salary(1200.0), min_usd_monthly=1200.0) is True


def test_no_salary_passes():
    assert has_minimum_salary(_job_with_salary(None), min_usd_monthly=1200.0) is True


# --- filter_jobs with all new params ---


def test_filter_jobs_applies_date_filter():
    jobs = [
        _job_with_date(days_ago=5),
        _job_with_date(days_ago=40),
        _job("Python Dev"),
    ]
    result = filter_jobs(jobs, ["python"], max_job_age_days=30)
    assert len(result) == 2


def test_filter_jobs_applies_blacklist():
    jobs = [
        _job("Python Developer"),
        _job("Python Dev, US Citizens Only"),
    ]
    result = filter_jobs(jobs, ["python"], blacklist=["us citizens only"])
    assert len(result) == 1
    assert result[0].title == "Python Developer"


def test_filter_jobs_applies_language_filter():
    with patch(
        "worksearcher.core.filters.detect_langs",
        side_effect=[
            [_fake_lang("en", 0.99)],
            [_fake_lang("fr", 0.95)],
        ],
    ):
        jobs = [_job("Python Developer"), _job("Développeur Python")]
        result = filter_jobs(jobs, ["python"], allowed_languages=["en", "es"])
    assert len(result) == 1


def test_filter_jobs_applies_salary_filter():
    jobs = [
        _job_with_salary(1500.0),
        _job_with_salary(800.0),
        _job_with_salary(None),
    ]
    result = filter_jobs(jobs, ["python"], min_salary_usd_monthly=1200.0)
    assert len(result) == 2


def test_filter_jobs_none_params_skip_filters():
    jobs = [_job_with_date(days_ago=60), _job("Python Dev")]
    result = filter_jobs(
        jobs,
        ["python"],
        max_job_age_days=None,
        blacklist=None,
        allowed_languages=None,
        min_salary_usd_monthly=None,
    )
    assert len(result) == 2


# --- langdetect determinism ---


def test_langdetect_seed_is_set():
    # Fix b36fe38: seed must be 0 so language filtering produces identical results
    # across runs. Without the seed, langdetect is non-deterministic and jobs may
    # be accepted or rejected inconsistently.
    assert DetectorFactory.seed == 0
