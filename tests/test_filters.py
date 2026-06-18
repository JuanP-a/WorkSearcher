from worksearcher.core.models import Job, JobSource
from worksearcher.core.filters import is_relevant, filter_jobs

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
