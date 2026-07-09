import sqlite3

import pytest

from worksearcher.core.models import Company, Job, JobSource
from worksearcher.storage.database import (
    get_seen_company_fingerprints,
    get_seen_fingerprints,
    get_unnotified_companies,
    get_unnotified_jobs,
    init_db,
    mark_companies_notified,
    mark_jobs_notified,
    save_companies,
    save_jobs,
)


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
    seen = get_seen_fingerprints([job.fingerprint], conn)
    assert job.fingerprint in seen


def test_get_seen_fingerprints_empty_candidates(conn):
    assert get_seen_fingerprints([], conn) == set()


def test_get_seen_fingerprints_unknown_fingerprint(conn):
    assert get_seen_fingerprints(["nonexistent"], conn) == set()


def test_get_seen_fingerprints_only_returns_matches(conn):
    job1 = _job("https://example.com/1")
    job2 = _job("https://example.com/2")
    save_jobs([job1], conn)
    seen = get_seen_fingerprints([job1.fingerprint, job2.fingerprint], conn)
    assert job1.fingerprint in seen
    assert job2.fingerprint not in seen


def test_save_empty_list_returns_zero(conn):
    assert save_jobs([], conn) == 0


def test_get_unnotified_jobs_returns_unsent(conn):
    job = _job("https://example.com/1")
    save_jobs([job], conn)
    unnotified = get_unnotified_jobs(conn)
    assert len(unnotified) == 1
    assert unnotified[0].url == job.url


def test_mark_jobs_notified_clears_pending(conn):
    job = _job("https://example.com/1")
    save_jobs([job], conn)
    mark_jobs_notified([job.fingerprint], conn)
    assert get_unnotified_jobs(conn) == []


def test_get_unnotified_jobs_empty_when_all_notified(conn):
    job = _job("https://example.com/1")
    save_jobs([job], conn)
    mark_jobs_notified([job.fingerprint], conn)
    assert get_unnotified_jobs(conn) == []


def test_special_characters_stored_correctly(conn):
    job = _job("https://example.com/1", title="Desarrollador de Software — México")
    inserted = save_jobs([job], conn)
    assert inserted == 1
    seen = get_seen_fingerprints([job.fingerprint], conn)
    assert job.fingerprint in seen


def _company(website: str, email: str | None = "rh@acme.mx", status: str = "pending") -> Company:
    return Company(
        name="Acme Corp",
        website=website,
        latitude=20.1,
        longitude=-100.8,
        email=email,
        status=status,
    )


def test_save_companies_returns_inserted_count(conn):
    companies = [_company("https://acme.mx"), _company("https://acme2.mx")]
    assert save_companies(companies, conn) == 2


def test_duplicate_company_not_reinserted(conn):
    company = _company("https://acme.mx")
    save_companies([company], conn)
    assert save_companies([company], conn) == 0


def test_save_empty_companies_returns_zero(conn):
    assert save_companies([], conn) == 0


def test_get_seen_company_fingerprints_returns_saved(conn):
    company = _company("https://acme.mx")
    save_companies([company], conn)
    seen = get_seen_company_fingerprints([company.fingerprint], conn)
    assert company.fingerprint in seen


def test_get_seen_company_fingerprints_empty_candidates(conn):
    assert get_seen_company_fingerprints([], conn) == set()


def test_get_unnotified_companies_excludes_no_email_found(conn):
    with_email = _company("https://acme.mx", email="rh@acme.mx", status="pending")
    without_email = Company(
        name="Beta", website="https://beta.mx", latitude=1.0, longitude=1.0, status="no_email_found"
    )
    save_companies([with_email, without_email], conn)
    unnotified = get_unnotified_companies(conn)
    assert [c.website for c in unnotified] == ["https://acme.mx"]


def test_mark_companies_notified_clears_pending(conn):
    company = _company("https://acme.mx")
    save_companies([company], conn)
    mark_companies_notified([company.fingerprint], conn)
    assert get_unnotified_companies(conn) == []
