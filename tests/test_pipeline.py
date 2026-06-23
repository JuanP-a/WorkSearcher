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
    monkeypatch.setattr("worksearcher.main._SCRAPERS", [_make_fake_scraper(jobs)])
    monkeypatch.setattr("worksearcher.main.get_connection", lambda: sqlite3.connect(db_path))

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

    monkeypatch.setattr("worksearcher.main._SCRAPERS", [_make_fake_scraper(existing)])
    monkeypatch.setattr("worksearcher.main.get_connection", lambda: sqlite3.connect(db_path))

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
    monkeypatch.setattr("worksearcher.main._SCRAPERS", [
        _make_failing_scraper(),
        _make_fake_scraper(good_jobs),
    ])
    monkeypatch.setattr("worksearcher.main.get_connection", lambda: sqlite3.connect(db_path))

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
        Job(title="Marketing Manager", company="Ads Co", location="Remote",
            url="https://example.com/job/99", source=JobSource.REMOTEOK,
            is_remote=True, description="brand strategy and campaigns"),
        _job(3, title="Backend Engineer"),
    ]
    monkeypatch.setattr("worksearcher.main._SCRAPERS", [_make_fake_scraper(jobs)])
    monkeypatch.setattr("worksearcher.main.get_connection", lambda: sqlite3.connect(db_path))

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
async def test_pipeline_logs_warning_when_notification_fails(tmp_path, monkeypatch, caplog, fake_settings):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    monkeypatch.setattr("worksearcher.main._SCRAPERS", [_make_fake_scraper([_job(1)])])
    monkeypatch.setattr("worksearcher.main.get_connection", lambda: sqlite3.connect(db_path))

    async def fake_send_digest(j, config):
        return False

    monkeypatch.setattr("worksearcher.main.send_digest", fake_send_digest)

    with caplog.at_level(logging.WARNING, logger="worksearcher.main"):
        await _run_pipeline(fake_settings)

    assert any("Notification failed" in r.message for r in caplog.records)
