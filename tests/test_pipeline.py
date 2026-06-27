"""
Pipeline orchestration tests — verify _run_pipeline wiring.
Uses in-memory SQLite and fake scrapers/notifier; no real HTTP calls.
"""

import logging
import sqlite3

import pytest

from worksearcher.core.models import Job, JobSource
from worksearcher.main import _run_pipeline
from worksearcher.storage.database import (
    init_db,
    mark_jobs_notified,
    save_jobs,
)


def _job(n: int, title: str = "", source: JobSource = JobSource.REMOTEOK) -> Job:
    return Job(
        title=title or f"Python Developer {n}",
        company=f"Company {n}",
        location="Remote",
        url=f"https://example.com/job/{n}",
        source=source,
        is_remote=True,
        description="python backend remote",
    )


def _make_fake_scraper(jobs: list[Job]):
    async def scrape(config) -> list[Job]:
        return jobs

    return scrape


def _make_failing_scraper():
    async def scrape(config) -> list[Job]:
        raise RuntimeError("scraper exploded")

    return scrape


@pytest.mark.asyncio
async def test_pipeline_saves_new_jobs(tmp_path, monkeypatch, fake_settings):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    jobs = [_job(1), _job(2)]
    monkeypatch.setattr("worksearcher.main._ALL_SCRAPERS", {"fake": _make_fake_scraper(jobs)})
    fake_settings.enabled_scrapers_list = ["fake"]
    monkeypatch.setattr("worksearcher.main.get_connection", lambda path: sqlite3.connect(db_path))

    notified = []

    async def fake_send_digest(j, config):
        notified.extend(j)
        return True

    monkeypatch.setattr("worksearcher.main.send_digest", fake_send_digest)

    await _run_pipeline(fake_settings)

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()

    assert count == 2
    assert len(notified) == 2


@pytest.mark.asyncio
async def test_pipeline_skips_notification_when_no_new_jobs(tmp_path, monkeypatch, fake_settings):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)

    existing = [_job(1), _job(2)]
    save_jobs(existing, conn)
    mark_jobs_notified([j.fingerprint for j in existing], conn)
    conn.close()

    monkeypatch.setattr("worksearcher.main._ALL_SCRAPERS", {"fake": _make_fake_scraper(existing)})
    fake_settings.enabled_scrapers_list = ["fake"]
    monkeypatch.setattr("worksearcher.main.get_connection", lambda path: sqlite3.connect(db_path))

    notified = []

    async def fake_send_digest(j, config):
        notified.extend(j)
        return True

    monkeypatch.setattr("worksearcher.main.send_digest", fake_send_digest)

    await _run_pipeline(fake_settings)

    assert notified == []


@pytest.mark.asyncio
async def test_pipeline_tolerates_scraper_failure(tmp_path, monkeypatch, fake_settings):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    good_jobs = [_job(1)]
    monkeypatch.setattr(
        "worksearcher.main._ALL_SCRAPERS",
        {
            "fail": _make_failing_scraper(),
            "good": _make_fake_scraper(good_jobs),
        },
    )
    fake_settings.enabled_scrapers_list = ["fail", "good"]
    monkeypatch.setattr("worksearcher.main.get_connection", lambda path: sqlite3.connect(db_path))

    async def fake_send_digest(j, config):
        return True

    monkeypatch.setattr("worksearcher.main.send_digest", fake_send_digest)

    await _run_pipeline(fake_settings)

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()

    assert count == 1


@pytest.mark.asyncio
async def test_pipeline_filters_irrelevant_jobs(tmp_path, monkeypatch, fake_settings):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    jobs = [
        _job(1, title="Python Developer"),
        Job(
            title="Marketing Manager",
            company="Ads Co",
            location="Remote",
            url="https://example.com/job/99",
            source=JobSource.REMOTEOK,
            is_remote=True,
            description="brand strategy and campaigns",
        ),
        _job(3, title="Backend Engineer"),
    ]
    monkeypatch.setattr("worksearcher.main._ALL_SCRAPERS", {"fake": _make_fake_scraper(jobs)})
    fake_settings.enabled_scrapers_list = ["fake"]
    monkeypatch.setattr("worksearcher.main.get_connection", lambda path: sqlite3.connect(db_path))

    notified = []

    async def fake_send_digest(j, config):
        notified.extend(j)
        return True

    monkeypatch.setattr("worksearcher.main.send_digest", fake_send_digest)

    await _run_pipeline(fake_settings)

    notified_titles = {j.title for j in notified}
    assert "Python Developer" in notified_titles
    assert "Backend Engineer" in notified_titles
    assert "Marketing Manager" not in notified_titles


@pytest.mark.asyncio
async def test_pipeline_logs_warning_when_notification_fails(
    tmp_path, monkeypatch, caplog, fake_settings
):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    monkeypatch.setattr("worksearcher.main._ALL_SCRAPERS", {"fake": _make_fake_scraper([_job(1)])})
    fake_settings.enabled_scrapers_list = ["fake"]
    monkeypatch.setattr("worksearcher.main.get_connection", lambda path: sqlite3.connect(db_path))

    async def fake_send_digest(j, config):
        return False

    monkeypatch.setattr("worksearcher.main.send_digest", fake_send_digest)

    with caplog.at_level(logging.WARNING, logger="worksearcher.main"):
        await _run_pipeline(fake_settings)

    assert any("Notification failed" in r.message for r in caplog.records)


def test_scrapers_list_includes_new_platforms():
    from worksearcher.main import _ALL_SCRAPERS

    assert "himalayas" in _ALL_SCRAPERS
    assert "hackernews" in _ALL_SCRAPERS


def test_all_scrapers_dict_includes_all_platforms():
    from worksearcher.main import _ALL_SCRAPERS

    expected = {
        "jobspy",
        "remoteok",
        "remotive",
        "wwr",
        "cybersecjobs",
        "computrabajo",
        "bumeran",
        "himalayas",
        "hackernews",
        "occ",
    }
    assert set(_ALL_SCRAPERS.keys()) == expected


def test_enabled_scrapers_defaults_to_all():
    from worksearcher.config import Settings

    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert set(s.enabled_scrapers_list) == {
        "jobspy",
        "remoteok",
        "remotive",
        "wwr",
        "cybersecjobs",
        "computrabajo",
        "bumeran",
        "himalayas",
        "hackernews",
        "occ",
    }


def test_enabled_scrapers_rejects_unknown_name():
    from pydantic import ValidationError

    from worksearcher.config import Settings

    with pytest.raises(ValidationError, match="Unknown scrapers"):
        Settings(
            META_PHONE_NUMBER_ID="x",
            META_ACCESS_TOKEN="x",
            META_RECIPIENT_PHONE="x",
            ENABLED_SCRAPERS="jobspy,nonexistent",
        )


@pytest.mark.asyncio
async def test_pipeline_passes_all_filter_params_from_config(tmp_path, monkeypatch, fake_settings):
    """filter_jobs must receive all four new config params from _run_pipeline."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    from worksearcher.core.filters import filter_jobs as real_filter_jobs

    captured_kwargs = {}

    def spy_filter_jobs(jobs, keywords, **kwargs):
        captured_kwargs.update(kwargs)
        return real_filter_jobs(jobs, keywords, **kwargs)

    monkeypatch.setattr("worksearcher.main.filter_jobs", spy_filter_jobs)
    monkeypatch.setattr("worksearcher.main._ALL_SCRAPERS", {"fake": _make_fake_scraper([])})
    fake_settings.enabled_scrapers_list = ["fake"]
    monkeypatch.setattr("worksearcher.main.get_connection", lambda path: sqlite3.connect(db_path))

    async def fake_send_digest(j, config):
        return True

    monkeypatch.setattr("worksearcher.main.send_digest", fake_send_digest)

    await _run_pipeline(fake_settings)

    assert captured_kwargs.get("max_years_experience") == fake_settings.MAX_YEARS_EXPERIENCE
    assert captured_kwargs.get("max_job_age_days") == fake_settings.MAX_JOB_AGE_DAYS
    assert captured_kwargs.get("blacklist") == fake_settings.blacklist_list
    assert captured_kwargs.get("allowed_languages") == fake_settings.filter_languages_list
    assert captured_kwargs.get("min_salary_usd_monthly") == fake_settings.MIN_SALARY_USD_MONTHLY


@pytest.mark.asyncio
async def test_pipeline_marks_only_sent_jobs_as_notified(tmp_path, monkeypatch, fake_settings):
    # Fix 5c549fa: when >MAX_JOBS_PER_MESSAGE new jobs arrive, only the jobs actually
    # included in the WhatsApp message should be marked notified. Previously all new
    # jobs were marked, so the extras would never be retried in future runs.
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    overflow = fake_settings.MAX_JOBS_PER_MESSAGE + 5
    jobs = [_job(i) for i in range(overflow)]
    monkeypatch.setattr("worksearcher.main._ALL_SCRAPERS", {"fake": _make_fake_scraper(jobs)})
    fake_settings.enabled_scrapers_list = ["fake"]
    monkeypatch.setattr("worksearcher.main.get_connection", lambda path: sqlite3.connect(db_path))

    async def fake_send_digest(j, config):
        return True

    monkeypatch.setattr("worksearcher.main.send_digest", fake_send_digest)

    await _run_pipeline(fake_settings)

    conn = sqlite3.connect(db_path)
    notified_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE notified=1").fetchone()[0]
    unnotified_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE notified=0").fetchone()[0]
    conn.close()

    assert notified_count == fake_settings.MAX_JOBS_PER_MESSAGE
    assert unnotified_count == 5


def test_max_jobs_per_message_config_field_exists():
    from worksearcher.config import Settings

    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert s.MAX_JOBS_PER_MESSAGE == 10


def test_scraper_timeout_config_field_exists():
    from worksearcher.config import Settings

    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert s.SCRAPER_TIMEOUT_SECONDS == 120
