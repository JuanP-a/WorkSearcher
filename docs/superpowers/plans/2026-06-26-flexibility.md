# Flexibility: Full .env Configuration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every user-tunable hardcoded value into `Settings` so the entire pipeline is configurable via `.env` without touching code.

**Architecture:** Each new field added to `Settings` gets a property for list-parsing if needed. Scrapers receive `config` already — they just start reading from it. `_SCRAPERS` list in `main.py` becomes `_ALL_SCRAPERS` dict filtered by `config.enabled_scrapers_list`. `MAX_JOBS_PER_MESSAGE` moves from a whatsapp constant into `Settings`.

**Tech Stack:** Python 3.12, pydantic-settings v2, pytest, respx (for HTTP mocking)

---

## File Map

| File | Change |
|------|--------|
| `worksearcher/config.py` | +11 new fields + validators + properties |
| `worksearcher/main.py` | `_SCRAPERS` list → `_ALL_SCRAPERS` dict; dynamic selection; timeout from config; remove `MAX_JOBS_PER_MESSAGE` import |
| `worksearcher/scrapers/bumeran_scraper.py` | Replace `_SEARCH_TERMS` constant with `config.bumeran_search_terms_list` |
| `worksearcher/scrapers/computrabajo_scraper.py` | Replace `keywords_list[:5]` with `config.computrabajo_search_terms_list` |
| `worksearcher/scrapers/jobspy_scraper.py` | Replace 3 hardcoded params with config |
| `worksearcher/scrapers/remoteok_scraper.py` | `timeout=30` → `config.HTTP_TIMEOUT_SECONDS` |
| `worksearcher/scrapers/remotive_scraper.py` | same |
| `worksearcher/scrapers/wwr_scraper.py` | same |
| `worksearcher/scrapers/cybersecjobs_scraper.py` | same |
| `worksearcher/scrapers/himalayas_scraper.py` | timeout + limit from config |
| `worksearcher/scrapers/hackernews_scraper.py` | `timeout=30` → `config.HTTP_TIMEOUT_SECONDS` |
| `worksearcher/notifier/whatsapp.py` | `_build_message` takes `max_jobs` param; remove module constant |
| `tests/conftest.py` | Add all new fields to `FakeSettings` |
| `tests/test_pipeline.py` | Update `_SCRAPERS` → `_ALL_SCRAPERS` monkeypatches; `MAX_JOBS_PER_MESSAGE` → `fake_settings.MAX_JOBS_PER_MESSAGE` |
| `tests/test_scrapers.py` | Add tests for new config params per scraper |
| `.env.example` | Document all new variables |

---

### Task 1: ENABLED_SCRAPERS — dynamic scraper selection

**Files:**
- Modify: `worksearcher/config.py`
- Modify: `worksearcher/main.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_pipeline.py`:

```python
def test_all_scrapers_dict_includes_all_platforms():
    from worksearcher.main import _ALL_SCRAPERS
    expected = {"jobspy", "remoteok", "remotive", "wwr", "cybersecjobs",
                "computrabajo", "bumeran", "himalayas", "hackernews"}
    assert set(_ALL_SCRAPERS.keys()) == expected


def test_enabled_scrapers_defaults_to_all():
    from worksearcher.config import Settings
    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert set(s.enabled_scrapers_list) == {
        "jobspy", "remoteok", "remotive", "wwr", "cybersecjobs",
        "computrabajo", "bumeran", "himalayas", "hackernews",
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
```

Also add `import pytest` at the top of `test_pipeline.py` if not already present.

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/test_pipeline.py::test_all_scrapers_dict_includes_all_platforms tests/test_pipeline.py::test_enabled_scrapers_defaults_to_all tests/test_pipeline.py::test_enabled_scrapers_rejects_unknown_name -v
```

Expected: `FAILED` (AttributeError: module has no attribute `_ALL_SCRAPERS` / `enabled_scrapers_list`)

- [ ] **Step 3: Add `ENABLED_SCRAPERS` to config.py**

Add after the `JOBSPY_SEARCH_TERMS` field and its validator:

```python
    _KNOWN_SCRAPERS: ClassVar[frozenset[str]] = frozenset({
        "jobspy", "remoteok", "remotive", "wwr", "cybersecjobs",
        "computrabajo", "bumeran", "himalayas", "hackernews",
    })

    ENABLED_SCRAPERS: str = (
        "jobspy,remoteok,remotive,wwr,cybersecjobs,computrabajo,bumeran,himalayas,hackernews"
    )
```

Add import at top of config.py:
```python
from typing import ClassVar
```

Add validator after `jobspy_terms_max_five`:

```python
    @field_validator("ENABLED_SCRAPERS")
    @classmethod
    def validate_scraper_names(cls, v: str) -> str:
        names = {n.strip() for n in v.split(",") if n.strip()}
        unknown = names - cls._KNOWN_SCRAPERS
        if unknown:
            raise ValueError(f"Unknown scrapers: {unknown}. Known: {cls._KNOWN_SCRAPERS}")
        return v
```

Add property:

```python
    @property
    def enabled_scrapers_list(self) -> list[str]:
        return [n.strip() for n in self.ENABLED_SCRAPERS.split(",") if n.strip()]
```

- [ ] **Step 4: Update main.py — rename to dict, dynamic selection**

Replace the `_SCRAPERS` list and its usage:

```python
# OLD — delete this block:
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

# NEW — replace with:
_ALL_SCRAPERS: dict[str, Callable[[Settings], Coroutine[None, None, list[Job]]]] = {
    "jobspy": jobspy_scraper.scrape,
    "remoteok": remoteok_scraper.scrape,
    "remotive": remotive_scraper.scrape,
    "wwr": wwr_scraper.scrape,
    "cybersecjobs": cybersecjobs_scraper.scrape,
    "computrabajo": computrabajo_scraper.scrape,
    "bumeran": bumeran_scraper.scrape,
    "himalayas": himalayas_scraper.scrape,
    "hackernews": hackernews_scraper.scrape,
}
```

In `_run_pipeline`, replace the line that references `_SCRAPERS`:

```python
# OLD:
results = await asyncio.gather(
    *[_scrape_with_timeout(scraper) for scraper in _SCRAPERS],
    return_exceptions=True,
)

# NEW:
active_scrapers = [_ALL_SCRAPERS[name] for name in config.enabled_scrapers_list]
results = await asyncio.gather(
    *[_scrape_with_timeout(scraper) for scraper in active_scrapers],
    return_exceptions=True,
)
```

- [ ] **Step 5: Update FakeSettings in conftest.py**

```python
class FakeSettings:
    META_PHONE_NUMBER_ID = "123456789"
    META_ACCESS_TOKEN = "fake_token"
    META_RECIPIENT_PHONE = "521234567890"
    META_API_VERSION = "v21.0"
    keywords_list = ["python", "backend", "cybersecurity"]
    jobspy_terms_list = ["python", "cybersecurity"]
    MAX_YEARS_EXPERIENCE = 3
    MAX_JOB_AGE_DAYS = 30
    blacklist_list: list = []
    filter_languages_list: list = ["en", "es"]
    MIN_SALARY_USD_MONTHLY = None
    DB_PATH = "worksearcher.db"
    enabled_scrapers_list = [
        "jobspy", "remoteok", "remotive", "wwr", "cybersecjobs",
        "computrabajo", "bumeran", "himalayas", "hackernews",
    ]
```

- [ ] **Step 6: Update test_pipeline.py monkeypatches**

All 6 occurrences of `monkeypatch.setattr("worksearcher.main._SCRAPERS", ...)` must change to patch `_ALL_SCRAPERS` and set `enabled_scrapers_list`:

```python
# OLD pattern (used in all async tests):
monkeypatch.setattr("worksearcher.main._SCRAPERS", [_make_fake_scraper(jobs)])

# NEW pattern:
monkeypatch.setattr("worksearcher.main._ALL_SCRAPERS", {"fake": _make_fake_scraper(jobs)})
fake_settings.enabled_scrapers_list = ["fake"]
```

Apply this change to all 6 tests:
- `test_pipeline_saves_new_jobs`
- `test_pipeline_skips_notification_when_no_new_jobs`
- `test_pipeline_tolerates_scraper_failure` (two scrapers → use `{"good": ..., "fail": ...}` and `enabled_scrapers_list = ["fail", "good"]`)
- `test_pipeline_filters_irrelevant_jobs`
- `test_pipeline_logs_warning_when_notification_fails`
- `test_pipeline_marks_only_sent_jobs_as_notified`
- `test_pipeline_passes_all_filter_params_from_config`

Also update `test_scrapers_list_includes_new_platforms`:

```python
def test_all_scrapers_dict_includes_new_platforms():
    from worksearcher.main import _ALL_SCRAPERS
    assert "himalayas" in _ALL_SCRAPERS
    assert "hackernews" in _ALL_SCRAPERS
```

- [ ] **Step 7: Run full test suite**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/ -v
```

Expected: all passing

- [ ] **Step 8: Commit**

```bash
git add worksearcher/config.py worksearcher/main.py tests/conftest.py tests/test_pipeline.py
git commit -F - <<'EOF'
feat: add ENABLED_SCRAPERS — select active scrapers via .env

_SCRAPERS list → _ALL_SCRAPERS dict; _run_pipeline filters by
config.enabled_scrapers_list. Defaults to all 9 scrapers.
Validator rejects unknown names.
EOF
```

---

### Task 2: LatAm scraper search terms (Bumeran + Computrabajo)

**Files:**
- Modify: `worksearcher/config.py`
- Modify: `worksearcher/scrapers/bumeran_scraper.py`
- Modify: `worksearcher/scrapers/computrabajo_scraper.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_scrapers.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_scrapers.py`:

```python
# --- Bumeran: uses config search terms ---

def test_bumeran_uses_config_search_terms():
    """_SEARCH_TERMS constant must not exist; bumeran reads from config."""
    import worksearcher.scrapers.bumeran_scraper as mod
    assert not hasattr(mod, "_SEARCH_TERMS"), (
        "_SEARCH_TERMS is hardcoded — should come from config.bumeran_search_terms_list"
    )


# --- Computrabajo: uses config search terms ---

def test_computrabajo_uses_config_search_terms():
    """Computrabajo must not slice keywords_list; it uses computrabajo_search_terms_list."""
    import inspect
    import worksearcher.scrapers.computrabajo_scraper as mod
    source = inspect.getsource(mod._blocking_scrape)
    assert "keywords_list[:5]" not in source, (
        "keywords_list[:5] is hardcoded — use config.computrabajo_search_terms_list"
    )
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/test_scrapers.py::test_bumeran_uses_config_search_terms tests/test_scrapers.py::test_computrabajo_uses_config_search_terms -v
```

Expected: `FAILED`

- [ ] **Step 3: Add fields to config.py**

Add after `ENABLED_SCRAPERS` field:

```python
    # Spanish search terms for LatAm scrapers (Bumeran, Computrabajo)
    BUMERAN_SEARCH_TERMS: str = (
        "desarrollador,programador,backend,ciberseguridad,seguridad informatica"
    )
    COMPUTRABAJO_SEARCH_TERMS: str = (
        "desarrollador,programador,backend,ciberseguridad,seguridad informatica"
    )
```

Add properties:

```python
    @property
    def bumeran_search_terms_list(self) -> list[str]:
        return [t.strip() for t in self.BUMERAN_SEARCH_TERMS.split(",") if t.strip()]

    @property
    def computrabajo_search_terms_list(self) -> list[str]:
        return [t.strip() for t in self.COMPUTRABAJO_SEARCH_TERMS.split(",") if t.strip()]
```

- [ ] **Step 4: Update bumeran_scraper.py**

Remove the `_SEARCH_TERMS` constant (lines 16-22) and update the loop:

```python
# DELETE this block entirely:
_SEARCH_TERMS = [
    "desarrollador",
    "programador",
    "backend",
    "ciberseguridad",
    "seguridad informatica",
]
```

In `_blocking_scrape`, change:

```python
# OLD:
for term in _SEARCH_TERMS:

# NEW:
for term in config.bumeran_search_terms_list:
```

- [ ] **Step 5: Update computrabajo_scraper.py**

In `_blocking_scrape`, change:

```python
# OLD:
for keyword in config.keywords_list[:5]:

# NEW:
for keyword in config.computrabajo_search_terms_list:
```

- [ ] **Step 6: Add to FakeSettings in conftest.py**

```python
    bumeran_search_terms_list = ["desarrollador", "programador"]
    computrabajo_search_terms_list = ["desarrollador", "programador"]
```

- [ ] **Step 7: Run full test suite**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/ -v
```

Expected: all passing

- [ ] **Step 8: Commit**

```bash
git add worksearcher/config.py worksearcher/scrapers/bumeran_scraper.py worksearcher/scrapers/computrabajo_scraper.py tests/conftest.py tests/test_scrapers.py
git commit -F - <<'EOF'
feat: add BUMERAN_SEARCH_TERMS + COMPUTRABAJO_SEARCH_TERMS config fields

Both LatAm scrapers now read search terms from config instead of
hardcoded Spanish IT terms / keywords_list[:5] slice.
EOF
```

---

### Task 3: Jobspy parameters (sites, results, age, location)

**Files:**
- Modify: `worksearcher/config.py`
- Modify: `worksearcher/scrapers/jobspy_scraper.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_scrapers.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_scrapers.py`:

```python
# --- Jobspy: config params forwarded ---

def test_jobspy_config_fields_exist():
    """Settings must expose all jobspy tuning params."""
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
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/test_scrapers.py::test_jobspy_config_fields_exist -v
```

Expected: `FAILED` (AttributeError)

- [ ] **Step 3: Add fields to config.py**

Add after `COMPUTRABAJO_SEARCH_TERMS`:

```python
    # jobspy (LinkedIn / Indeed / Glassdoor) tuning
    JOBSPY_SITES: str = "linkedin,indeed,glassdoor"
    JOBSPY_RESULTS_WANTED: int = 50
    JOBSPY_HOURS_OLD: int = 24
    SEARCH_LOCATION: str = "Remote"
```

Add property:

```python
    @property
    def jobspy_sites_list(self) -> list[str]:
        return [s.strip() for s in self.JOBSPY_SITES.split(",") if s.strip()]
```

- [ ] **Step 4: Update jobspy_scraper.py**

```python
# OLD:
results = scrape_jobs(
    site_name=["linkedin", "indeed", "glassdoor"],
    search_term=" OR ".join(config.jobspy_terms_list),
    location="Remote",
    results_wanted=50,
    hours_old=24,
    is_remote=True,
)

# NEW:
results = scrape_jobs(
    site_name=config.jobspy_sites_list,
    search_term=" OR ".join(config.jobspy_terms_list),
    location=config.SEARCH_LOCATION,
    results_wanted=config.JOBSPY_RESULTS_WANTED,
    hours_old=config.JOBSPY_HOURS_OLD,
    is_remote=True,
)
```

- [ ] **Step 5: Add to FakeSettings in conftest.py**

```python
    jobspy_sites_list = ["linkedin", "indeed", "glassdoor"]
    JOBSPY_RESULTS_WANTED = 50
    JOBSPY_HOURS_OLD = 24
    SEARCH_LOCATION = "Remote"
```

- [ ] **Step 6: Run full test suite**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/ -v
```

Expected: all passing

- [ ] **Step 7: Commit**

```bash
git add worksearcher/config.py worksearcher/scrapers/jobspy_scraper.py tests/conftest.py tests/test_scrapers.py
git commit -F - <<'EOF'
feat: add JOBSPY_SITES, JOBSPY_RESULTS_WANTED, JOBSPY_HOURS_OLD, SEARCH_LOCATION config fields

jobspy scraper now reads all 4 params from config instead of
hardcoded values. Enables targeting different locations/volumes.
EOF
```

---

### Task 4: HTTP_TIMEOUT_SECONDS — unified timeout for all HTTP scrapers

**Files:**
- Modify: `worksearcher/config.py`
- Modify: `worksearcher/scrapers/remoteok_scraper.py`
- Modify: `worksearcher/scrapers/remotive_scraper.py`
- Modify: `worksearcher/scrapers/wwr_scraper.py`
- Modify: `worksearcher/scrapers/cybersecjobs_scraper.py`
- Modify: `worksearcher/scrapers/himalayas_scraper.py`
- Modify: `worksearcher/scrapers/hackernews_scraper.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_scrapers.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_scrapers.py`:

```python
def test_http_timeout_config_field_exists():
    from worksearcher.config import Settings
    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert s.HTTP_TIMEOUT_SECONDS == 30
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/test_scrapers.py::test_http_timeout_config_field_exists -v
```

Expected: `FAILED`

- [ ] **Step 3: Add field to config.py**

Add after `SEARCH_LOCATION`:

```python
    HTTP_TIMEOUT_SECONDS: int = 30
```

- [ ] **Step 4: Update all 6 HTTP scrapers**

In each file below, find `timeout=30` inside an `httpx.AsyncClient(...)` or `httpx.Client(...)` call and replace with `timeout=config.HTTP_TIMEOUT_SECONDS`.

**remoteok_scraper.py** — find `timeout=30` in `httpx.AsyncClient`:
```python
# OLD:
async with httpx.AsyncClient(timeout=30) as client:
# NEW:
async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
```

**remotive_scraper.py** — same pattern.

**wwr_scraper.py** — same pattern.

**cybersecjobs_scraper.py** — same pattern.

**himalayas_scraper.py** — same pattern:
```python
# OLD:
async with httpx.AsyncClient(
    headers={"User-Agent": "WorkSearcher/1.0"},
    timeout=30,
) as client:
# NEW:
async with httpx.AsyncClient(
    headers={"User-Agent": "WorkSearcher/1.0"},
    timeout=config.HTTP_TIMEOUT_SECONDS,
) as client:
```

**hackernews_scraper.py** — same pattern.

- [ ] **Step 5: Add to FakeSettings in conftest.py**

```python
    HTTP_TIMEOUT_SECONDS = 30
```

- [ ] **Step 6: Run full test suite**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/ -v
```

Expected: all passing

- [ ] **Step 7: Commit**

```bash
git add worksearcher/config.py \
  worksearcher/scrapers/remoteok_scraper.py \
  worksearcher/scrapers/remotive_scraper.py \
  worksearcher/scrapers/wwr_scraper.py \
  worksearcher/scrapers/cybersecjobs_scraper.py \
  worksearcher/scrapers/himalayas_scraper.py \
  worksearcher/scrapers/hackernews_scraper.py \
  tests/conftest.py tests/test_scrapers.py
git commit -F - <<'EOF'
feat: add HTTP_TIMEOUT_SECONDS — unified httpx timeout via config

All 6 HTTP scrapers now read timeout from config instead of
hardcoded 30s. Useful for slow networks or rate-limited proxies.
EOF
```

---

### Task 5: HIMALAYAS_RESULTS_LIMIT + MAX_JOBS_PER_MESSAGE

**Files:**
- Modify: `worksearcher/config.py`
- Modify: `worksearcher/scrapers/himalayas_scraper.py`
- Modify: `worksearcher/notifier/whatsapp.py`
- Modify: `worksearcher/main.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_scrapers.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_scrapers.py`:

```python
def test_himalayas_results_limit_config_field_exists():
    from worksearcher.config import Settings
    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert s.HIMALAYAS_RESULTS_LIMIT == 50
```

Add to `tests/test_pipeline.py`:

```python
def test_max_jobs_per_message_config_field_exists():
    from worksearcher.config import Settings
    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert s.MAX_JOBS_PER_MESSAGE == 10
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/test_scrapers.py::test_himalayas_results_limit_config_field_exists tests/test_pipeline.py::test_max_jobs_per_message_config_field_exists -v
```

Expected: `FAILED`

- [ ] **Step 3: Add fields to config.py**

Add after `HTTP_TIMEOUT_SECONDS`:

```python
    HIMALAYAS_RESULTS_LIMIT: int = 50
    MAX_JOBS_PER_MESSAGE: int = 10
```

- [ ] **Step 4: Update himalayas_scraper.py**

```python
# OLD:
response = await client.get(HIMALAYAS_API, params={"limit": 50})
# NEW:
response = await client.get(HIMALAYAS_API, params={"limit": config.HIMALAYAS_RESULTS_LIMIT})
```

- [ ] **Step 5: Update whatsapp.py**

Change `_build_message` to accept `max_jobs` parameter and remove the module-level constant:

```python
# DELETE this line:
MAX_JOBS_PER_MESSAGE = 10

# Update _build_message signature:
def _build_message(jobs: list[Job], max_jobs: int) -> str:
    lines = ["*WorkSearcher — nuevas ofertas:*\n"]
    for job in jobs[:max_jobs]:
        lines.append(f"• *{job.title}* @ {job.company}")
        lines.append(f"  [{job.source}] {job.url}\n")
    if len(jobs) > max_jobs:
        lines.append(f"_...y {len(jobs) - max_jobs} más guardadas en DB_")
    return "\n".join(lines)

# Update send_digest to pass the limit:
async def send_digest(jobs: list[Job], config: Settings) -> bool:
    if not jobs:
        return False

    url = _META_API_URL.format(version=config.META_API_VERSION, phone_id=config.META_PHONE_NUMBER_ID)
    headers = {
        "Authorization": f"Bearer {config.META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": config.META_RECIPIENT_PHONE,
        "type": "text",
        "text": {"body": _build_message(jobs, config.MAX_JOBS_PER_MESSAGE)},
    }

    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info("WhatsApp digest sent: %d jobs", len(jobs))
            return True
        except httpx.HTTPStatusError as e:
            error_code = e.response.json().get("error", {}).get("code") if e.response.content else None
            logger.error("WhatsApp API error %s (code=%s)", e.response.status_code, error_code)
            return False
        except httpx.RequestError as e:
            logger.error("WhatsApp request failed: %s", e)
            return False
```

- [ ] **Step 6: Update main.py**

Remove the `MAX_JOBS_PER_MESSAGE` import from whatsapp and use config:

```python
# OLD import line:
from worksearcher.notifier.whatsapp import MAX_JOBS_PER_MESSAGE, send_digest

# NEW import line:
from worksearcher.notifier.whatsapp import send_digest
```

In `_run_pipeline`, replace the two slice references:

```python
# Line ~101 (unnotified retry path):
# OLD:
mark_jobs_notified([j.fingerprint for j in unnotified[:MAX_JOBS_PER_MESSAGE]], conn)
# NEW:
mark_jobs_notified([j.fingerprint for j in unnotified[:config.MAX_JOBS_PER_MESSAGE]], conn)

# Line ~113 (new jobs path):
# OLD:
mark_jobs_notified([j.fingerprint for j in new_jobs[:MAX_JOBS_PER_MESSAGE]], conn)
# NEW:
mark_jobs_notified([j.fingerprint for j in new_jobs[:config.MAX_JOBS_PER_MESSAGE]], conn)
```

- [ ] **Step 7: Add to FakeSettings in conftest.py**

```python
    HIMALAYAS_RESULTS_LIMIT = 50
    MAX_JOBS_PER_MESSAGE = 10
```

- [ ] **Step 8: Update test_pipeline.py imports**

Remove the `MAX_JOBS_PER_MESSAGE` import from whatsapp:

```python
# OLD:
from worksearcher.notifier.whatsapp import MAX_JOBS_PER_MESSAGE

# DELETE the line above — it no longer exists.
```

In `test_pipeline_marks_only_sent_jobs_as_notified`, replace `MAX_JOBS_PER_MESSAGE` with `fake_settings.MAX_JOBS_PER_MESSAGE`:

```python
@pytest.mark.asyncio
async def test_pipeline_marks_only_sent_jobs_as_notified(tmp_path, monkeypatch, fake_settings):
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
```

- [ ] **Step 9: Run full test suite**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/ -v
```

Expected: all passing

- [ ] **Step 10: Commit**

```bash
git add worksearcher/config.py \
  worksearcher/scrapers/himalayas_scraper.py \
  worksearcher/notifier/whatsapp.py \
  worksearcher/main.py \
  tests/conftest.py tests/test_pipeline.py tests/test_scrapers.py
git commit -F - <<'EOF'
feat: add HIMALAYAS_RESULTS_LIMIT + move MAX_JOBS_PER_MESSAGE to config

Himalayas API result limit now configurable. MAX_JOBS_PER_MESSAGE
moved from whatsapp module constant into Settings so it can be
tuned via .env without code changes.
EOF
```

---

### Task 6: SCRAPER_TIMEOUT_SECONDS

**Files:**
- Modify: `worksearcher/config.py`
- Modify: `worksearcher/main.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_pipeline.py`:

```python
def test_scraper_timeout_config_field_exists():
    from worksearcher.config import Settings
    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert s.SCRAPER_TIMEOUT_SECONDS == 120
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/test_pipeline.py::test_scraper_timeout_config_field_exists -v
```

Expected: `FAILED`

- [ ] **Step 3: Add field to config.py**

Add after `MAX_JOBS_PER_MESSAGE`:

```python
    SCRAPER_TIMEOUT_SECONDS: int = 120
```

- [ ] **Step 4: Update main.py**

In `_scrape_with_timeout`:

```python
# OLD:
return await asyncio.wait_for(scraper(config), timeout=120)
# ... and the error message:
logger.error("Scraper %s timed out after 120s", scraper.__name__)

# NEW:
return await asyncio.wait_for(scraper(config), timeout=config.SCRAPER_TIMEOUT_SECONDS)
# ... and the error message:
logger.error("Scraper %s timed out after %ds", scraper.__name__, config.SCRAPER_TIMEOUT_SECONDS)
```

- [ ] **Step 5: Add to FakeSettings in conftest.py**

```python
    SCRAPER_TIMEOUT_SECONDS = 120
```

- [ ] **Step 6: Run full test suite**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/ -v
```

Expected: all passing

- [ ] **Step 7: Commit**

```bash
git add worksearcher/config.py worksearcher/main.py tests/conftest.py tests/test_pipeline.py
git commit -F - <<'EOF'
feat: add SCRAPER_TIMEOUT_SECONDS config field

Per-scraper timeout in _run_pipeline now reads from config instead
of hardcoded 120s. Useful when Playwright scrapers run slow on VPS.
EOF
```

---

### Task 7: Update .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add all new variables**

Replace the full `.env.example` content:

```dotenv
# Meta Cloud API — WhatsApp Business (System User token, never expires)
META_PHONE_NUMBER_ID=your_phone_number_id_here
META_ACCESS_TOKEN=your_permanent_system_user_token_here
META_RECIPIENT_PHONE=+521234567890  # con código de país
# META_API_VERSION=v21.0  # sólo cambiar cuando Meta deprece la versión actual

# ---------------------------------------------------------------------------
# Scraper selection — comma-separated list of active platforms
# Valid values: jobspy, remoteok, remotive, wwr, cybersecjobs,
#               computrabajo, bumeran, himalayas, hackernews
# ---------------------------------------------------------------------------
# ENABLED_SCRAPERS=jobspy,remoteok,remotive,wwr,cybersecjobs,computrabajo,bumeran,himalayas,hackernews

# ---------------------------------------------------------------------------
# Post-scrape keyword filter — applied to ALL scrapers (no term limit)
# ---------------------------------------------------------------------------
SEARCH_KEYWORDS=python,javascript,typescript,react,node.js,frontend,backend,fullstack,software engineer,developer,web developer,cybersecurity,security engineer,SOC analyst,pentester,infosec,ethical hacker,red team,blue team,cloud security,devops,automation,SRE

# ---------------------------------------------------------------------------
# jobspy (LinkedIn / Indeed / Glassdoor)
# ---------------------------------------------------------------------------
# Query sent to jobspy — max 5 terms
JOBSPY_SEARCH_TERMS=python,cybersecurity,software engineer,devops,javascript

# Which platforms jobspy queries (valid: linkedin, indeed, glassdoor)
# JOBSPY_SITES=linkedin,indeed,glassdoor

# Geographic search scope (e.g. "Mexico City", "Remote", "Buenos Aires")
# SEARCH_LOCATION=Remote

# Max results per site per run
# JOBSPY_RESULTS_WANTED=50

# Only return jobs posted within this many hours
# JOBSPY_HOURS_OLD=24

# ---------------------------------------------------------------------------
# LatAm scrapers (Bumeran, Computrabajo)
# ---------------------------------------------------------------------------
# Spanish search terms for Bumeran (Bumeran MX uses Spanish titles)
# BUMERAN_SEARCH_TERMS=desarrollador,programador,backend,ciberseguridad,seguridad informatica

# Spanish search terms for Computrabajo
# COMPUTRABAJO_SEARCH_TERMS=desarrollador,programador,backend,ciberseguridad,seguridad informatica

# ---------------------------------------------------------------------------
# Himalayas
# ---------------------------------------------------------------------------
# Max jobs fetched per run from the Himalayas API
# HIMALAYAS_RESULTS_LIMIT=50

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
# Discard jobs requiring more years of experience than this
MAX_YEARS_EXPERIENCE=3

# Discard jobs older than N days (0 = no filter)
MAX_JOB_AGE_DAYS=30

# Discard jobs whose title/description matches these keywords (case-insensitive)
BLACKLIST_KEYWORDS=security clearance,active clearance,top secret,ts/sci,dod clearance,secret clearance,public trust,us citizens only,must be authorized to work in the us,us work authorization,must be a us citizen,green card required,sales executive,account executive,must relocate,relocation required,staffing agency,recruiting firm

# Allowed description languages (ISO 639-1). Empty = no language filter
FILTER_LANGUAGES=en,es

# Minimum monthly salary in USD. Empty = no salary filter
MIN_SALARY_USD_MONTHLY=

# ---------------------------------------------------------------------------
# WhatsApp notifications
# ---------------------------------------------------------------------------
# Max job listings per WhatsApp message (remainder saved in DB for next run)
# MAX_JOBS_PER_MESSAGE=10

# ---------------------------------------------------------------------------
# Performance tuning
# ---------------------------------------------------------------------------
# HTTP timeout in seconds for all httpx-based scrapers
# HTTP_TIMEOUT_SECONDS=30

# Hard timeout per scraper in the pipeline (prevents hung Playwright browsers)
# SCRAPER_TIMEOUT_SECONDS=120

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
# Path to SQLite DB — on VPS use absolute path outside repo
# DB_PATH=worksearcher.db
```

- [ ] **Step 2: Run linter**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run ruff check . && uv run ruff format --check .
```

Expected: no errors

- [ ] **Step 3: Run full test suite one final time**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && uv run pytest tests/ -v
```

Expected: all passing

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -F - <<'EOF'
docs: update .env.example with all new configurable fields

Documents all 11 new env vars added in feat/009-flexibility.
New vars commented out (defaults match prior hardcoded behaviour).
EOF
```

---

## Summary of all new config fields

| Field | Default | Replaces |
|-------|---------|---------|
| `ENABLED_SCRAPERS` | all 9 scrapers | hardcoded `_SCRAPERS` list in main.py |
| `BUMERAN_SEARCH_TERMS` | `desarrollador,...` | `_SEARCH_TERMS` constant in bumeran_scraper.py |
| `COMPUTRABAJO_SEARCH_TERMS` | `desarrollador,...` | `keywords_list[:5]` in computrabajo_scraper.py |
| `JOBSPY_SITES` | `linkedin,indeed,glassdoor` | hardcoded list in jobspy_scraper.py |
| `JOBSPY_RESULTS_WANTED` | `50` | hardcoded `results_wanted=50` |
| `JOBSPY_HOURS_OLD` | `24` | hardcoded `hours_old=24` |
| `SEARCH_LOCATION` | `Remote` | hardcoded `location="Remote"` |
| `HTTP_TIMEOUT_SECONDS` | `30` | hardcoded `timeout=30` in 6 scrapers |
| `HIMALAYAS_RESULTS_LIMIT` | `50` | hardcoded `params={"limit": 50}` |
| `MAX_JOBS_PER_MESSAGE` | `10` | `MAX_JOBS_PER_MESSAGE` constant in whatsapp.py |
| `SCRAPER_TIMEOUT_SECONDS` | `120` | hardcoded `timeout=120` in main.py |
