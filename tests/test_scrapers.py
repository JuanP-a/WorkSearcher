"""
Scraper parsing tests — pure unit tests using fixture data.
No HTTP calls, no playwright. Tests the parsing logic extracted
from each scraper's response-handling code.
"""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from worksearcher.core.models import JobSource
from worksearcher.core.utils import slugify
from worksearcher.scrapers.bumeran_scraper import _REMOTE_MARKERS as BUMERAN_MARKERS
from worksearcher.scrapers.computrabajo_scraper import _REMOTE_MARKERS as COMPUTRABAJO_MARKERS
from worksearcher.scrapers.cybersecjobs_scraper import scrape as cybersecjobs_scrape
from worksearcher.scrapers.hackernews_scraper import _parse_hn_comment
from worksearcher.scrapers.hackernews_scraper import scrape as hn_scrape
from worksearcher.scrapers.himalayas_scraper import scrape as himalayas_scrape
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


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_parses_jobs_correctly(fake_settings):
    respx.get("https://remoteok.com/api").mock(
        return_value=httpx.Response(200, json=REMOTEOK_FIXTURE)
    )
    jobs = await remoteok_scrape(fake_settings)
    assert len(jobs) == 2
    assert jobs[0].title == "Python Developer"
    assert jobs[0].company == "Startup"
    assert jobs[0].source == JobSource.REMOTEOK
    assert jobs[0].is_remote is True
    assert jobs[0].url.startswith("https://remoteok.com/remote-jobs/")


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_skips_metadata_item(fake_settings):
    respx.get("https://remoteok.com/api").mock(
        return_value=httpx.Response(200, json=REMOTEOK_FIXTURE)
    )
    jobs = await remoteok_scrape(fake_settings)
    # metadata item has no "position" key — should be skipped
    titles = [j.title for j in jobs]
    assert "metadata item" not in titles


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_returns_empty_on_http_error(fake_settings):
    respx.get("https://remoteok.com/api").mock(return_value=httpx.Response(500))
    jobs = await remoteok_scrape(fake_settings)
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_returns_empty_on_network_error(fake_settings):
    respx.get("https://remoteok.com/api").mock(side_effect=httpx.ConnectError("timeout"))
    jobs = await remoteok_scrape(fake_settings)
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
async def test_remotive_parses_jobs_correctly(fake_settings):
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=REMOTIVE_FIXTURE)
    )
    jobs = await remotive_scrape(fake_settings)
    assert len(jobs) == 2
    assert jobs[0].title == "Backend Developer"
    assert jobs[0].company == "Remote Co"
    assert jobs[0].source == JobSource.REMOTIVE
    assert jobs[0].is_remote is True


@pytest.mark.asyncio
@respx.mock
async def test_remotive_handles_empty_jobs_list(fake_settings):
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json={"jobs": []})
    )
    jobs = await remotive_scrape(fake_settings)
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_remotive_handles_missing_jobs_key(fake_settings):
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json={"error": "unexpected"})
    )
    jobs = await remotive_scrape(fake_settings)
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_remotive_returns_empty_on_http_error(fake_settings):
    respx.get("https://remotive.com/api/remote-jobs").mock(return_value=httpx.Response(429))
    jobs = await remotive_scrape(fake_settings)
    assert jobs == []


# --- slugify (shared utility used by Bumeran and Computrabajo) ---


def test_slugify_spaces_to_dashes():
    assert slugify("seguridad informatica") == "seguridad-informatica"


def test_slugify_lowercases():
    assert slugify("Python") == "python"


def test_slugify_strips_special_chars():
    assert slugify("c++") == "c"


def test_slugify_software_engineer():
    assert slugify("software engineer") == "software-engineer"


def test_slugify_devops():
    assert slugify("DevOps") == "devops"


# --- Bumeran: remote markers ---


def test_bumeran_remote_markers_cover_common_terms():
    assert "remoto" in BUMERAN_MARKERS
    assert "home office" in BUMERAN_MARKERS
    assert "teletrabajo" in BUMERAN_MARKERS


# --- Computrabajo: remote markers ---


def test_computrabajo_remote_markers_cover_common_terms():
    assert "remoto" in COMPUTRABAJO_MARKERS
    assert "home office" in COMPUTRABAJO_MARKERS


# --- CyberSecJobs: HTML parsing via mocked HTTP ---

_ISECJOBS_HTML = """
<html><body>
  <div class="card">
    <h5><a class="stretched-link" href="/job/123">Security Engineer</a></h5>
    <small>SecureCorp</small>
  </div>
  <div class="card">
    <h5><a class="stretched-link" href="/job/456">Penetration Tester</a></h5>
    <small>CyberFirm</small>
  </div>
</body></html>
"""

_ISECJOBS_EMPTY_HTML = "<html><body><p>No jobs found</p></body></html>"


@pytest.mark.asyncio
@respx.mock
async def test_cybersecjobs_parses_jobs_correctly(fake_settings):
    respx.get("https://isecjobs.com/?remote=1").mock(
        return_value=httpx.Response(200, text=_ISECJOBS_HTML)
    )
    jobs = await cybersecjobs_scrape(fake_settings)
    assert len(jobs) == 2
    titles = {j.title for j in jobs}
    assert "Security Engineer" in titles
    assert "Penetration Tester" in titles
    assert all(j.source == JobSource.CYBERSECJOBS for j in jobs)
    assert all(j.is_remote for j in jobs)


@pytest.mark.asyncio
@respx.mock
async def test_cybersecjobs_extracts_company_from_card(fake_settings):
    respx.get("https://isecjobs.com/?remote=1").mock(
        return_value=httpx.Response(200, text=_ISECJOBS_HTML)
    )
    jobs = await cybersecjobs_scrape(fake_settings)
    companies = {j.company for j in jobs}
    assert "SecureCorp" in companies
    assert "CyberFirm" in companies


@pytest.mark.asyncio
@respx.mock
async def test_cybersecjobs_returns_empty_when_no_links(fake_settings):
    respx.get("https://isecjobs.com/?remote=1").mock(
        return_value=httpx.Response(200, text=_ISECJOBS_EMPTY_HTML)
    )
    jobs = await cybersecjobs_scrape(fake_settings)
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_cybersecjobs_returns_empty_on_http_error(fake_settings):
    respx.get("https://isecjobs.com/?remote=1").mock(return_value=httpx.Response(503))
    jobs = await cybersecjobs_scrape(fake_settings)
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_cybersecjobs_does_not_follow_redirects(fake_settings):
    # Fix 50a10ed: follow_redirects=False prevents SSRF via open redirect.
    # If the scraper followed the redirect, it would request attacker.com (mocked
    # below) — respx would record the call and the assertion would fail.
    redirect_target = respx.get("https://attacker.example.com/").mock(
        return_value=httpx.Response(200, text="<html></html>")
    )
    respx.get("https://isecjobs.com/?remote=1").mock(
        return_value=httpx.Response(301, headers={"Location": "https://attacker.example.com/"})
    )
    jobs = await cybersecjobs_scrape(fake_settings)
    assert not redirect_target.called
    assert jobs == []


# --- Himalayas scraper: parse fixture response ---

HIMALAYAS_FIXTURE = {
    "jobs": [
        {
            "title": "Backend Engineer",
            "companyName": "Acme Corp",
            "applicationLink": "https://himalayas.app/companies/acme/jobs/backend-engineer",
            "guid": "https://himalayas.app/companies/acme/jobs/backend-engineer",
            "description": "<p>Python and Django experience required.</p>",
            "locationRestrictions": [],
        },
        {
            "title": "Frontend Developer",
            "companyName": "Beta Inc",
            "applicationLink": "https://himalayas.app/companies/beta/jobs/frontend-dev",
            "guid": "https://himalayas.app/companies/beta/jobs/frontend-dev",
            "description": "<p>React and TypeScript experience.</p>",
            "locationRestrictions": ["USA"],
        },
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_parses_jobs_correctly(fake_settings):
    respx.get("https://himalayas.app/jobs/api").mock(
        return_value=httpx.Response(200, json=HIMALAYAS_FIXTURE)
    )
    jobs = await himalayas_scrape(fake_settings)
    assert len(jobs) == 2
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "Acme Corp"
    assert jobs[0].source == JobSource.HIMALAYAS
    assert jobs[0].is_remote is True
    assert "himalayas.app" in jobs[0].url


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_returns_empty_on_http_error(fake_settings):
    respx.get("https://himalayas.app/jobs/api").mock(return_value=httpx.Response(503))
    jobs = await himalayas_scrape(fake_settings)
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_handles_empty_jobs_list(fake_settings):
    respx.get("https://himalayas.app/jobs/api").mock(
        return_value=httpx.Response(200, json={"jobs": []})
    )
    jobs = await himalayas_scrape(fake_settings)
    assert jobs == []


# --- HackerNews "Who's Hiring" scraper ---

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
HN_ITEMS_URL = "https://hn.algolia.com/api/v1/items/48000000"

HN_SEARCH_FIXTURE = {
    "hits": [{"objectID": "48000000", "title": "Ask HN: Who is hiring? (June 2026)"}]
}

HN_ITEMS_FIXTURE = {
    "type": "story",
    "id": 48000000,
    "title": "Ask HN: Who is hiring? (June 2026)",
    "children": [
        {
            "type": "comment",
            "id": 48000001,
            "author": "alice",
            "text": "Acme Corp | Backend Engineer | Remote | REMOTE | $120-150K<p>We use Python and Django.",
        },
        {
            "type": "comment",
            "id": 48000002,
            "author": "bob",
            "text": "Beta Inc | Security Analyst | NYC | ONSITE",
        },
        {
            "type": "comment",
            "id": 48000003,
            "author": None,
            "text": None,  # deleted comment — must be skipped
        },
    ],
}


def test_parse_hn_comment_pipe_format():
    title, company = _parse_hn_comment("Acme Corp | Backend Engineer | Remote | REMOTE")
    assert company == "Acme Corp"
    assert title == "Backend Engineer"


def test_parse_hn_comment_no_pipe():
    title, company = _parse_hn_comment("We are hiring engineers with 5+ years experience")
    assert title == "We are hiring engineers with 5+ years experience"
    assert company == ""


def test_parse_hn_comment_strips_html():
    title, company = _parse_hn_comment("Acme &#x2F; Corp | Engineer<p>details here")
    assert "/" in company  # &#x2F; decoded to /
    assert "<p>" not in title


@pytest.mark.asyncio
@respx.mock
async def test_hackernews_parses_jobs_correctly(fake_settings):
    respx.get(HN_SEARCH_URL).mock(return_value=httpx.Response(200, json=HN_SEARCH_FIXTURE))
    respx.get(HN_ITEMS_URL).mock(return_value=httpx.Response(200, json=HN_ITEMS_FIXTURE))
    jobs = await hn_scrape(fake_settings)
    assert len(jobs) == 2  # deleted comment skipped
    assert jobs[0].company == "Acme Corp"
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].source == JobSource.HACKERNEWS
    assert jobs[0].is_remote is True  # REMOTE comment
    assert jobs[1].is_remote is False  # ONSITE comment


@pytest.mark.asyncio
@respx.mock
async def test_hackernews_returns_empty_on_no_thread(fake_settings):
    respx.get(HN_SEARCH_URL).mock(return_value=httpx.Response(200, json={"hits": []}))
    jobs = await hn_scrape(fake_settings)
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_hackernews_returns_empty_on_http_error(fake_settings):
    respx.get(HN_SEARCH_URL).mock(return_value=httpx.Response(500))
    jobs = await hn_scrape(fake_settings)
    assert jobs == []


# --- posted_at population tests ---

# --- Himalayas: posted_at ---

HIMALAYAS_FIXTURE_WITH_DATE = {
    "jobs": [
        {
            "title": "Backend Engineer",
            "companyName": "Acme Corp",
            "applicationLink": "https://himalayas.app/companies/acme/jobs/backend",
            "guid": "https://himalayas.app/companies/acme/jobs/backend",
            "description": "Python role",
            "locationRestrictions": [],
            "pubDate": 1700000000,
        }
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_populates_posted_at(fake_settings):
    respx.get("https://himalayas.app/jobs/api").mock(
        return_value=httpx.Response(200, json=HIMALAYAS_FIXTURE_WITH_DATE)
    )
    jobs = await himalayas_scrape(fake_settings)
    assert jobs[0].posted_at is not None
    assert jobs[0].posted_at == datetime.fromtimestamp(1700000000, tz=UTC)


HIMALAYAS_FIXTURE_RFC2822 = {
    "jobs": [
        {
            "title": "Backend Engineer",
            "companyName": "Acme Corp",
            "applicationLink": "https://himalayas.app/companies/acme/jobs/backend-rfc",
            "guid": "https://himalayas.app/companies/acme/jobs/backend-rfc",
            "description": "Python role",
            "locationRestrictions": [],
            "pubDate": "Mon, 23 Jun 2025 10:00:00 +0000",
        }
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_parses_rfc2822_posted_at(fake_settings):
    # Fix 7b3beec: Himalayas API returns RFC 2822 strings, not Unix timestamps.
    # Before the fix, parsedate_to_datetime was not called for string pubDates
    # and posted_at silently remained None, breaking the age filter entirely.
    respx.get("https://himalayas.app/jobs/api").mock(
        return_value=httpx.Response(200, json=HIMALAYAS_FIXTURE_RFC2822)
    )
    jobs = await himalayas_scrape(fake_settings)
    assert len(jobs) == 1
    assert jobs[0].posted_at is not None
    assert jobs[0].posted_at == datetime(2025, 6, 23, 10, 0, 0, tzinfo=UTC)


# --- RemoteOK: posted_at ---

REMOTEOK_FIXTURE_WITH_DATE = [
    {"legal": "metadata"},
    {
        "position": "Python Developer",
        "company": "Startup",
        "slug": "python-dev-123",
        "description": "We need Python skills",
        "epoch": 1700000000,
    },
]


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_populates_posted_at(fake_settings):
    respx.get("https://remoteok.com/api").mock(
        return_value=httpx.Response(200, json=REMOTEOK_FIXTURE_WITH_DATE)
    )
    jobs = await remoteok_scrape(fake_settings)
    assert jobs[0].posted_at is not None
    assert jobs[0].posted_at == datetime.fromtimestamp(1700000000, tz=UTC)


# --- HackerNews: posted_at ---

HN_ITEMS_FIXTURE_WITH_DATE = {
    "type": "story",
    "id": 48000000,
    "children": [
        {
            "type": "comment",
            "id": 48000001,
            "author": "alice",
            "text": "Acme Corp | Backend Engineer | Remote | REMOTE",
            "created_at_i": 1700000000,
        },
    ],
}


@pytest.mark.asyncio
@respx.mock
async def test_hackernews_populates_posted_at(fake_settings):
    respx.get(HN_SEARCH_URL).mock(return_value=httpx.Response(200, json=HN_SEARCH_FIXTURE))
    respx.get(HN_ITEMS_URL).mock(return_value=httpx.Response(200, json=HN_ITEMS_FIXTURE_WITH_DATE))
    jobs = await hn_scrape(fake_settings)
    assert jobs[0].posted_at is not None
    assert jobs[0].posted_at == datetime.fromtimestamp(1700000000, tz=UTC)


# --- Himalayas: min_salary_usd_monthly ---

HIMALAYAS_FIXTURE_USD_MONTHLY = {
    "jobs": [
        {
            "title": "Backend Engineer",
            "companyName": "Co",
            "applicationLink": "https://himalayas.app/co/backend",
            "guid": "https://himalayas.app/co/backend",
            "description": "Python",
            "locationRestrictions": [],
            "pubDate": None,
            "currency": "USD",
            "minSalary": 2000,
            "salaryPeriod": "monthly",
        }
    ]
}

HIMALAYAS_FIXTURE_USD_ANNUAL = {
    "jobs": [
        {
            "title": "Backend Engineer",
            "companyName": "Co",
            "applicationLink": "https://himalayas.app/co/backend",
            "guid": "https://himalayas.app/co/backend",
            "description": "Python",
            "locationRestrictions": [],
            "pubDate": None,
            "currency": "USD",
            "minSalary": 24000,
            "salaryPeriod": "annual",
        }
    ]
}

HIMALAYAS_FIXTURE_EUR = {
    "jobs": [
        {
            "title": "Backend Engineer",
            "companyName": "Co",
            "applicationLink": "https://himalayas.app/co/backend",
            "guid": "https://himalayas.app/co/backend",
            "description": "Python",
            "locationRestrictions": [],
            "pubDate": None,
            "currency": "EUR",
            "minSalary": 2000,
            "salaryPeriod": "monthly",
        }
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_salary_usd_monthly(fake_settings):
    respx.get("https://himalayas.app/jobs/api").mock(
        return_value=httpx.Response(200, json=HIMALAYAS_FIXTURE_USD_MONTHLY)
    )
    jobs = await himalayas_scrape(fake_settings)
    assert jobs[0].min_salary_usd_monthly == 2000.0


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_salary_usd_annual_converted(fake_settings):
    respx.get("https://himalayas.app/jobs/api").mock(
        return_value=httpx.Response(200, json=HIMALAYAS_FIXTURE_USD_ANNUAL)
    )
    jobs = await himalayas_scrape(fake_settings)
    assert jobs[0].min_salary_usd_monthly == 2000.0  # 24000 / 12


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_salary_non_usd_ignored(fake_settings):
    respx.get("https://himalayas.app/jobs/api").mock(
        return_value=httpx.Response(200, json=HIMALAYAS_FIXTURE_EUR)
    )
    jobs = await himalayas_scrape(fake_settings)
    assert jobs[0].min_salary_usd_monthly is None


# --- RemoteOK: min_salary_usd_monthly ---

REMOTEOK_FIXTURE_WITH_SALARY = [
    {"legal": "metadata"},
    {
        "position": "Python Developer",
        "company": "Startup",
        "slug": "python-dev-123",
        "description": "Python skills",
        "epoch": None,
        "salary_min": 60000,
        "salary_max": 90000,
    },
]

REMOTEOK_FIXTURE_ZERO_SALARY = [
    {"legal": "metadata"},
    {
        "position": "Python Developer",
        "company": "Startup",
        "slug": "python-dev-456",
        "description": "Python skills",
        "epoch": None,
        "salary_min": 0,
        "salary_max": 0,
    },
]


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_salary_populated(fake_settings):
    respx.get("https://remoteok.com/api").mock(
        return_value=httpx.Response(200, json=REMOTEOK_FIXTURE_WITH_SALARY)
    )
    jobs = await remoteok_scrape(fake_settings)
    assert jobs[0].min_salary_usd_monthly == 5000.0  # 60000 / 12


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_zero_salary_treated_as_none(fake_settings):
    respx.get("https://remoteok.com/api").mock(
        return_value=httpx.Response(200, json=REMOTEOK_FIXTURE_ZERO_SALARY)
    )
    jobs = await remoteok_scrape(fake_settings)
    assert jobs[0].min_salary_usd_monthly is None


# --- LatAm scrapers: use config search terms ---


def test_bumeran_search_terms_constant_removed():
    """_SEARCH_TERMS constant must not exist — bumeran reads from config."""
    import worksearcher.scrapers.bumeran_scraper as mod

    assert not hasattr(mod, "_SEARCH_TERMS"), (
        "_SEARCH_TERMS is hardcoded — should come from config.bumeran_search_terms_list"
    )


def test_computrabajo_does_not_slice_keywords_list():
    """Computrabajo must not slice keywords_list; it uses computrabajo_search_terms_list."""
    import inspect  # noqa: PLC0415, I001
    import worksearcher.scrapers.computrabajo_scraper as mod  # noqa: PLC0415

    source = inspect.getsource(mod._blocking_scrape)
    assert "keywords_list[:5]" not in source, (
        "keywords_list[:5] is hardcoded — use config.computrabajo_search_terms_list"
    )


def test_bumeran_search_terms_config_field_exists():
    from worksearcher.config import Settings

    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert s.bumeran_search_terms_list == [
        "desarrollador",
        "programador",
        "backend",
        "ciberseguridad",
        "seguridad informatica",
    ]


def test_computrabajo_search_terms_config_field_exists():
    from worksearcher.config import Settings

    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert s.computrabajo_search_terms_list == [
        "desarrollador",
        "programador",
        "backend",
        "ciberseguridad",
        "seguridad informatica",
    ]


def test_jobspy_config_fields_exist():
    from worksearcher.config import Settings

    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert s.jobspy_sites_list == ["linkedin", "indeed", "glassdoor"]
    assert s.JOBSPY_RESULTS_WANTED == 50
    assert s.JOBSPY_HOURS_OLD == 24
    assert s.SEARCH_LOCATION == "Remote"


def test_http_timeout_config_field_exists():
    from worksearcher.config import Settings

    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert s.HTTP_TIMEOUT_SECONDS == 30
