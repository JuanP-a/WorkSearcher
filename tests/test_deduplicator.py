from worksearcher.core.models import Job, JobSource
from worksearcher.core.deduplicator import deduplicate


def _job(url: str) -> Job:
    return Job(
        title="Dev",
        company="Co",
        location="Remote",
        url=url,
        source=JobSource.REMOTEOK,
        is_remote=True,
    )


def test_seen_jobs_are_removed():
    job1 = _job("https://example.com/1")
    job2 = _job("https://example.com/2")
    result = deduplicate([job1, job2], seen={job1.fingerprint})
    assert len(result) == 1
    assert result[0].url == "https://example.com/2"


def test_empty_seen_returns_all():
    jobs = [_job("https://example.com/1"), _job("https://example.com/2")]
    assert deduplicate(jobs, seen=set()) == jobs


def test_all_seen_returns_empty():
    job = _job("https://example.com/1")
    assert deduplicate([job], seen={job.fingerprint}) == []


def test_empty_jobs_returns_empty():
    assert deduplicate([], seen={"abc"}) == []
