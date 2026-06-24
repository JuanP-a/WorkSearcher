# Arquitectura — WorkSearcher

## Stack

| Capa | Tecnología |
|------|-----------|
| Lenguaje | Python 3.12 |
| Scraping major boards | `jobspy` (pinado a commit SHA, no semver) |
| Scraping niche / JSON APIs | `httpx` + `BeautifulSoup4` |
| Scraping LatAm (JS-heavy) | `playwright` (Chromium headless) |
| Detección de idioma | `langdetect` (usa `detect_langs`, no `detect`) |
| Modelos de datos | `pydantic` v2 |
| Configuración | `pydantic-settings` (desde `.env`) |
| Base de datos | SQLite stdlib — WAL mode, `INSERT OR IGNORE` |
| Scheduler | cron del sistema (no daemon, no APScheduler) |
| Notificaciones | Meta Cloud API — mensajes de texto WhatsApp |
| CLI | `click` |
| Tests | `pytest` + `respx` (mocks HTTP) + `pytest-asyncio` |
| Linter | `ruff` (E/W/F/I/B/UP, target py312) |
| CI | GitHub Actions — `jdx/mise-action` + pytest + ruff |

---

## Mapa de carpetas

```
worksearcher/
  scrapers/           ← un módulo por plataforma; interfaz uniforme
    jobspy_scraper.py       LinkedIn · Indeed · Glassdoor
    remoteok_scraper.py     API JSON pública
    remotive_scraper.py     API JSON pública
    wwr_scraper.py          We Work Remotely — httpx + BS4
    cybersecjobs_scraper.py isecjobs.com — httpx + BS4
    himalayas_scraper.py    API JSON pública
    hackernews_scraper.py   Algolia API (hilo "Who's Hiring")
    computrabajo_scraper.py playwright — LatAm
    bumeran_scraper.py      playwright — LatAm
  core/               ← lógica pura, sin I/O
    models.py               Job (Pydantic) + JobSource (StrEnum)
    filters.py              Predicados puros + filter_jobs
    deduplicator.py         deduplicate(jobs, seen) → list[Job]
    utils.py                slugify()
  storage/
    database.py             SQLite CRUD (init, save, dedup query, notified)
  notifier/
    whatsapp.py             send_digest() → bool
  config.py           ← Settings (pydantic-settings, lee .env)
  main.py             ← _run_pipeline() + CLI click
  __main__.py         ← permite `python -m worksearcher run`

specs/                ← una spec SDD por feature (antes de implementar)
docs/
  arquitectura.md     ← diseño general del sistema
  deuda-tecnica.md    ← backlog de issues técnicos con estado
  contexto/           ← este directorio
  superpowers/plans/  ← planes de implementación generados por agente

tests/                ← pytest; un archivo por módulo
  conftest.py         ← FakeSettings + fixture fake_settings
```

---

## Flujo de datos

```
cron (cada 4h)
    └─▶ main._run_pipeline(config)
            │
            ├─▶ [9 scrapers concurrentes — asyncio.gather, 120s timeout cada uno]
            │       └─▶ list[Job]  (cada scraper devuelve [] si falla)
            │
            ├─▶ filter_jobs(all_jobs, config.*)
            │       ├─ is_relevant (keywords + is_remote)
            │       ├─ meets_experience_requirement (MAX_YEARS_EXPERIENCE)
            │       ├─ is_recent (MAX_JOB_AGE_DAYS, total_seconds)
            │       ├─ is_not_blacklisted (BLACKLIST_KEYWORDS)
            │       ├─ is_language_allowed (FILTER_LANGUAGES, langdetect ≥0.8)
            │       └─ has_minimum_salary (MIN_SALARY_USD_MONTHLY)
            │
            ├─▶ deduplicate(relevant, seen_fingerprints_from_db)
            │
            ├─▶ save_jobs(new_jobs, conn)          → SQLite INSERT OR IGNORE
            │
            └─▶ send_digest(new_jobs, config)      → WhatsApp (Meta Cloud API)
                    └─ mark_jobs_notified(fps, conn) si send_digest devuelve True
```

**Retry de notificación:** al inicio del pipeline, `get_unnotified_jobs` recupera
jobs guardados con `notified=0` y los reenvía antes de procesar el scrape nuevo.

---

## Modelo de datos principal

```python
class Job(BaseModel):
    title: str
    company: str
    location: str
    url: str                               # único por job
    source: JobSource                      # enum de 11 valores
    is_remote: bool
    description: str = ""
    posted_at: datetime | None = None      # UTC; None si el scraper no lo expone
    min_salary_usd_monthly: float | None = None  # USD/mes normalizado; None = desconocido
    fingerprint: str  # computed: sha256(lower(title+company+url)) — clave de dedup
```

SQLite guarda también: `created_at` (CURRENT_TIMESTAMP) y `notified` (0/1).
`min_salary_usd_monthly` **no se persiste** en la BD — solo se usa en el filtro en memoria.

---

## Qué NO existe (gaps conocidos)

- **Sin interfaz web / dashboard** — solo CLI + WhatsApp
- **Sin conversión de divisas** — solo salarios en USD son procesados
- **Sin proxy pool activo** — jobspy usa Webshare free tier [PENDIENTE: verificar config actual]
- **Sin alertas de scraper caído** — fallos loguean a stderr; no hay notificación de error
- **Sin versionado de schema SQLite** — migrations manuales via `ALTER TABLE ... IF NOT EXISTS`
- **Sin rate limiting entre scrapers** — todos lanzan simultáneamente
- **`min_salary_usd_monthly` no persiste** — no hay historial de salarios en BD
