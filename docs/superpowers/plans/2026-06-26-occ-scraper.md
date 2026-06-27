# OCC Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OCC (occ.com.mx) as a job source with Playwright scraping and configurable search terms.

**Architecture:** Follows the established LatAm Playwright scraper pattern (Bumeran/Computrabajo). Remote jobs filtered server-side by OCC via URL path `/tipo-home-office-remoto/` — no text-marker check needed. Pure `_build_url` function enables unit testing without Playwright.

**Tech Stack:** Python 3.12, Playwright (sync_api), pydantic-settings, pytest, ruff

---

### Task 1: Add `JobSource.OCC` to models

**Files:**
- Modify: `worksearcher/core/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_models.py`:

```python
def test_job_source_occ_value():
    from worksearcher.core.models import JobSource
    assert JobSource.OCC == "occ"
```

- [ ] **Step 2: Run test — verify FAIL**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/test_models.py::test_job_source_occ_value -v
```
Expected: `AttributeError: OCC`

- [ ] **Step 3: Add `OCC` to `JobSource` enum**

In `worksearcher/core/models.py`, after line `HACKERNEWS = "hackernews"`:

```python
    OCC = "occ"
```

- [ ] **Step 4: Run test — verify PASS**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/test_models.py::test_job_source_occ_value -v
```
Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && git add worksearcher/core/models.py tests/test_models.py && git commit -F - <<'EOF'
feat: add JobSource.OCC enum value

Part of feat-010-occ-scraper.
EOF
```

---

### Task 2: Add OCC config fields

**Files:**
- Modify: `worksearcher/config.py`
- Modify: `tests/test_scrapers.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_scrapers.py` (at the bottom, after existing LatAm tests):

```python
def test_occ_search_terms_config_field_exists():
    from worksearcher.config import Settings

    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
    )
    assert s.occ_search_terms_list == [
        "desarrollador",
        "programador",
        "backend",
        "ciberseguridad",
        "seguridad informatica",
    ]


def test_occ_known_scraper_registered_in_config():
    from pydantic import ValidationError

    from worksearcher.config import Settings

    # "occ" must be accepted as a valid scraper name
    s = Settings(
        META_PHONE_NUMBER_ID="x",
        META_ACCESS_TOKEN="x",
        META_RECIPIENT_PHONE="x",
        ENABLED_SCRAPERS="occ",
    )
    assert "occ" in s.enabled_scrapers_list

    # unknown name must still be rejected
    with pytest.raises(ValidationError, match="Unknown scrapers"):
        Settings(
            META_PHONE_NUMBER_ID="x",
            META_ACCESS_TOKEN="x",
            META_RECIPIENT_PHONE="x",
            ENABLED_SCRAPERS="occ,notareal",
        )
```

- [ ] **Step 2: Run tests — verify FAIL**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/test_scrapers.py::test_occ_search_terms_config_field_exists tests/test_scrapers.py::test_occ_known_scraper_registered_in_config -v
```
Expected: `AttributeError: occ_search_terms_list`

- [ ] **Step 3: Add OCC fields to `worksearcher/config.py`**

In `_KNOWN_SCRAPERS`, add `"occ"` to the frozenset:

```python
    _KNOWN_SCRAPERS: ClassVar[frozenset[str]] = frozenset(
        {
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
    )
```

In `ENABLED_SCRAPERS` default, append `,occ`:

```python
    ENABLED_SCRAPERS: str = (
        "jobspy,remoteok,remotive,wwr,cybersecjobs,computrabajo,bumeran,himalayas,hackernews,occ"
    )
```

After `COMPUTRABAJO_SEARCH_TERMS` field (around line 51), add:

```python
    OCC_SEARCH_TERMS: str = (
        "desarrollador,programador,backend,ciberseguridad,seguridad informatica"
    )
```

After `computrabajo_search_terms_list` property (around line 128), add:

```python
    @property
    def occ_search_terms_list(self) -> list[str]:
        return [t.strip().lower() for t in self.OCC_SEARCH_TERMS.split(",") if t.strip()]
```

- [ ] **Step 4: Run tests — verify PASS**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/test_scrapers.py::test_occ_search_terms_config_field_exists tests/test_scrapers.py::test_occ_known_scraper_registered_in_config -v
```
Expected: both `PASSED`

- [ ] **Step 5: Run full suite — verify no regressions**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/ -q
```
Expected: all pass (existing `test_enabled_scrapers_rejects_unknown_name` still passes because "occ" is now known).

- [ ] **Step 6: Commit**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && git add worksearcher/config.py tests/test_scrapers.py && git commit -F - <<'EOF'
feat: add OCC_SEARCH_TERMS config field and register occ in _KNOWN_SCRAPERS

Adds OCC_SEARCH_TERMS (independent from Bumeran/Computrabajo),
occ_search_terms_list property, and registers "occ" as a valid
scraper name in _KNOWN_SCRAPERS and ENABLED_SCRAPERS default.
EOF
```

---

### Task 3: Update FakeSettings and pipeline registry tests

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Add `occ_search_terms_list` to `FakeSettings` in `tests/conftest.py`**

In `FakeSettings`, add after `computrabajo_search_terms_list`:

```python
    occ_search_terms_list = ["desarrollador", "programador"]
```

Also add `"occ"` to `enabled_scrapers_list`:

```python
    enabled_scrapers_list = [
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
    ]
```

- [ ] **Step 2: Update pipeline registry tests in `tests/test_pipeline.py`**

Update `test_all_scrapers_dict_includes_all_platforms` — add `"occ"` to the expected set:

```python
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
```

Update `test_enabled_scrapers_defaults_to_all` — add `"occ"` to the expected set:

```python
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
```

- [ ] **Step 3: Run pipeline tests — verify they fail on `_ALL_SCRAPERS` (scraper not registered yet)**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/test_pipeline.py::test_all_scrapers_dict_includes_all_platforms -v
```
Expected: `FAILED` — `"occ"` missing from `_ALL_SCRAPERS` (that's correct, Task 5 wires it in)

- [ ] **Step 4: Commit conftest + test updates**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && git add tests/conftest.py tests/test_pipeline.py && git commit -F - <<'EOF'
test: update FakeSettings and registry assertions for OCC scraper

Prepares test suite for OCC integration — adds occ_search_terms_list
to FakeSettings and updates _ALL_SCRAPERS / enabled_scrapers expected sets.
Tests intentionally fail until occ_scraper is registered in main.py (Task 5).
EOF
```

---

### Task 4: Implement `occ_scraper.py`

**Files:**
- Create: `worksearcher/scrapers/occ_scraper.py`
- Modify: `tests/test_scrapers.py`

- [ ] **Step 1: Write failing tests for `_build_url`**

Add to `tests/test_scrapers.py`:

```python
# --- OCC: URL builder (pure function, testable without Playwright) ---


def test_occ_build_url_simple_term():
    from worksearcher.scrapers.occ_scraper import _build_url

    url = _build_url("desarrollador")
    assert url == "https://www.occ.com.mx/empleos/de-desarrollador/tipo-home-office-remoto/"


def test_occ_build_url_multi_word_term():
    from worksearcher.scrapers.occ_scraper import _build_url

    url = _build_url("seguridad informatica")
    assert url == "https://www.occ.com.mx/empleos/de-seguridad-informatica/tipo-home-office-remoto/"


def test_occ_build_url_uppercase_normalized():
    from worksearcher.scrapers.occ_scraper import _build_url

    url = _build_url("Ciberseguridad")
    assert url == "https://www.occ.com.mx/empleos/de-ciberseguridad/tipo-home-office-remoto/"


def test_occ_no_remote_markers_constant():
    """OCC filters remote server-side via URL path — no _REMOTE_MARKERS needed."""
    import worksearcher.scrapers.occ_scraper as mod

    assert not hasattr(mod, "_REMOTE_MARKERS"), (
        "_REMOTE_MARKERS must not exist in occ_scraper — remote is filtered by URL path"
    )
```

- [ ] **Step 2: Run tests — verify FAIL**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/test_scrapers.py::test_occ_build_url_simple_term tests/test_scrapers.py::test_occ_build_url_multi_word_term tests/test_scrapers.py::test_occ_build_url_uppercase_normalized tests/test_scrapers.py::test_occ_no_remote_markers_constant -v
```
Expected: `ModuleNotFoundError: occ_scraper`

- [ ] **Step 3: Create `worksearcher/scrapers/occ_scraper.py`**

```python
import asyncio
import logging

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource
from worksearcher.core.utils import slugify

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.occ.com.mx"


def _build_url(term: str) -> str:
    return f"{_BASE_URL}/empleos/de-{slugify(term)}/tipo-home-office-remoto/"


def _blocking_scrape(config: Settings) -> list[Job]:
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright

    jobs: list[Job] = []
    seen_urls: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="es-MX",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for term in config.occ_search_terms_list:
            page = context.new_page()
            try:
                url = _build_url(term)
                logger.debug("OCC: fetching %s", url)
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)

                if "403" in page.title() or "Forbidden" in page.title():
                    logger.warning("OCC: 403 received — skipping remaining terms")
                    page.close()
                    break

                try:
                    # OCC individual job URLs use /empleo/ (singular)
                    page.wait_for_selector("a[href*='/empleo/']", timeout=10_000)
                except PWTimeout:
                    logger.warning("OCC: no job cards loaded for '%s'", term)
                    page.close()
                    continue

                job_links = page.query_selector_all("a[href*='/empleo/']")
                for link in job_links:
                    try:
                        href = link.get_attribute("href") or ""
                        if not href or href in seen_urls:
                            continue

                        job_url = href if href.startswith("http") else f"{_BASE_URL}{href}"
                        seen_urls.add(href)

                        raw = link.inner_text().strip()
                        lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]

                        title = next((ln for ln in lines if len(ln) > 3), "")
                        company_idx = lines.index(title) + 1 if title in lines else -1
                        company = lines[company_idx] if 0 < company_idx < len(lines) else ""

                        if not title:
                            continue

                        jobs.append(
                            Job(
                                title=title,
                                company=company,
                                location="Remote",
                                url=job_url,
                                source=JobSource.OCC,
                                is_remote=True,
                            )
                        )
                    except Exception as exc:
                        logger.warning("OCC: skipping malformed link: %s", exc)
                        continue

            except Exception as exc:
                logger.warning("OCC: term '%s' failed: %s", term, exc)
            finally:
                page.close()

        browser.close()

    return jobs


async def scrape(config: Settings) -> list[Job]:
    try:
        jobs = await asyncio.to_thread(_blocking_scrape, config)
        logger.info("OCC: %d jobs found", len(jobs))
        return jobs
    except Exception as exc:
        logger.error("OCC scraper failed: %s", exc)
        return []
```

- [ ] **Step 4: Run OCC tests — verify PASS**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/test_scrapers.py::test_occ_build_url_simple_term tests/test_scrapers.py::test_occ_build_url_multi_word_term tests/test_scrapers.py::test_occ_build_url_uppercase_normalized tests/test_scrapers.py::test_occ_no_remote_markers_constant -v
```
Expected: all `PASSED`

- [ ] **Step 5: Run full scrapers test suite**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/test_scrapers.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && git add worksearcher/scrapers/occ_scraper.py tests/test_scrapers.py && git commit -F - <<'EOF'
feat: implement OCC Playwright scraper

Scrapes occ.com.mx for remote jobs. Remote filter embedded in URL path
(/tipo-home-office-remoto/) — OCC filters server-side, no text markers needed.
Exports _build_url() as pure function for unit testing.
EOF
```

---

### Task 5: Register OCC in pipeline (`main.py`)

**Files:**
- Modify: `worksearcher/main.py`

- [ ] **Step 1: Add `occ_scraper` import to `worksearcher/main.py`**

In the scrapers import block (after `wwr_scraper`), add:

```python
from worksearcher.scrapers import (
    bumeran_scraper,
    computrabajo_scraper,
    cybersecjobs_scraper,
    hackernews_scraper,
    himalayas_scraper,
    jobspy_scraper,
    occ_scraper,
    remoteok_scraper,
    remotive_scraper,
    wwr_scraper,
)
```

- [ ] **Step 2: Add `"occ"` entry to `_ALL_SCRAPERS` dict**

In `_ALL_SCRAPERS`, add after `"hackernews"`:

```python
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
    "occ": occ_scraper.scrape,
}
```

- [ ] **Step 3: Run pipeline registry tests — verify PASS**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/test_pipeline.py::test_all_scrapers_dict_includes_all_platforms tests/test_pipeline.py::test_enabled_scrapers_defaults_to_all -v
```
Expected: both `PASSED` (were failing since Task 3)

- [ ] **Step 4: Run full test suite**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/ -q
```
Expected: all pass, no regressions

- [ ] **Step 5: Lint check**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && ruff check . && ruff format --check .
```
Expected: no violations

- [ ] **Step 6: Commit**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && git add worksearcher/main.py && git commit -F - <<'EOF'
feat: register occ_scraper in pipeline _ALL_SCRAPERS

Completes OCC integration — scraper now runs as part of the
default pipeline alongside Bumeran and Computrabajo.
EOF
```

---

### Task 6: Update docs and `.env.example`

**Files:**
- Modify: `.env.example`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add OCC section to `.env.example`**

Find the Bumeran/Computrabajo section in `.env.example` and add after it:

```bash
# ---------------------------------------------------------------------------
# OCC (occ.com.mx) — LatAm scraper, México
# Remote filter embebido en URL path (/tipo-home-office-remoto/) — no markers
# ---------------------------------------------------------------------------
# OCC_SEARCH_TERMS=desarrollador,programador,backend,ciberseguridad,seguridad informatica
```

- [ ] **Step 2: Update OCC entry in CLAUDE.md platforms table**

In `CLAUDE.md`, the "Plataformas target" table currently has 10 platforms. Add OCC:

```markdown
| OCC | playwright scraping | LatAm (MX) |
```

Also add `OCC_SEARCH_TERMS` to the "Keywords de búsqueda" section:

```markdown
- **`OCC_SEARCH_TERMS`** (términos en español para OCC MX):
  - Default: desarrollador, programador, backend, ciberseguridad, seguridad informatica
```

- [ ] **Step 3: Verify full suite still green**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && python -m pytest tests/ -q && ruff check . && ruff format --check .
```
Expected: all pass, no violations

- [ ] **Step 4: Commit**

```bash
cd "/Volumes/M2 Mac/proyectos/WorkSearcher" && git add .env.example CLAUDE.md && git commit -F - <<'EOF'
docs: add OCC scraper to .env.example and CLAUDE.md

Documents OCC_SEARCH_TERMS config field and adds OCC to the
platform table and keyword configuration section.
EOF
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|-----------------|------|
| `JobSource.OCC == "occ"` | Task 1 |
| `OCC_SEARCH_TERMS` config field + `occ_search_terms_list` | Task 2 |
| `"occ"` in `_KNOWN_SCRAPERS` + `ENABLED_SCRAPERS` | Task 2 |
| `_build_url(term)` returns correct URL | Task 4 |
| No `_REMOTE_MARKERS` constant | Task 4 |
| `"occ"` in `_ALL_SCRAPERS` | Task 5 |
| No regressions | Task 3, 4, 5 |
| `.env.example` + CLAUDE.md docs | Task 6 |

All spec requirements covered. ✓

### Placeholder scan

No TBD, TODO, or vague instructions found. All code blocks show exact content. ✓

### Type consistency

- `_build_url(term: str) -> str` — used in `_blocking_scrape` and tests consistently.
- `config.occ_search_terms_list` — defined in Task 2, used in `_blocking_scrape` in Task 4 and `FakeSettings` in Task 3. ✓
- `JobSource.OCC` — defined in Task 1, used in `occ_scraper.py` Task 4. ✓
