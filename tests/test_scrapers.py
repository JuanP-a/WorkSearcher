"""
Scraper parsing tests — pure unit tests using fixture data.
No HTTP calls, no playwright. Tests the parsing logic extracted
from each scraper's response-handling code.
"""

import httpx
import pytest
import respx

from worksearcher.core.models import JobSource
from worksearcher.scrapers.remoteok_scraper import scrape as remoteok_scrape
from worksearcher.scrapers.remotive_scraper import scrape as remotive_scrape
from worksearcher.scrapers.wwr_scraper import _parse_title_and_company

# --- WWR: _parse_title_and_company ---

def test_wwr_parse_standard_format():
    title, company = _parse_title_and_company("Engineering: Backend Engineer at Acme Corp")
    assert title == "Backend Engineer"
    assert company == "Acme Corp"


def test_wwr_parse_no_category():
    title, company = _parse_title_and_company("Backend Engineer at Acme Corp")
    assert title == "Backend Engineer"
    assert company == "Acme Corp"


def test_wwr_parse_no_at_sign():
    title, company = _parse_title_and_company("Engineering: Backend Engineer")
    assert title == "Backend Engineer"
    assert company == ""


def test_wwr_parse_empty_string():
    title, company = _parse_title_and_company("")
    assert title == ""
    assert company == ""


def test_wwr_parse_company_with_spaces():
    title, company = _parse_title_and_company("Design: Product Designer at Big Tech Company Inc")
    assert title == "Product Designer"
    assert company == "Big Tech Company Inc"


# --- RemoteOK scraper: parse fixture response ---

REMOTEOK_FIXTURE = [
    {"legal": "metadata item"},  # first item is metadata — should be skipped
    {
        "position": "Python Developer",
        "company": "Startup",
        "slug": "python-developer-startup-123",
        "description": "<p>We need Python skills</p>",
        "tags": ["python", "remote"],
    },
    {
        "position": "Security Engineer",
        "company": "SecureCo",
        "slug": "security-engineer-secureco-456",
        "description": "SOC experience required",
        "tags": ["security", "remote"],
    },
]


class FakeSettings:
    keywords_list = ["python", "backend", "cybersecurity"]
    MAX_YEARS_EXPERIENCE = 3


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_parses_jobs_correctly():
    respx.get("https://remoteok.com/api").mock(
        return_value=httpx.Response(200, json=REMOTEOK_FIXTURE)
    )
    jobs = await remoteok_scrape(FakeSettings())
    assert len(jobs) == 2
    assert jobs[0].title == "Python Developer"
    assert jobs[0].company == "Startup"
    assert jobs[0].source == JobSource.REMOTEOK
    assert jobs[0].is_remote is True
    assert "slug" not in jobs[0].url or "remoteok.com" in jobs[0].url


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_skips_metadata_item():
    respx.get("https://remoteok.com/api").mock(
        return_value=httpx.Response(200, json=REMOTEOK_FIXTURE)
    )
    jobs = await remoteok_scrape(FakeSettings())
    # metadata item has no "position" key — should be skipped
    titles = [j.title for j in jobs]
    assert "metadata item" not in titles


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_returns_empty_on_http_error():
    respx.get("https://remoteok.com/api").mock(
        return_value=httpx.Response(500)
    )
    jobs = await remoteok_scrape(FakeSettings())
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_returns_empty_on_network_error():
    respx.get("https://remoteok.com/api").mock(
        side_effect=httpx.ConnectError("timeout")
    )
    jobs = await remoteok_scrape(FakeSettings())
    assert jobs == []


# --- Remotive scraper: parse fixture response ---

REMOTIVE_FIXTURE = {
    "jobs": [
        {
            "id": 1,
            "title": "Backend Developer",
            "company_name": "Remote Co",
            "candidate_required_location": "Worldwide",
            "url": "https://remotive.com/remote-jobs/software-dev/backend-1",
            "description": "Python and Django experience",
        },
        {
            "id": 2,
            "title": "SOC Analyst",
            "company_name": "CyberFirm",
            "candidate_required_location": "Remote",
            "url": "https://remotive.com/remote-jobs/security/soc-2",
            "description": "Monitor security events",
        },
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_remotive_parses_jobs_correctly():
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=REMOTIVE_FIXTURE)
    )
    jobs = await remotive_scrape(FakeSettings())
    assert len(jobs) == 2
    assert jobs[0].title == "Backend Developer"
    assert jobs[0].company == "Remote Co"
    assert jobs[0].source == JobSource.REMOTIVE
    assert jobs[0].is_remote is True


@pytest.mark.asyncio
@respx.mock
async def test_remotive_handles_empty_jobs_list():
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json={"jobs": []})
    )
    jobs = await remotive_scrape(FakeSettings())
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_remotive_handles_missing_jobs_key():
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json={"error": "unexpected"})
    )
    jobs = await remotive_scrape(FakeSettings())
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_remotive_returns_empty_on_http_error():
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(429)
    )
    jobs = await remotive_scrape(FakeSettings())
    assert jobs == []
