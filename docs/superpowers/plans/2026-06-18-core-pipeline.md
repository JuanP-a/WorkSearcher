# Core Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full automated job search pipeline: scrape LinkedIn/Indeed/Glassdoor/RemoteOK/Remotive, filter for remote dev+cybersecurity roles, deduplicate against SQLite history, and send new jobs as a WhatsApp digest via Meta Cloud API.

**Architecture:** Functional core (models, filters, deduplicator — pure functions, no I/O) wrapped by an imperative shell (scrapers, DB, notifier — all I/O). Pipeline is orchestrated by a Click CLI that runs all scrapers concurrently via `asyncio.gather`, then feeds results through the pure core, then persists and notifies.

**Tech Stack:** Python 3.12, pydantic v2, pydantic-settings, jobspy, httpx, playwright, click, sqlite3 (stdlib), pytest

---

## File Map

| File | Responsibility |
|---|---|
| `requirements.txt` | All dependencies pinned |
| `worksearcher/__init__.py` | Empty package marker |
| `worksearcher/config.py` | Pydantic Settings — reads `.env` |
| `worksearcher/core/__init__.py` | Empty |
| `worksearcher/core/models.py` | `Job` Pydantic model + `JobSource` enum + fingerprint |
| `worksearcher/core/filters.py` | `is_relevant()` + `filter_jobs()` — pure functions |
| `worksearcher/core/deduplicator.py` | `deduplicate()` — pure function |
| `worksearcher/storage/__init__.py` | Empty |
| `worksearcher/storage/database.py` | SQLite CRUD: `init_db`, `save_jobs`, `get_seen_fingerprints` |
| `worksearcher/scrapers/__init__.py` | Empty |
| `worksearcher/scrapers/remoteok_scraper.py` | RemoteOK public JSON API |
| `worksearcher/scrapers/remotive_scraper.py` | Remotive public JSON API |
| `worksearcher/scrapers/jobspy_scraper.py` | jobspy wrapper for LinkedIn/Indeed/Glassdoor |
| `worksearcher/notifier/__init__.py` | Empty |
| `worksearcher/notifier/whatsapp.py` | Meta Cloud API WhatsApp sender |
| `worksearcher/main.py` | Click CLI + pipeline orchestrator |
| `worksearcher/__main__.py` | Entry point for `python -m worksearcher` |
| `tests/__init__.py` | Empty |
| `tests/test_models.py` | Unit tests for Job model + fingerprint |
| `tests/test_filters.py` | Unit tests for filter logic |
| `tests/test_deduplicator.py` | Unit tests for deduplication |
| `tests/test_database.py` | SQLite tests using in-memory DB |

---

## Task 1: Project Bootstrap

**Files:**
- Create: `requirements.txt`
- Create: `worksearcher/__init__.py`
- Create: `worksearcher/core/__init__.py`
- Create: `worksearcher/scrapers/__init__.py`
- Create: `worksearcher/storage/__init__.py`
- Create: `worksearcher/notifier/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
jobspy>=0.1.0
httpx>=0.27.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
playwright>=1.44.0
click>=8.1.7
pytest>=8.2.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: Create all `__init__.py` files**

```bash
touch worksearcher/__init__.py \
      worksearcher/core/__init__.py \
      worksearcher/scrapers/__init__.py \
      worksearcher/storage/__init__.py \
      worksearcher/notifier/__init__.py \
      tests/__init__.py
```

- [ ] **Step 3: Create and activate virtual environment**

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Expected: all packages install without errors.

- [ ] **Step 4: Verify pytest runs (empty suite)**

```bash
pytest tests/ -v
```

Expected: `no tests ran` or `0 passed` — no errors.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt worksearcher/__init__.py worksearcher/core/__init__.py \
        worksearcher/scrapers/__init__.py worksearcher/storage/__init__.py \
        worksearcher/notifier/__init__.py tests/__init__.py
git commit -m "chore: bootstrap project dependencies and package structure"
```

---

## Task 2: Job Model + JobSource Enum

**Files:**
- Create: `worksearcher/core/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_models.py`:

```python
from worksearcher.core.models import Job, JobSource


def test_job_fingerprint_is_computed_on_creation():
    job = Job(
        title="Python Developer",
        company="Acme Corp",
        location="Remote",
        url="https://example.com/job/1",
        source=JobSource.REMOTEOK,
        is_remote=True,
    )
    assert job.fingerprint != ""
    assert len(job.fingerprint) == 64  # SHA256 hex digest


def test_same_data_produces_same_fingerprint():
    kwargs = dict(
        title="Python Developer",
        company="Acme Corp",
        location="Remote",
        url="https://example.com/job/1",
        source=JobSource.REMOTEOK,
        is_remote=True,
    )
    job1 = Job(**kwargs)
    job2 = Job(**kwargs)
    assert job1.fingerprint == job2.fingerprint


def test_different_url_produces_different_fingerprint():
    base = dict(
        title="Dev",
        company="Co",
        location="Remote",
        source=JobSource.REMOTEOK,
        is_remote=True,
    )
    job1 = Job(**base, url="https://example.com/1")
    job2 = Job(**base, url="https://example.com/2")
    assert job1.fingerprint != job2.fingerprint


def test_fingerprint_is_case_insensitive():
    base = dict(company="Co", location="Remote", source=JobSource.REMOTEOK, is_remote=True)
    job1 = Job(**base, title="Python Developer", url="https://example.com/1")
    job2 = Job(**base, title="PYTHON DEVELOPER", url="https://example.com/1")
    assert job1.fingerprint == job2.fingerprint


def test_job_source_enum_values():
    assert JobSource.LINKEDIN == "linkedin"
    assert JobSource.INDEED == "indeed"
    assert JobSource.GLASSDOOR == "glassdoor"
    assert JobSource.REMOTEOK == "remoteok"
    assert JobSource.REMOTIVE == "remotive"
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'worksearcher.core.models'`

- [ ] **Step 3: Implement `worksearcher/core/models.py`**

```python
from enum import StrEnum
from hashlib import sha256
from datetime import datetime

from pydantic import BaseModel, model_validator


class JobSource(StrEnum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    REMOTEOK = "remoteok"
    REMOTIVE = "remotive"


class Job(BaseModel):
    title: str
    company: str
    location: str
    url: str
    source: JobSource
    is_remote: bool
    description: str = ""
    posted_at: datetime | None = None
    fingerprint: str = ""

    @model_validator(mode="after")
    def compute_fingerprint(self) -> "Job":
        raw = f"{self.title}{self.company}{self.url}".lower()
        self.fingerprint = sha256(raw.encode()).hexdigest()
        return self
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_models.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add worksearcher/core/models.py tests/test_models.py
git commit -m "feat: add Job model with JobSource enum and SHA256 fingerprint"
```

---

## Task 3: Configuration (Pydantic Settings)

**Files:**
- Create: `worksearcher/config.py`

No unit tests for config — it reads from env, tested implicitly via integration. We'll verify it loads correctly manually.

- [ ] **Step 1: Implement `worksearcher/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    META_PHONE_NUMBER_ID: str
    META_ACCESS_TOKEN: str
    META_RECIPIENT_PHONE: str
    SEARCH_KEYWORDS: str = "python,backend,cybersecurity,security engineer,SOC,pentester,infosec"
    SCRAPE_INTERVAL_HOURS: int = 4

    @property
    def keywords_list(self) -> list[str]:
        return [k.strip().lower() for k in self.SEARCH_KEYWORDS.split(",")]
```

- [ ] **Step 2: Verify it loads from `.env`**

```bash
cp .env.example .env
# Fill in META_PHONE_NUMBER_ID, META_ACCESS_TOKEN, META_RECIPIENT_PHONE with real values
python -c "from worksearcher.config import Settings; s = Settings(); print(s.keywords_list)"
```

Expected: `['python', 'backend', 'cybersecurity', 'security engineer', 'soc', 'pentester', 'infosec']`

- [ ] **Step 3: Commit**

```bash
git add worksearcher/config.py
git commit -m "feat: add Pydantic Settings config from .env"
```

---

## Task 4: Filter Logic (Pure Functions)

**Files:**
- Create: `worksearcher/core/filters.py`
- Create: `tests/test_filters.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_filters.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_filters.py -v
```

Expected: `ModuleNotFoundError: No module named 'worksearcher.core.filters'`

- [ ] **Step 3: Implement `worksearcher/core/filters.py`**

```python
from worksearcher.core.models import Job


def is_relevant(job: Job, keywords: list[str]) -> bool:
    if not job.is_remote:
        return False
    searchable = f"{job.title} {job.description}".lower()
    return any(kw.lower() in searchable for kw in keywords)


def filter_jobs(jobs: list[Job], keywords: list[str]) -> list[Job]:
    return [j for j in jobs if is_relevant(j, keywords)]
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_filters.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add worksearcher/core/filters.py tests/test_filters.py
git commit -m "feat: add job filter logic with keyword and remote check"
```

---

## Task 5: Deduplicator (Pure Function)

**Files:**
- Create: `worksearcher/core/deduplicator.py`
- Create: `tests/test_deduplicator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_deduplicator.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_deduplicator.py -v
```

Expected: `ModuleNotFoundError: No module named 'worksearcher.core.deduplicator'`

- [ ] **Step 3: Implement `worksearcher/core/deduplicator.py`**

```python
from worksearcher.core.models import Job


def deduplicate(jobs: list[Job], seen: set[str]) -> list[Job]:
    return [j for j in jobs if j.fingerprint not in seen]
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_deduplicator.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: `15 passed` (4 models + 7 filters + 4 deduplicator)

- [ ] **Step 6: Commit**

```bash
git add worksearcher/core/deduplicator.py tests/test_deduplicator.py
git commit -m "feat: add deduplicator using job fingerprint set"
```

---

## Task 6: SQLite Storage

**Files:**
- Create: `worksearcher/storage/database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_database.py`:

```python
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
    job = _job("https://example.com/1", title="Desarrollador de Sofware — México")
    inserted = save_jobs([job], conn)
    assert inserted == 1
    seen = get_seen_fingerprints(conn)
    assert job.fingerprint in seen
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_database.py -v
```

Expected: `ModuleNotFoundError: No module named 'worksearcher.storage.database'`

- [ ] **Step 3: Implement `worksearcher/storage/database.py`**

```python
import sqlite3
import logging
from pathlib import Path

from worksearcher.core.models import Job

logger = logging.getLogger(__name__)

DB_PATH = Path("worksearcher.db")


def get_connection(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            fingerprint TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            company     TEXT NOT NULL,
            location    TEXT,
            url         TEXT NOT NULL,
            source      TEXT NOT NULL,
            is_remote   INTEGER NOT NULL,
            description TEXT,
            posted_at   TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def save_jobs(jobs: list[Job], conn: sqlite3.Connection) -> int:
    if not jobs:
        return 0
    before = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.executemany(
        """
        INSERT OR IGNORE INTO jobs
            (fingerprint, title, company, location, url, source, is_remote, description, posted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                j.fingerprint,
                j.title,
                j.company,
                j.location,
                j.url,
                j.source.value,
                int(j.is_remote),
                j.description,
                j.posted_at.isoformat() if j.posted_at else None,
            )
            for j in jobs
        ],
    )
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    return after - before


def get_seen_fingerprints(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT fingerprint FROM jobs").fetchall()
    return {row[0] for row in rows}
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_database.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -v
```

Expected: `21 passed`

- [ ] **Step 6: Commit**

```bash
git add worksearcher/storage/database.py tests/test_database.py
git commit -m "feat: add SQLite storage with ON CONFLICT IGNORE deduplication"
```

---

## Task 7: RemoteOK Scraper

**Files:**
- Create: `worksearcher/scrapers/remoteok_scraper.py`

No unit tests for scrapers — they hit live APIs. Tested manually via CLI in Task 11.

- [ ] **Step 1: Implement `worksearcher/scrapers/remoteok_scraper.py`**

```python
import httpx
import logging

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

REMOTEOK_API = "https://remoteok.com/api"


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "WorkSearcher/1.0"},
            timeout=30,
        ) as client:
            response = await client.get(REMOTEOK_API)
            response.raise_for_status()
            data = response.json()

        # First item in RemoteOK API response is metadata — skip it
        listings = [item for item in data if isinstance(item, dict) and "position" in item]
        jobs = []
        for item in listings:
            try:
                job = Job(
                    title=item.get("position", ""),
                    company=item.get("company", ""),
                    location="Remote",
                    url=f"https://remoteok.com/remote-jobs/{item.get('slug', '')}",
                    source=JobSource.REMOTEOK,
                    is_remote=True,
                    description=item.get("description", ""),
                )
                jobs.append(job)
            except Exception:
                continue

        logger.info("RemoteOK: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("RemoteOK scraper failed: %s", exc)
        return []
```

- [ ] **Step 2: Smoke-test manually**

```bash
python -c "
import asyncio
from worksearcher.config import Settings
from worksearcher.scrapers import remoteok_scraper
jobs = asyncio.run(remoteok_scraper.scrape(Settings()))
print(f'{len(jobs)} jobs. First: {jobs[0].title if jobs else \"none\"}')
"
```

Expected: prints a count > 0 and a job title.

- [ ] **Step 3: Commit**

```bash
git add worksearcher/scrapers/remoteok_scraper.py
git commit -m "feat: add RemoteOK scraper via public JSON API"
```

---

## Task 8: Remotive Scraper

**Files:**
- Create: `worksearcher/scrapers/remotive_scraper.py`

- [ ] **Step 1: Implement `worksearcher/scrapers/remotive_scraper.py`**

```python
import httpx
import logging

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

REMOTIVE_API = "https://remotive.com/api/remote-jobs"


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(REMOTIVE_API)
            response.raise_for_status()
            data = response.json()

        listings = data.get("jobs", [])
        jobs = []
        for item in listings:
            try:
                job = Job(
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    location=item.get("candidate_required_location", "Remote"),
                    url=item.get("url", ""),
                    source=JobSource.REMOTIVE,
                    is_remote=True,
                    description=item.get("description", ""),
                )
                jobs.append(job)
            except Exception:
                continue

        logger.info("Remotive: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("Remotive scraper failed: %s", exc)
        return []
```

- [ ] **Step 2: Smoke-test manually**

```bash
python -c "
import asyncio
from worksearcher.config import Settings
from worksearcher.scrapers import remotive_scraper
jobs = asyncio.run(remotive_scraper.scrape(Settings()))
print(f'{len(jobs)} jobs. First: {jobs[0].title if jobs else \"none\"}')
"
```

Expected: prints a count > 0 and a job title.

- [ ] **Step 3: Commit**

```bash
git add worksearcher/scrapers/remotive_scraper.py
git commit -m "feat: add Remotive scraper via public JSON API"
```

---

## Task 9: jobspy Scraper (LinkedIn / Indeed / Glassdoor)

**Files:**
- Create: `worksearcher/scrapers/jobspy_scraper.py`

- [ ] **Step 1: Implement `worksearcher/scrapers/jobspy_scraper.py`**

```python
import asyncio
import logging

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

_SOURCE_MAP: dict[str, JobSource] = {
    "linkedin": JobSource.LINKEDIN,
    "indeed": JobSource.INDEED,
    "glassdoor": JobSource.GLASSDOOR,
}


async def scrape(config: Settings) -> list[Job]:
    try:
        from jobspy import scrape_jobs  # import here — jobspy is slow to import

        def _blocking_scrape() -> list[Job]:
            results = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term=" OR ".join(config.keywords_list[:5]),
                location="Remote",
                results_wanted=50,
                hours_old=24,
                is_remote=True,
            )
            jobs = []
            for _, row in results.iterrows():
                try:
                    source_str = str(row.get("site", "linkedin")).lower()
                    job = Job(
                        title=str(row.get("title", "")),
                        company=str(row.get("company", "")),
                        location=str(row.get("location", "Remote")),
                        url=str(row.get("job_url", "")),
                        source=_SOURCE_MAP.get(source_str, JobSource.LINKEDIN),
                        is_remote=True,
                        description=str(row.get("description", "") or ""),
                    )
                    jobs.append(job)
                except Exception:
                    continue
            return jobs

        # jobspy uses requests (sync) internally — run in thread pool
        jobs = await asyncio.to_thread(_blocking_scrape)
        logger.info("jobspy: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("jobspy scraper failed: %s", exc)
        return []
```

- [ ] **Step 2: Smoke-test manually**

```bash
python -c "
import asyncio
from worksearcher.config import Settings
from worksearcher.scrapers import jobspy_scraper
jobs = asyncio.run(jobspy_scraper.scrape(Settings()))
print(f'{len(jobs)} jobs. First: {jobs[0].title if jobs else \"none\"}')
"
```

Expected: prints a count > 0. Note: may be slow (10-30s) — LinkedIn rate limiting.

- [ ] **Step 3: Commit**

```bash
git add worksearcher/scrapers/jobspy_scraper.py
git commit -m "feat: add jobspy scraper for LinkedIn/Indeed/Glassdoor"
```

---

## Task 10: WhatsApp Notifier (Meta Cloud API)

**Files:**
- Create: `worksearcher/notifier/whatsapp.py`

- [ ] **Step 1: Implement `worksearcher/notifier/whatsapp.py`**

```python
import httpx
import logging

from worksearcher.config import Settings
from worksearcher.core.models import Job

logger = logging.getLogger(__name__)

_META_API_URL = "https://graph.facebook.com/v18.0/{phone_id}/messages"
_MAX_JOBS_PER_MESSAGE = 10


def _build_message(jobs: list[Job]) -> str:
    lines = ["*WorkSearcher — nuevas ofertas:*\n"]
    for job in jobs[:_MAX_JOBS_PER_MESSAGE]:
        lines.append(f"• *{job.title}* @ {job.company}")
        lines.append(f"  [{job.source}] {job.url}\n")
    if len(jobs) > _MAX_JOBS_PER_MESSAGE:
        lines.append(f"_...y {len(jobs) - _MAX_JOBS_PER_MESSAGE} más guardadas en DB_")
    return "\n".join(lines)


async def send_digest(jobs: list[Job], config: Settings) -> None:
    if not jobs:
        return

    url = _META_API_URL.format(phone_id=config.META_PHONE_NUMBER_ID)
    headers = {
        "Authorization": f"Bearer {config.META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": config.META_RECIPIENT_PHONE,
        "type": "text",
        "text": {"body": _build_message(jobs)},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()

    logger.info("WhatsApp digest sent: %d jobs", len(jobs))
```

- [ ] **Step 2: Verify message format without sending**

```bash
python -c "
from worksearcher.core.models import Job, JobSource
from worksearcher.notifier.whatsapp import _build_message
jobs = [
    Job(title='Python Dev', company='Acme', location='Remote', url='https://ex.com/1', source=JobSource.REMOTEOK, is_remote=True),
    Job(title='SOC Analyst', company='SecCo', location='Remote', url='https://ex.com/2', source=JobSource.REMOTIVE, is_remote=True),
]
print(_build_message(jobs))
"
```

Expected: formatted WhatsApp message with both jobs printed.

- [ ] **Step 3: Commit**

```bash
git add worksearcher/notifier/whatsapp.py
git commit -m "feat: add WhatsApp notifier via Meta Cloud API"
```

---

## Task 11: CLI Orchestrator (main.py)

**Files:**
- Create: `worksearcher/main.py`

- [ ] **Step 1: Implement `worksearcher/main.py`**

```python
import asyncio
import logging
from collections.abc import Callable, Coroutine

import click

from worksearcher.config import Settings
from worksearcher.core.deduplicator import deduplicate
from worksearcher.core.filters import filter_jobs
from worksearcher.core.models import Job
from worksearcher.notifier.whatsapp import send_digest
from worksearcher.scrapers import jobspy_scraper, remoteok_scraper, remotive_scraper
from worksearcher.storage.database import get_connection, get_seen_fingerprints, init_db, save_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

_SCRAPERS: list[Callable[[Settings], Coroutine[None, None, list[Job]]]] = [
    jobspy_scraper.scrape,
    remoteok_scraper.scrape,
    remotive_scraper.scrape,
]


async def _run_pipeline() -> None:
    config = Settings()
    logger.info("Pipeline started")

    # Scrape all platforms concurrently
    results = await asyncio.gather(
        *[scraper(config) for scraper in _SCRAPERS],
        return_exceptions=True,
    )
    all_jobs: list[Job] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("Scraper failed: %s", result)
        else:
            all_jobs.extend(result)
    logger.info("Scraped: %d total jobs", len(all_jobs))

    # Filter by keywords + remote
    relevant = filter_jobs(all_jobs, config.keywords_list)
    logger.info("Relevant: %d jobs after keyword filter", len(relevant))

    # Dedup + persist + notify
    conn = get_connection()
    try:
        init_db(conn)
        seen = get_seen_fingerprints(conn)
        new_jobs = deduplicate(relevant, seen)
        logger.info("New (unseen): %d jobs", len(new_jobs))

        if new_jobs:
            inserted = save_jobs(new_jobs, conn)
            logger.info("Inserted %d jobs into DB", inserted)
            await send_digest(new_jobs, config)
        else:
            logger.info("No new jobs — skipping notification")
    finally:
        conn.close()

    logger.info("Pipeline complete")


@click.group()
def cli() -> None:
    pass


@cli.command()
def run() -> None:
    """Run the full job search pipeline."""
    asyncio.run(_run_pipeline())


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Test `--help` works**

```bash
python -m worksearcher --help
```

Expected:
```
Usage: python -m worksearcher [OPTIONS] COMMAND [ARGS]...
Commands:
  run  Run the full job search pipeline.
```

- [ ] **Step 3: Create `worksearcher/__main__.py`**

```python
from worksearcher.main import cli

cli()
```

- [ ] **Step 4: Re-test `--help`**

```bash
python -m worksearcher --help
```

Expected: same output as Step 2.

- [ ] **Step 5: Run full pipeline end-to-end**

```bash
python -m worksearcher run
```

Expected output (example):
```
2026-06-18 10:00:01 worksearcher.main INFO Pipeline started
2026-06-18 10:00:05 worksearcher.scrapers.remoteok_scraper INFO RemoteOK: 312 jobs found
2026-06-18 10:00:06 worksearcher.scrapers.remotive_scraper INFO Remotive: 198 jobs found
2026-06-18 10:00:35 worksearcher.scrapers.jobspy_scraper INFO jobspy: 47 jobs found
2026-06-18 10:00:35 worksearcher.main INFO Scraped: 557 total jobs
2026-06-18 10:00:35 worksearcher.main INFO Relevant: 23 jobs after keyword filter
2026-06-18 10:00:35 worksearcher.main INFO New (unseen): 23 jobs
2026-06-18 10:00:35 worksearcher.main INFO Inserted 23 jobs into DB
2026-06-18 10:00:35 worksearcher.notifier.whatsapp INFO WhatsApp digest sent: 23 jobs
2026-06-18 10:00:35 worksearcher.main INFO Pipeline complete
```

You should receive a WhatsApp message on `META_RECIPIENT_PHONE`.

- [ ] **Step 6: Run pipeline a second time — verify no duplicate notification**

```bash
python -m worksearcher run
```

Expected: `New (unseen): 0 jobs` and `No new jobs — skipping notification`. No WhatsApp message received.

- [ ] **Step 7: Run full test suite**

```bash
pytest tests/ -v
```

Expected: `21 passed`

- [ ] **Step 8: Commit**

```bash
git add worksearcher/main.py worksearcher/__main__.py
git commit -m "feat: add CLI orchestrator with asyncio pipeline"
```

---

## Task 12: Crontab Setup Doc + Final Push

**Files:**
- Create: `crontab.example`

- [ ] **Step 1: Create `crontab.example`**

```bash
# WorkSearcher — run every 4 hours
# Install on VPS: crontab -e, paste this line
0 */4 * * * cd /path/to/worksearcher && /path/to/venv/bin/python -m worksearcher run >> /var/log/worksearcher.log 2>&1
```

- [ ] **Step 2: Final test suite run**

```bash
pytest tests/ -v --tb=short
```

Expected: `21 passed, 0 warnings`

- [ ] **Step 3: Push all commits to GitHub**

```bash
git push origin main
```

- [ ] **Step 4: Verify GitHub repo shows all commits**

Open: https://github.com/JuanP-a/WorkSearcher

Expected: all commits visible, no `.env` in the repo.
