# New Scrapers (Himalayas + HackerNews) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new remote job scrapers — Himalayas (public JSON API) and HackerNews "Who's Hiring" (Algolia API) — integrating them into the existing pipeline.

**Architecture:** Each scraper follows the existing pattern: a single `async def scrape(config: Settings) -> list[Job]` function registered in `main.py`'s `_SCRAPERS` list. Both use `httpx` only (no new dependencies). The existing `filter_jobs` and deduplicator downstream handle keyword/remote filtering.

**Tech Stack:** Python 3.12, `httpx`, `beautifulsoup4` (already installed), `pytest`, `respx`

---

## Investigation notes (pre-plan)

- **Getonbrd**: Returns 401 Unauthorized — not actually a public API. Discarded.
- **InfoSec-Jobs.com**: Already covered by existing `cybersecjobs_scraper.py` (scrapes `isecjobs.com`).
- **Himalayas**: Public JSON API at `https://himalayas.app/jobs/api`. No key required. Verified working.
  - Response: `{"jobs": [{"title": ..., "companyName": ..., "applicationLink": ..., "description": ..., "locationRestrictions": [...]}]}`
  - `locationRestrictions: []` = worldwide/fully remote.
- **HackerNews**: Algolia public API, no key, no proxy needed. Monthly thread confirmed for June 2026.
  - Step 1: `GET https://hn.algolia.com/api/v1/search?query=Ask+HN%3A+Who+is+hiring%3F+%28{Month}+{Year}%29&tags=story%2Cauthor_whoishiring&hitsPerPage=1`
  - Step 2: `GET https://hn.algolia.com/api/v1/items/{objectID}` → `children[]` are top-level comments.
  - Comment text is HTML-encoded (`<p>`, `&#x2F;`, etc.). First line format: `Company | Role | Location | REMOTE | ...`

---

## File map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `worksearcher/core/models.py` | Add `HIMALAYAS` and `HACKERNEWS` to `JobSource` |
| Create | `worksearcher/scrapers/himalayas_scraper.py` | Himalayas public API scraper |
| Create | `worksearcher/scrapers/hackernews_scraper.py` | HackerNews Algolia API scraper |
| Modify | `worksearcher/main.py` | Import + register both scrapers in `_SCRAPERS` |
| Modify | `tests/test_scrapers.py` | Unit tests for both scrapers (mocked HTTP) |
| Modify | `tests/test_models.py` | Update `test_job_source_enum_covers_all_platforms` |

---

## Task 1: Extend JobSource enum

**Files:**
- Modify: `worksearcher/core/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_models.py`, update `test_job_source_enum_covers_all_platforms`:

```python
def test_job_source_enum_covers_all_platforms():
    # All 11 target platforms must be represented
    assert JobSource.LINKEDIN == "linkedin"
    assert JobSource.INDEED == "indeed"
    assert JobSource.GLASSDOOR == "glassdoor"
    assert JobSource.REMOTEOK == "remoteok"
    assert JobSource.REMOTIVE == "remotive"
    assert JobSource.WWR == "weworkremotely"
    assert JobSource.CYBERSECJOBS == "cybersecjobs"
    assert JobSource.COMPUTRABAJO == "computrabajo"
    assert JobSource.BUMERAN == "bumeran"
    assert JobSource.HIMALAYAS == "himalayas"
    assert JobSource.HACKERNEWS == "hackernews"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py::test_job_source_enum_covers_all_platforms -v
```

Expected: `AttributeError: HIMALAYAS` (enum value missing).

- [ ] **Step 3: Add enum values**

In `worksearcher/core/models.py`, add after `BUMERAN`:

```python
class JobSource(StrEnum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    REMOTEOK = "remoteok"
    REMOTIVE = "remotive"
    WWR = "weworkremotely"
    CYBERSECJOBS = "cybersecjobs"
    COMPUTRABAJO = "computrabajo"
    BUMERAN = "bumeran"
    HIMALAYAS = "himalayas"
    HACKERNEWS = "hackernews"
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_models.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add worksearcher/core/models.py tests/test_models.py
git commit -m "feat: add HIMALAYAS and HACKERNEWS to JobSource enum"
```

---

## Task 2: Himalayas scraper

**Files:**
- Create: `worksearcher/scrapers/himalayas_scraper.py`
- Modify: `tests/test_scrapers.py`

### API details (verified)

- URL: `https://himalayas.app/jobs/api?limit=50`
- Response: `{"jobs": [{"title": str, "companyName": str, "applicationLink": str, "description": str, "locationRestrictions": list[str]}]}`
- `locationRestrictions: []` means worldwide (fully remote, no restriction).
- All Himalayas jobs are remote by definition.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scrapers.py`:

```python
from worksearcher.scrapers.himalayas_scraper import scrape as himalayas_scrape

HIMALAYAS_API = "https://himalayas.app/jobs/api"

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
    respx.get(HIMALAYAS_API).mock(
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
    respx.get(HIMALAYAS_API).mock(
        return_value=httpx.Response(503)
    )
    jobs = await himalayas_scrape(fake_settings)
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_handles_empty_jobs_list(fake_settings):
    respx.get(HIMALAYAS_API).mock(
        return_value=httpx.Response(200, json={"jobs": []})
    )
    jobs = await himalayas_scrape(fake_settings)
    assert jobs == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scrapers.py::test_himalayas_parses_jobs_correctly -v
```

Expected: `ModuleNotFoundError: No module named 'worksearcher.scrapers.himalayas_scraper'`

- [ ] **Step 3: Implement the scraper**

Create `worksearcher/scrapers/himalayas_scraper.py`:

```python
import logging

import httpx

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

HIMALAYAS_API = "https://himalayas.app/jobs/api"


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "WorkSearcher/1.0"},
            timeout=30,
        ) as client:
            response = await client.get(HIMALAYAS_API, params={"limit": 50})
            response.raise_for_status()
            data = response.json()

        listings = data.get("jobs", [])
        jobs = []
        for item in listings:
            try:
                url = item.get("applicationLink") or item.get("guid", "")
                location_restrictions = item.get("locationRestrictions", [])
                location = location_restrictions[0] if location_restrictions else "Remote"
                job = Job(
                    title=item.get("title", ""),
                    company=item.get("companyName", ""),
                    location=location,
                    url=url,
                    source=JobSource.HIMALAYAS,
                    is_remote=True,
                    description=item.get("description", ""),
                )
                jobs.append(job)
            except Exception as exc:
                logger.warning("Himalayas: skipping malformed job %s: %s", item.get("guid", "?"), exc)
                continue

        logger.info("Himalayas: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("Himalayas scraper failed: %s", exc)
        return []
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_scrapers.py -k himalayas -v
```

Expected: all 3 Himalayas tests PASS.

- [ ] **Step 5: Commit**

```bash
git add worksearcher/scrapers/himalayas_scraper.py tests/test_scrapers.py
git commit -m "feat: add Himalayas scraper via public JSON API"
```

---

## Task 3: HackerNews Who's Hiring scraper

**Files:**
- Create: `worksearcher/scrapers/hackernews_scraper.py`
- Modify: `tests/test_scrapers.py`

### API details (verified)

Two-step fetch:

**Step 1** — Find latest monthly thread (title format: "Ask HN: Who is hiring? (Month Year)"):
```
GET https://hn.algolia.com/api/v1/search
    ?query=Ask+HN%3A+Who+is+hiring%3F
    &tags=story%2Cauthor_whoishiring
    &hitsPerPage=1
```
Response: `{"hits": [{"objectID": "48357725", "title": "Ask HN: Who is hiring? (June 2026)"}]}`

**Step 2** — Get all top-level comments:
```
GET https://hn.algolia.com/api/v1/items/{objectID}
```
Response:
```json
{
  "type": "story",
  "children": [
    {
      "type": "comment",
      "author": "chrisposhka",
      "text": "Pathos AI | Senior Software &#x2F; AI Engineer | NYC (hybrid) | REMOTE | $180-200K<p>Details...",
      "id": 12345
    }
  ]
}
```

Comments with `text: null` are deleted — skip them. Each top-level comment is one job post. The `text` field is HTML (use BeautifulSoup to strip tags). First line of plain text typically has: `Company | Role | Location | ...`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scrapers.py`:

```python
from worksearcher.scrapers.hackernews_scraper import scrape as hn_scrape, _parse_hn_comment

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
    respx.get(HN_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=HN_SEARCH_FIXTURE)
    )
    respx.get(HN_ITEMS_URL).mock(
        return_value=httpx.Response(200, json=HN_ITEMS_FIXTURE)
    )
    jobs = await hn_scrape(fake_settings)
    assert len(jobs) == 2  # deleted comment skipped
    assert jobs[0].company == "Acme Corp"
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].source == JobSource.HACKERNEWS
    assert jobs[0].is_remote is True


@pytest.mark.asyncio
@respx.mock
async def test_hackernews_skips_deleted_comments(fake_settings):
    respx.get(HN_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=HN_SEARCH_FIXTURE)
    )
    respx.get(HN_ITEMS_URL).mock(
        return_value=httpx.Response(200, json=HN_ITEMS_FIXTURE)
    )
    jobs = await hn_scrape(fake_settings)
    authors = {j.company for j in jobs}
    assert "" not in authors or len(jobs) == 2  # deleted comment has no author/text


@pytest.mark.asyncio
@respx.mock
async def test_hackernews_returns_empty_on_no_thread(fake_settings):
    respx.get(HN_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"hits": []})
    )
    jobs = await hn_scrape(fake_settings)
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_hackernews_returns_empty_on_http_error(fake_settings):
    respx.get(HN_SEARCH_URL).mock(
        return_value=httpx.Response(500)
    )
    jobs = await hn_scrape(fake_settings)
    assert jobs == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scrapers.py -k hackernews -v
```

Expected: `ModuleNotFoundError: No module named 'worksearcher.scrapers.hackernews_scraper'`

- [ ] **Step 3: Implement the scraper**

Create `worksearcher/scrapers/hackernews_scraper.py`:

```python
import logging

import httpx
from bs4 import BeautifulSoup

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
HN_ITEMS_URL = "https://hn.algolia.com/api/v1/items/{thread_id}"


def _parse_hn_comment(text: str) -> tuple[str, str]:
    """Extract (title, company) from first line of an HN job comment.

    HN job posts have no fixed format; the common pattern is:
        Company | Role | Location | REMOTE | salary
    We take the first line, strip HTML, split on '|'.
    """
    plain = BeautifulSoup(text, "html.parser").get_text()
    first_line = plain.split("\n")[0].strip()
    parts = [p.strip() for p in first_line.split("|")]
    if len(parts) >= 2:
        return parts[1], parts[0]
    return first_line, ""


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "WorkSearcher/1.0"},
            timeout=30,
        ) as client:
            # Step 1: find latest monthly "Who is hiring?" thread
            search_resp = await client.get(
                HN_SEARCH_URL,
                params={
                    "query": "Ask HN: Who is hiring?",
                    "tags": "story,author_whoishiring",
                    "hitsPerPage": 1,
                },
            )
            search_resp.raise_for_status()
            hits = search_resp.json().get("hits", [])
            if not hits:
                logger.warning("HackerNews: no 'Who is hiring?' thread found")
                return []

            thread_id = hits[0]["objectID"]
            logger.info("HackerNews: scraping thread %s — %s", thread_id, hits[0].get("title", ""))

            # Step 2: fetch all top-level comments in one request
            items_resp = await client.get(HN_ITEMS_URL.format(thread_id=thread_id))
            items_resp.raise_for_status()
            thread = items_resp.json()

        jobs = []
        for child in thread.get("children", []):
            text = child.get("text")
            if not text:
                continue  # deleted or empty comment
            try:
                title, company = _parse_hn_comment(text)
                if not title:
                    continue
                job_id = child.get("id", "")
                job = Job(
                    title=title,
                    company=company,
                    location="Remote",
                    url=f"https://news.ycombinator.com/item?id={job_id}",
                    source=JobSource.HACKERNEWS,
                    is_remote=True,
                    description=BeautifulSoup(text, "html.parser").get_text(),
                )
                jobs.append(job)
            except Exception as exc:
                logger.warning("HackerNews: skipping malformed comment %s: %s", child.get("id", "?"), exc)
                continue

        logger.info("HackerNews: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("HackerNews scraper failed: %s", exc)
        return []
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_scrapers.py -k hackernews -v
```

Expected: all 5 HackerNews tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add worksearcher/scrapers/hackernews_scraper.py tests/test_scrapers.py
git commit -m "feat: add HackerNews Who's Hiring scraper via Algolia API"
```

---

## Task 4: Register scrapers in pipeline

**Files:**
- Modify: `worksearcher/main.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py` (check existing file first — add if similar test doesn't exist):

```python
def test_scrapers_list_includes_new_platforms():
    from worksearcher.main import _SCRAPERS
    scraper_names = {s.__module__ for s in _SCRAPERS}
    assert "worksearcher.scrapers.himalayas_scraper" in scraper_names
    assert "worksearcher.scrapers.hackernews_scraper" in scraper_names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_pipeline.py::test_scrapers_list_includes_new_platforms -v
```

Expected: FAIL — scrapers not yet registered.

- [ ] **Step 3: Register in main.py**

In `worksearcher/main.py`, add imports and register:

```python
from worksearcher.scrapers import (
    bumeran_scraper,
    computrabajo_scraper,
    cybersecjobs_scraper,
    hackernews_scraper,
    himalayas_scraper,
    jobspy_scraper,
    remoteok_scraper,
    remotive_scraper,
    wwr_scraper,
)

_SCRAPERS: list[Callable[[Settings], Coroutine[None, None, list[Job]]]] = [
    jobspy_scraper.scrape,
    remoteok_scraper.scrape,
    remotive_scraper.scrape,
    wwr_scraper.scrape,
    cybersecjobs_scraper.scrape,
    computrabajo_scraper.scrape,
    bumeran_scraper.scrape,
    himalayas_scraper.scrape,
    hackernews_scraper.scrape,
]
```

- [ ] **Step 4: Run tests**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 5: Lint**

```bash
uvx ruff check worksearcher/ tests/
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add worksearcher/main.py tests/test_pipeline.py
git commit -m "feat: register Himalayas and HackerNews scrapers in pipeline"
```

---

## Self-review checklist

- [x] Both scrapers follow existing `async def scrape(config) -> list[Job]` interface
- [x] Both use `httpx` only — no new dependencies
- [x] `JobSource` enum updated and test updated
- [x] Error handling: all scrapers return `[]` on any failure (consistent with existing)
- [x] Deleted HN comments (text=None) are skipped
- [x] Tests use `respx.mock` — no real HTTP calls
- [x] Lint check included in Task 4
- [x] All tasks end with a commit
