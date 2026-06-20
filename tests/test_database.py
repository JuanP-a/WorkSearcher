import sqlite3
import pytest
from worksearcher.core.models import Job, JobSource
from worksearcher.storage.database import init_db, save_jobs, get_seen_fingerprints


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    init_db(c)
    yield c
    c.close()


def _job(url: str, title: str = "Dev") -> Job:
    return Job(
        title=title,
        company="Co",
        location="Remote",
        url=url,
        source=JobSource.REMOTEOK,
        is_remote=True,
    )


def test_save_jobs_returns_inserted_count(conn):
    jobs = [_job("https://example.com/1"), _job("https://example.com/2")]
    assert save_jobs(jobs, conn) == 2


def test_duplicate_job_not_reinserted(conn):
    job = _job("https://example.com/1")
    save_jobs([job], conn)
    assert save_jobs([job], conn) == 0


def test_get_seen_fingerprints_returns_saved(conn):
    job = _job("https://example.com/1")
    save_jobs([job], conn)
    seen = get_seen_fingerprints(conn)
    assert job.fingerprint in seen


def test_get_seen_fingerprints_empty_db(conn):
    assert get_seen_fingerprints(conn) == set()


def test_save_empty_list_returns_zero(conn):
    assert save_jobs([], conn) == 0


def test_special_characters_stored_correctly(conn):
    job = _job("https://example.com/1", title="Desarrollador de Software — México")
    inserted = save_jobs([job], conn)
    assert inserted == 1
    seen = get_seen_fingerprints(conn)
    assert job.fingerprint in seen
