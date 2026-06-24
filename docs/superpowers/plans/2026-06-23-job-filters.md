# Job Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four configurable post-scrape filters (date, blacklist, language, salary) to the WorkSearcher pipeline, plus populate the corresponding fields in four scrapers.

**Architecture:** Pure filter functions added to `worksearcher/core/filters.py`; `filter_jobs` signature extended with optional params; settings added to `config.py`; scrapers updated to populate `posted_at` and `min_salary_usd_monthly`; pipeline wired in `main.py`. Jobs without `posted_at` or salary always pass — no silent exclusion.

**Tech Stack:** Python 3.12, `pydantic` v2, `langdetect>=1.0.9` (new dep), `pytest`, `unittest.mock`

---

## File map

| Action | File | What changes |
|--------|------|-------------|
| Modify | `worksearcher/core/models.py` | Add `min_salary_usd_monthly: float \| None = None` to `Job` |
| Modify | `worksearcher/config.py` | Add 4 settings + 2 properties |
| Modify | `tests/conftest.py` | Add 4 new fields to `FakeSettings` |
| Modify | `worksearcher/core/filters.py` | Add 4 pure filter fns, extend `filter_jobs` |
| Modify | `worksearcher/scrapers/himalayas_scraper.py` | Map `pubDate` → `posted_at`, salary → `min_salary_usd_monthly` |
| Modify | `worksearcher/scrapers/remoteok_scraper.py` | Map `epoch` → `posted_at`, `salary_min` → `min_salary_usd_monthly` |
| Modify | `worksearcher/scrapers/hackernews_scraper.py` | Map `created_at_i` → `posted_at` |
| Modify | `worksearcher/scrapers/jobspy_scraper.py` | Map `date_posted` → `posted_at` |
| Modify | `worksearcher/main.py` | Pass new config fields to `filter_jobs` |
| Modify | `requirements.txt` | Add `langdetect>=1.0.9` |
| Modify | `tests/test_models.py` | Assert `min_salary_usd_monthly` field exists |
| Modify | `tests/test_filters.py` | Tests for 4 new filter functions |
| Modify | `tests/test_scrapers.py` | Tests for `posted_at` and salary in scrapers |

---

## Task 1: Add `min_salary_usd_monthly` to Job model

**Files:**
- Modify: `worksearcher/core/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
def test_job_has_min_salary_field():
    job = Job(
        title="Dev",
        company="Co",
        location="Remote",
        url="https://example.com/1",
        source=JobSource.REMOTEOK,
        is_remote=True,
    )
    assert job.min_salary_usd_monthly is None  # optional, defaults to None

def test_job_accepts_salary_value():
    job = Job(
        title="Dev",
        company="Co",
        location="Remote",
        url="https://example.com/1",
        source=JobSource.REMOTEOK,
        is_remote=True,
        min_salary_usd_monthly=1500.0,
    )
    assert job.min_salary_usd_monthly == 1500.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && pytest tests/test_models.py::test_job_has_min_salary_field -v
```

Expected: `FAILED` — `ValidationError: 1 validation error for Job`

- [ ] **Step 3: Add field to Job model**

In `worksearcher/core/models.py`, add after `posted_at`:

```python
class Job(BaseModel):
    title: str
    company: str
    location: str
    url: str
    source: JobSource
    is_remote: bool
    description: str = ""
    posted_at: datetime | None = None
    min_salary_usd_monthly: float | None = None

    @computed_field
    @property
    def fingerprint(self) -> str:
        raw = f"{self.title}{self.company}{self.url}".lower()
        return sha256(raw.encode()).hexdigest()
```

- [ ] **Step 4: Run full test suite**

```bash
source .venv/bin/activate && pytest -v
```

Expected: all tests PASS (new field is optional, existing tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add worksearcher/core/models.py tests/test_models.py
git commit -m "feat: add min_salary_usd_monthly field to Job model"
```

---

## Task 2: Add filter settings to config

**Files:**
- Modify: `worksearcher/config.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_filters.py` (at the top, after existing imports):

```python
def test_fake_settings_has_filter_fields(fake_settings):
    assert hasattr(fake_settings, "MAX_JOB_AGE_DAYS")
    assert hasattr(fake_settings, "blacklist_list")
    assert hasattr(fake_settings, "filter_languages_list")
    assert hasattr(fake_settings, "MIN_SALARY_USD_MONTHLY")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate && pytest tests/test_filters.py::test_fake_settings_has_filter_fields -v
```

Expected: `FAILED — AttributeError`

- [ ] **Step 3: Update config.py**

In `worksearcher/config.py`, add after `MAX_YEARS_EXPERIENCE`:

```python
MAX_JOB_AGE_DAYS: int = 30

BLACKLIST_KEYWORDS: str = (
    "security clearance,active clearance,top secret,ts/sci,dod clearance,"
    "secret clearance,public trust,us citizens only,"
    "must be authorized to work in the us,us work authorization,"
    "must be a us citizen,green card required,"
    "sales executive,account executive,must relocate,relocation required,"
    "staffing agency,recruiting firm"
)

MIN_SALARY_USD_MONTHLY: int | None = None

FILTER_LANGUAGES: str = "en,es"

@property
def blacklist_list(self) -> list[str]:
    return [k.strip().lower() for k in self.BLACKLIST_KEYWORDS.split(",") if k.strip()]

@property
def filter_languages_list(self) -> list[str]:
    return [lang.strip().lower() for lang in self.FILTER_LANGUAGES.split(",") if lang.strip()]
```

- [ ] **Step 4: Update FakeSettings in conftest.py**

Replace the existing `FakeSettings` in `tests/conftest.py`:

```python
class FakeSettings:
    """Implements the full Settings interface so tests don't diverge when new fields are added."""
    META_PHONE_NUMBER_ID = "123456789"
    META_ACCESS_TOKEN = "fake_token"
    META_RECIPIENT_PHONE = "521234567890"
    META_API_VERSION = "v21.0"
    keywords_list = ["python", "backend", "cybersecurity"]
    MAX_YEARS_EXPERIENCE = 3
    MAX_JOB_AGE_DAYS = 30
    blacklist_list: list[str] = []
    filter_languages_list: list[str] = ["en", "es"]
    MIN_SALARY_USD_MONTHLY = None
```

- [ ] **Step 5: Run full test suite**

```bash
source .venv/bin/activate && pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add worksearcher/config.py tests/conftest.py tests/test_filters.py
git commit -m "feat: add filter settings (age, blacklist, salary, language)"
```

---

## Task 3: Add four filter functions and extend `filter_jobs`

**Files:**
- Modify: `worksearcher/core/filters.py`
- Modify: `tests/test_filters.py`

### API verified facts
- `langdetect.detect(text)` returns ISO 639-1 code (e.g. `"en"`, `"es"`, `"fr"`)
- It raises `langdetect.lang_detect_exception.LangDetectException` on empty/undetectable text
- Non-deterministic by design → always mock in tests with `unittest.mock.patch`
- Mock target: `"worksearcher.core.filters.detect"` (patch the imported name)

- [ ] **Step 1: Write all failing tests**

Add to `tests/test_filters.py`:

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from worksearcher.core.filters import (
    has_minimum_salary,
    is_language_allowed,
    is_not_blacklisted,
    is_recent,
)


def _job_with_date(days_ago: int) -> Job:
    posted = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return Job(
        title="Python Developer",
        company="Co",
        location="Remote",
        url=f"https://example.com/{days_ago}",
        source=JobSource.REMOTEOK,
        is_remote=True,
        posted_at=posted,
    )


def _job_with_salary(salary: float | None) -> Job:
    return Job(
        title="Python Developer",
        company="Co",
        location="Remote",
        url="https://example.com/salary",
        source=JobSource.REMOTEOK,
        is_remote=True,
        min_salary_usd_monthly=salary,
    )


# --- is_recent ---

def test_recent_job_passes():
    assert is_recent(_job_with_date(days_ago=5), max_days=30) is True

def test_old_job_fails():
    assert is_recent(_job_with_date(days_ago=31), max_days=30) is False

def test_job_exactly_at_limit_passes():
    assert is_recent(_job_with_date(days_ago=30), max_days=30) is True

def test_job_without_posted_at_passes():
    job = _job("Python Developer")  # posted_at=None by default
    assert is_recent(job, max_days=30) is True


# --- is_not_blacklisted ---

def test_clean_job_passes_blacklist():
    assert is_not_blacklisted(_job("Python Developer"), ["security clearance"]) is True

def test_blacklisted_title_fails():
    assert is_not_blacklisted(_job("Security Clearance Required"), ["security clearance"]) is False

def test_blacklisted_description_fails():
    job = _job("Backend Engineer", description="Must have TS/SCI clearance")
    assert is_not_blacklisted(job, ["ts/sci"]) is False

def test_blacklist_is_case_insensitive():
    assert is_not_blacklisted(_job("TOP SECRET project"), ["top secret"]) is False

def test_empty_blacklist_always_passes():
    assert is_not_blacklisted(_job("Any Title"), []) is True


# --- is_language_allowed ---

def test_english_job_passes():
    with patch("worksearcher.core.filters.detect", return_value="en"):
        assert is_language_allowed(_job("Python Developer"), ["en", "es"]) is True

def test_spanish_job_passes():
    with patch("worksearcher.core.filters.detect", return_value="es"):
        assert is_language_allowed(_job("Desarrollador Python"), ["en", "es"]) is True

def test_french_job_fails():
    with patch("worksearcher.core.filters.detect", return_value="fr"):
        assert is_language_allowed(_job("Développeur Python"), ["en", "es"]) is False

def test_language_passes_on_detection_error():
    with patch("worksearcher.core.filters.detect", side_effect=Exception("undetectable")):
        assert is_language_allowed(_job("???"), ["en", "es"]) is True

def test_empty_text_passes_language_filter():
    job = _job("", description="")
    assert is_language_allowed(job, ["en", "es"]) is True


# --- has_minimum_salary ---

def test_salary_above_minimum_passes():
    assert has_minimum_salary(_job_with_salary(1500.0), min_usd_monthly=1200.0) is True

def test_salary_below_minimum_fails():
    assert has_minimum_salary(_job_with_salary(1000.0), min_usd_monthly=1200.0) is False

def test_salary_exactly_at_minimum_passes():
    assert has_minimum_salary(_job_with_salary(1200.0), min_usd_monthly=1200.0) is True

def test_no_salary_passes():
    assert has_minimum_salary(_job_with_salary(None), min_usd_monthly=1200.0) is True


# --- filter_jobs with all new params ---

def test_filter_jobs_applies_date_filter():
    jobs = [
        _job_with_date(days_ago=5),    # recent — keep
        _job_with_date(days_ago=40),   # old — exclude
        _job("Python Dev"),            # no date — keep
    ]
    result = filter_jobs(jobs, ["python"], max_job_age_days=30)
    assert len(result) == 2

def test_filter_jobs_applies_blacklist():
    jobs = [
        _job("Python Developer"),
        _job("Python Dev, US Citizens Only"),
    ]
    result = filter_jobs(jobs, ["python"], blacklist=["us citizens only"])
    assert len(result) == 1
    assert result[0].title == "Python Developer"

def test_filter_jobs_applies_language_filter():
    with patch("worksearcher.core.filters.detect", side_effect=["en", "fr"]):
        jobs = [_job("Python Developer"), _job("Développeur Python")]
        result = filter_jobs(jobs, ["python"], allowed_languages=["en", "es"])
    assert len(result) == 1

def test_filter_jobs_applies_salary_filter():
    jobs = [
        _job_with_salary(1500.0),   # above threshold — keep; title is "Python Developer"
        _job_with_salary(800.0),    # below threshold — exclude
        _job_with_salary(None),     # no salary — keep
    ]
    # all jobs need to match keywords too
    result = filter_jobs(jobs, ["python"], min_salary_usd_monthly=1200.0)
    assert len(result) == 2

def test_filter_jobs_none_params_skip_filters():
    jobs = [_job_with_date(days_ago=60), _job("Python Dev")]
    result = filter_jobs(
        jobs,
        ["python"],
        max_job_age_days=None,
        blacklist=None,
        allowed_languages=None,
        min_salary_usd_monthly=None,
    )
    assert len(result) == 2  # old job and normal job both pass
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && pytest tests/test_filters.py -k "is_recent or is_not_blacklisted or is_language or has_minimum or filter_jobs_applies" -v
```

Expected: `ImportError` — functions not yet defined.

- [ ] **Step 3: Install langdetect**

```bash
echo "langdetect>=1.0.9" >> "/Volumes/M2 Mac/proyectos/WorkSearcher/requirements.txt"
source .venv/bin/activate && pip install langdetect
source .venv/bin/activate && pip freeze > "/Volumes/M2 Mac/proyectos/WorkSearcher/requirements.lock"
```

- [ ] **Step 4: Implement the four filter functions**

Replace the full content of `worksearcher/core/filters.py`:

```python
import re
from datetime import datetime, timezone

from langdetect import detect

from worksearcher.core.models import Job

# Matches "3-5 years", "3–5 years", "3‒5 years", "3—5 years", "3−5 years"
# Covers: hyphen-minus, figure dash, en dash, em dash, minus sign (U+2212)
_RANGE_PATTERN = re.compile(r'(\d+)\s*[-‒–—−]\s*(\d+)\s*(?:years?|yrs?|años?)', re.IGNORECASE)

# Matches "5 years", "5+ years", "5 años de experiencia"
_YEARS_PATTERN = re.compile(r'(\d+)\+?\s*(?:years?|yrs?|años?)', re.IGNORECASE)

# Entry-level signals → treat as 0 years required
_ENTRY_LEVEL_PATTERN = re.compile(
    r'\b(?:entry[\s-]?level|junior|no experience required|recent graduate'
    r'|recién egresado|sin experiencia)\b',
    re.IGNORECASE,
)


def extract_min_years_required(text: str) -> int | None:
    """Return the minimum years of experience a job requires, or None if not mentioned."""
    if not text:
        return None
    if _ENTRY_LEVEL_PATTERN.search(text):
        return 0
    range_match = _RANGE_PATTERN.search(text)
    if range_match:
        return int(range_match.group(1))  # lower bound of range
    year_match = _YEARS_PATTERN.search(text)
    if year_match:
        return int(year_match.group(1))
    return None


def meets_experience_requirement(job: Job, max_years: int) -> bool:
    """Return True if job does not require more than max_years of experience.

    Jobs with no experience requirement mentioned are assumed accessible.
    """
    searchable = f"{job.title} {job.description or ''}"
    min_years = extract_min_years_required(searchable)
    if min_years is None:
        return True
    return min_years <= max_years


def is_relevant(job: Job, keywords: list[str]) -> bool:
    if not job.is_remote:
        return False
    searchable = f"{job.title} {job.description}".lower()
    return any(kw.lower() in searchable for kw in keywords)


def is_recent(job: Job, max_days: int) -> bool:
    """Return True if job was posted within max_days. Jobs without posted_at always pass."""
    if job.posted_at is None:
        return True
    delta = datetime.now(timezone.utc) - job.posted_at.astimezone(timezone.utc)
    return delta.days <= max_days


def is_not_blacklisted(job: Job, blacklist: list[str]) -> bool:
    """Return True if no blacklist keyword appears in title or description."""
    if not blacklist:
        return True
    searchable = f"{job.title} {job.description}".lower()
    return not any(kw in searchable for kw in blacklist)


def is_language_allowed(job: Job, allowed_langs: list[str]) -> bool:
    """Return True if job language is in allowed_langs.

    Uses langdetect on first 500 chars of title+description.
    Passes through if text is empty or detection fails (avoids silent exclusion).
    """
    text = f"{job.title} {job.description}".strip()[:500]
    if not text:
        return True
    try:
        lang = detect(text)
        return lang in allowed_langs
    except Exception:
        return True


def has_minimum_salary(job: Job, min_usd_monthly: float) -> bool:
    """Return True if job meets minimum salary. Jobs without salary always pass."""
    if job.min_salary_usd_monthly is None:
        return True
    return job.min_salary_usd_monthly >= min_usd_monthly


def filter_jobs(
    jobs: list[Job],
    keywords: list[str],
    max_years_experience: int | None = None,
    max_job_age_days: int | None = None,
    blacklist: list[str] | None = None,
    allowed_languages: list[str] | None = None,
    min_salary_usd_monthly: float | None = None,
) -> list[Job]:
    filtered = [j for j in jobs if is_relevant(j, keywords)]
    if max_years_experience is not None:
        filtered = [j for j in filtered if meets_experience_requirement(j, max_years_experience)]
    if max_job_age_days is not None:
        filtered = [j for j in filtered if is_recent(j, max_job_age_days)]
    if blacklist:
        filtered = [j for j in filtered if is_not_blacklisted(j, blacklist)]
    if allowed_languages:
        filtered = [j for j in filtered if is_language_allowed(j, allowed_languages)]
    if min_salary_usd_monthly is not None:
        filtered = [j for j in filtered if has_minimum_salary(j, min_salary_usd_monthly)]
    return filtered
```

- [ ] **Step 5: Run all filter tests**

```bash
source .venv/bin/activate && pytest tests/test_filters.py -v
```

Expected: all PASS.

- [ ] **Step 6: Run full suite**

```bash
source .venv/bin/activate && pytest -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add worksearcher/core/filters.py requirements.txt requirements.lock tests/test_filters.py
git commit -m "feat: add date/blacklist/language/salary filters to filter_jobs"
```

---

## Task 4: Populate `posted_at` in four scrapers

**Files:**
- Modify: `worksearcher/scrapers/himalayas_scraper.py`
- Modify: `worksearcher/scrapers/remoteok_scraper.py`
- Modify: `worksearcher/scrapers/hackernews_scraper.py`
- Modify: `worksearcher/scrapers/jobspy_scraper.py`
- Modify: `tests/test_scrapers.py`

### Verified API fields
- **Himalayas**: `pubDate` → Unix int (e.g. `1782237867`)
- **RemoteOK**: `epoch` → Unix int (e.g. `1782162385`)
- **HackerNews comments**: `created_at_i` → Unix int
- **jobspy DataFrame**: `date_posted` → `datetime.date` object or `None`/`NaN`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_scrapers.py` (after existing fixtures/imports):

```python
from datetime import datetime, timezone

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
            "pubDate": 1700000000,  # fixed Unix timestamp for testing
        }
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_populates_posted_at(fake_settings):
    respx.get(HIMALAYAS_API).mock(
        return_value=httpx.Response(200, json=HIMALAYAS_FIXTURE_WITH_DATE)
    )
    jobs = await himalayas_scrape(fake_settings)
    assert jobs[0].posted_at is not None
    assert jobs[0].posted_at == datetime.fromtimestamp(1700000000, tz=timezone.utc)


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
    assert jobs[0].posted_at == datetime.fromtimestamp(1700000000, tz=timezone.utc)


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
    respx.get(HN_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=HN_SEARCH_FIXTURE)
    )
    respx.get(HN_ITEMS_URL).mock(
        return_value=httpx.Response(200, json=HN_ITEMS_FIXTURE_WITH_DATE)
    )
    jobs = await hn_scrape(fake_settings)
    assert jobs[0].posted_at is not None
    assert jobs[0].posted_at == datetime.fromtimestamp(1700000000, tz=timezone.utc)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && pytest tests/test_scrapers.py -k "posted_at" -v
```

Expected: `FAILED — AssertionError: assert None is not None`

- [ ] **Step 3: Update himalayas_scraper.py**

Replace full file content of `worksearcher/scrapers/himalayas_scraper.py`:

```python
import logging
from datetime import datetime, timezone

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
                restrictions = item.get("locationRestrictions", [])
                location = restrictions[0] if restrictions else "Remote"
                url = item.get("applicationLink", "") or item.get("guid", "")

                pub_date = item.get("pubDate")
                posted_at = (
                    datetime.fromtimestamp(pub_date, tz=timezone.utc) if pub_date else None
                )

                currency = item.get("currency", "") or ""
                min_salary_raw = item.get("minSalary")
                salary_period = item.get("salaryPeriod", "") or ""
                min_salary_usd_monthly = None
                if currency == "USD" and min_salary_raw is not None:
                    if salary_period == "annual":
                        min_salary_usd_monthly = float(min_salary_raw) / 12
                    elif salary_period == "monthly":
                        min_salary_usd_monthly = float(min_salary_raw)

                job = Job(
                    title=item.get("title", ""),
                    company=item.get("companyName", ""),
                    location=location,
                    url=url,
                    source=JobSource.HIMALAYAS,
                    is_remote=True,
                    description=item.get("description", ""),
                    posted_at=posted_at,
                    min_salary_usd_monthly=min_salary_usd_monthly,
                )
                jobs.append(job)
            except Exception as exc:
                logger.warning("Himalayas: skipping malformed job %s: %s", item.get("title", "?"), exc)
                continue

        logger.info("Himalayas: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("Himalayas scraper failed: %s", exc)
        return []
```

- [ ] **Step 4: Update remoteok_scraper.py**

Replace full file content of `worksearcher/scrapers/remoteok_scraper.py`:

```python
import logging
from datetime import datetime, timezone

import httpx

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
                epoch = item.get("epoch")
                posted_at = (
                    datetime.fromtimestamp(int(epoch), tz=timezone.utc) if epoch else None
                )

                salary_min = item.get("salary_min")
                min_salary_usd_monthly = (
                    float(salary_min) if salary_min and int(salary_min) > 0 else None
                )

                job = Job(
                    title=item.get("position", ""),
                    company=item.get("company", ""),
                    location="Remote",
                    url=f"https://remoteok.com/remote-jobs/{item.get('slug', '')}",
                    source=JobSource.REMOTEOK,
                    is_remote=True,
                    description=item.get("description", ""),
                    posted_at=posted_at,
                    min_salary_usd_monthly=min_salary_usd_monthly,
                )
                jobs.append(job)
            except Exception as exc:
                logger.warning("RemoteOK: skipping malformed job %s: %s", item.get("slug", "?"), exc)
                continue

        logger.info("RemoteOK: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("RemoteOK scraper failed: %s", exc)
        return []
```

- [ ] **Step 5: Update hackernews_scraper.py**

In `worksearcher/scrapers/hackernews_scraper.py`, add `from datetime import datetime, timezone` import and map `created_at_i` in the job creation loop.

Replace full file content:

```python
import logging
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
HN_ITEMS_URL = "https://hn.algolia.com/api/v1/items/{thread_id}"


def _parse_hn_comment(text: str) -> tuple[str, str]:
    """Return (title, company) from HN job comment HTML.

    Pipe-delimited format: Company | Role | Location | REMOTE | ...
    Falls back to (full first line, "") if no pipe found.
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

            items_resp = await client.get(HN_ITEMS_URL.format(thread_id=thread_id))
            items_resp.raise_for_status()
            thread = items_resp.json()

        jobs = []
        for child in thread.get("children", []):
            text = child.get("text")
            if not text:
                continue
            try:
                title, company = _parse_hn_comment(text)
                if not title:
                    continue
                job_id = child.get("id", "")
                created_at_i = child.get("created_at_i")
                posted_at = (
                    datetime.fromtimestamp(created_at_i, tz=timezone.utc)
                    if created_at_i
                    else None
                )
                job = Job(
                    title=title,
                    company=company,
                    location="Remote",
                    url=f"https://news.ycombinator.com/item?id={job_id}",
                    source=JobSource.HACKERNEWS,
                    is_remote=True,
                    description=BeautifulSoup(text, "html.parser").get_text(),
                    posted_at=posted_at,
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

- [ ] **Step 6: Update jobspy_scraper.py**

Replace full file content of `worksearcher/scrapers/jobspy_scraper.py`:

```python
import asyncio
import logging
from datetime import datetime, timezone

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
                search_term=" OR ".join(config.jobspy_terms_list),
                location="Remote",
                results_wanted=50,
                hours_old=24,
                is_remote=True,
            )
            jobs = []
            for _, row in results.iterrows():
                try:
                    source_str = str(row.get("site", "")).lower()
                    source = _SOURCE_MAP.get(source_str)
                    if source is None:
                        logger.warning("jobspy: unknown source %r — skipping row", source_str)
                        continue

                    date_posted = row.get("date_posted")
                    posted_at = None
                    try:
                        if date_posted is not None:
                            posted_at = datetime(
                                date_posted.year,
                                date_posted.month,
                                date_posted.day,
                                tzinfo=timezone.utc,
                            )
                    except Exception:
                        posted_at = None

                    job = Job(
                        title=str(row.get("title", "")),
                        company=str(row.get("company", "")),
                        location=str(row.get("location", "Remote")),
                        url=str(row.get("job_url", "")),
                        source=source,
                        is_remote=True,
                        description=str(row.get("description", "") or ""),
                        posted_at=posted_at,
                    )
                    jobs.append(job)
                except Exception as exc:
                    logger.warning("jobspy: skipping malformed row: %s", exc)
                    continue
            return jobs

        jobs = await asyncio.to_thread(_blocking_scrape)
        logger.info("jobspy: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("jobspy scraper failed: %s", exc)
        return []
```

- [ ] **Step 7: Run failing tests**

```bash
source .venv/bin/activate && pytest tests/test_scrapers.py -k "posted_at" -v
```

Expected: all 3 `posted_at` tests PASS.

- [ ] **Step 8: Run full suite**

```bash
source .venv/bin/activate && pytest -v
```

Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add worksearcher/scrapers/himalayas_scraper.py \
        worksearcher/scrapers/remoteok_scraper.py \
        worksearcher/scrapers/hackernews_scraper.py \
        worksearcher/scrapers/jobspy_scraper.py \
        tests/test_scrapers.py
git commit -m "feat: populate posted_at in Himalayas, RemoteOK, HackerNews, jobspy scrapers"
```

---

## Task 5: Populate `min_salary_usd_monthly` in Himalayas and RemoteOK

**Files:**
- Modify: `tests/test_scrapers.py` (only — scrapers already updated in Task 4)

Note: The scraper implementations for salary were already included in Task 4's scraper rewrites. This task adds the tests to verify salary behaviour.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_scrapers.py`:

```python
# --- Himalayas: salary ---

HIMALAYAS_FIXTURE_USD_MONTHLY = {
    "jobs": [{
        "title": "Backend Engineer", "companyName": "Co",
        "applicationLink": "https://himalayas.app/co/backend", "guid": "https://himalayas.app/co/backend",
        "description": "Python", "locationRestrictions": [],
        "pubDate": None, "currency": "USD", "minSalary": 2000, "salaryPeriod": "monthly",
    }]
}

HIMALAYAS_FIXTURE_USD_ANNUAL = {
    "jobs": [{
        "title": "Backend Engineer", "companyName": "Co",
        "applicationLink": "https://himalayas.app/co/backend", "guid": "https://himalayas.app/co/backend",
        "description": "Python", "locationRestrictions": [],
        "pubDate": None, "currency": "USD", "minSalary": 24000, "salaryPeriod": "annual",
    }]
}

HIMALAYAS_FIXTURE_EUR = {
    "jobs": [{
        "title": "Backend Engineer", "companyName": "Co",
        "applicationLink": "https://himalayas.app/co/backend", "guid": "https://himalayas.app/co/backend",
        "description": "Python", "locationRestrictions": [],
        "pubDate": None, "currency": "EUR", "minSalary": 2000, "salaryPeriod": "monthly",
    }]
}


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_salary_usd_monthly(fake_settings):
    respx.get(HIMALAYAS_API).mock(return_value=httpx.Response(200, json=HIMALAYAS_FIXTURE_USD_MONTHLY))
    jobs = await himalayas_scrape(fake_settings)
    assert jobs[0].min_salary_usd_monthly == 2000.0


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_salary_usd_annual_converted(fake_settings):
    respx.get(HIMALAYAS_API).mock(return_value=httpx.Response(200, json=HIMALAYAS_FIXTURE_USD_ANNUAL))
    jobs = await himalayas_scrape(fake_settings)
    assert jobs[0].min_salary_usd_monthly == 2000.0  # 24000 / 12


@pytest.mark.asyncio
@respx.mock
async def test_himalayas_salary_non_usd_ignored(fake_settings):
    respx.get(HIMALAYAS_API).mock(return_value=httpx.Response(200, json=HIMALAYAS_FIXTURE_EUR))
    jobs = await himalayas_scrape(fake_settings)
    assert jobs[0].min_salary_usd_monthly is None


# --- RemoteOK: salary ---

REMOTEOK_FIXTURE_WITH_SALARY = [
    {"legal": "metadata"},
    {
        "position": "Python Developer", "company": "Startup",
        "slug": "python-dev-123", "description": "Python skills",
        "epoch": None, "salary_min": 1500, "salary_max": 2500,
    },
]

REMOTEOK_FIXTURE_ZERO_SALARY = [
    {"legal": "metadata"},
    {
        "position": "Python Developer", "company": "Startup",
        "slug": "python-dev-456", "description": "Python skills",
        "epoch": None, "salary_min": 0, "salary_max": 0,
    },
]


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_salary_populated(fake_settings):
    respx.get("https://remoteok.com/api").mock(
        return_value=httpx.Response(200, json=REMOTEOK_FIXTURE_WITH_SALARY)
    )
    jobs = await remoteok_scrape(fake_settings)
    assert jobs[0].min_salary_usd_monthly == 1500.0


@pytest.mark.asyncio
@respx.mock
async def test_remoteok_zero_salary_treated_as_none(fake_settings):
    respx.get("https://remoteok.com/api").mock(
        return_value=httpx.Response(200, json=REMOTEOK_FIXTURE_ZERO_SALARY)
    )
    jobs = await remoteok_scrape(fake_settings)
    assert jobs[0].min_salary_usd_monthly is None
```

- [ ] **Step 2: Run tests**

```bash
source .venv/bin/activate && pytest tests/test_scrapers.py -k "salary" -v
```

Expected: all PASS (implementations already done in Task 4).

- [ ] **Step 3: Run full suite**

```bash
source .venv/bin/activate && pytest -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_scrapers.py
git commit -m "feat: populate min_salary_usd_monthly in Himalayas and RemoteOK scrapers"
```

---

## Task 6: Wire filters into pipeline

**Files:**
- Modify: `worksearcher/main.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_pipeline.py`:

```python
def test_filter_jobs_called_with_all_config_params():
    from unittest.mock import MagicMock, patch
    from worksearcher.main import _run_pipeline

    mock_config = MagicMock()
    mock_config.keywords_list = ["python"]
    mock_config.MAX_YEARS_EXPERIENCE = 3
    mock_config.MAX_JOB_AGE_DAYS = 30
    mock_config.blacklist_list = ["us citizens only"]
    mock_config.filter_languages_list = ["en", "es"]
    mock_config.MIN_SALARY_USD_MONTHLY = None

    with patch("worksearcher.main.filter_jobs") as mock_filter:
        mock_filter.return_value = []
        with patch("worksearcher.main._SCRAPERS", []):
            with patch("worksearcher.main.get_connection"), \
                 patch("worksearcher.main.init_db"), \
                 patch("worksearcher.main.get_unnotified_jobs", return_value=[]), \
                 patch("worksearcher.main.get_seen_fingerprints", return_value=set()):
                import asyncio
                asyncio.run(_run_pipeline(mock_config))

    mock_filter.assert_called_once_with(
        [],
        mock_config.keywords_list,
        max_years_experience=mock_config.MAX_YEARS_EXPERIENCE,
        max_job_age_days=mock_config.MAX_JOB_AGE_DAYS,
        blacklist=mock_config.blacklist_list,
        allowed_languages=mock_config.filter_languages_list,
        min_salary_usd_monthly=mock_config.MIN_SALARY_USD_MONTHLY,
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate && pytest tests/test_pipeline.py::test_filter_jobs_called_with_all_config_params -v
```

Expected: `FAILED — AssertionError: filter_jobs called with wrong args`

- [ ] **Step 3: Update main.py filter_jobs call**

In `worksearcher/main.py`, find this line (around line 72):

```python
relevant = filter_jobs(all_jobs, config.keywords_list, config.MAX_YEARS_EXPERIENCE)
```

Replace with:

```python
relevant = filter_jobs(
    all_jobs,
    config.keywords_list,
    max_years_experience=config.MAX_YEARS_EXPERIENCE,
    max_job_age_days=config.MAX_JOB_AGE_DAYS,
    blacklist=config.blacklist_list,
    allowed_languages=config.filter_languages_list,
    min_salary_usd_monthly=config.MIN_SALARY_USD_MONTHLY,
)
```

Also update the log line below it (around line 73):

```python
logger.info(
    "Relevant: %d jobs after filters (keywords + experience ≤%dy + date/blacklist/lang/salary)",
    len(relevant),
    config.MAX_YEARS_EXPERIENCE,
)
```

- [ ] **Step 4: Run all tests**

```bash
source .venv/bin/activate && pytest -v
```

Expected: all PASS.

- [ ] **Step 5: Lint**

```bash
source .venv/bin/activate && uvx ruff check worksearcher/ tests/
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add worksearcher/main.py tests/test_pipeline.py
git commit -m "feat: wire all filters (date/blacklist/language/salary) into pipeline"
```

---

## Self-review

### Spec coverage

| Spec requirement | Task |
|-----------------|------|
| `posted_at` populated: Himalayas, RemoteOK, HN, jobspy | T4 |
| `min_salary_usd_monthly` in Job model | T1 |
| `min_salary_usd_monthly` populated: Himalayas (USD only), RemoteOK | T4 + T5 |
| `is_recent` — 30 days, None passes | T3 |
| `is_not_blacklisted` — case-insensitive substring | T3 |
| `is_language_allowed` — langdetect, fail=pass | T3 |
| `has_minimum_salary` — None passes | T3 |
| `filter_jobs` extended with 4 new optional params | T3 |
| Settings: `MAX_JOB_AGE_DAYS`, `BLACKLIST_KEYWORDS`, `MIN_SALARY_USD_MONTHLY`, `FILTER_LANGUAGES` | T2 |
| Properties: `blacklist_list`, `filter_languages_list` | T2 |
| `FakeSettings` updated | T2 |
| Pipeline wired | T6 |
| `langdetect` installed | T3 |

All requirements covered. ✅

### Placeholder scan

No TBDs, no "similar to Task N", no missing code blocks. ✅

### Type consistency

- `is_recent(job: Job, max_days: int) -> bool` — used consistently in T3 and T6
- `is_not_blacklisted(job: Job, blacklist: list[str]) -> bool` — consistent
- `is_language_allowed(job: Job, allowed_langs: list[str]) -> bool` — consistent
- `has_minimum_salary(job: Job, min_usd_monthly: float) -> bool` — consistent
- `filter_jobs(..., allowed_languages: list[str] | None)` matches `is_language_allowed` param name — ✅
- `min_salary_usd_monthly: float | None` in Job model matches `has_minimum_salary` signature — ✅
