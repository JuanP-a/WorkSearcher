# Deuda Técnica — WorkSearcher

Hallazgos consolidados de reviews: backend, QA y DevOps.
Formato: `[archivo:línea]` donde aplica. Ordenado por severidad.

---

## Pendiente

_(sin items pendientes)_

---

## Completado ✓

### BACK-1 — Full table scan en fingerprints ✓
`get_seen_fingerprints` ahora consulta solo los candidatos del scrape actual via `WHERE fingerprint IN (...)`.

### BACK-2 — Bumeran/Computrabajo marcaban `is_remote=True` sin verificarlo ✓
Ambos scrapers ahora verifican marcadores de texto ("remoto", "home office", "teletrabajo") antes de incluir un job.

### BACK-3 — Regex de experiencia no cubría todos los guiones Unicode ✓
`_RANGE_PATTERN` ahora incluye figure dash, em dash y minus sign (`[-‒–—−]`).

### BACK-4 — `save_jobs` usaba dos `COUNT(*)` ✓
Reemplazado por `cursor.rowcount`.

### BACK-6 — Playwright reutilizaba `page` entre keywords ✓
Computrabajo ahora abre una página nueva por keyword con `page.close()` en finally.

### BACK-7 — CyberSecJobs no extraía `company` ✓
Extracción best-effort desde el card parent HTML; warning cuando no se encuentra.

### BACK-8 — Versión Meta API hardcodeada ✓
`META_API_VERSION: str = "v21.0"` en Settings; configurable vía `.env`.

### BACK-9 — jobspy fallback silencioso a `LINKEDIN` para fuentes desconocidas ✓
Fuentes desconocidas emiten warning y se omiten en lugar de atribuirse a LinkedIn.

### BACK-10 — Sin timeout por scraper ✓
`asyncio.wait_for(scraper(config), timeout=config.SCRAPER_TIMEOUT_SECONDS)` por scraper (default 120s, configurable via `.env`). Un navegador colgado no bloquea el pipeline.

### BACK-11 — Dependencias sin lockfile ✓
`requirements.lock` generado con versiones exactas de los 39 paquetes.

### BACK-12 — `wait_for_timeout(3_000)` hardcodeado en Bumeran ✓
Reemplazado por `page.wait_for_selector("a[href*='/empleos/']", timeout=10_000)`.

### BACK-13 — `_slug()` duplicada en Bumeran y Computrabajo ✓
Movida a `worksearcher/core/utils.py` como `slugify()`.

### BACK-14 — `SCRAPE_INTERVAL_HOURS` confundía operadores ✓
Comentado en `.env.example` como referencia humana; no lo lee el código.

### DEVOPS-2 — Log sin rotación ✓
`deploy/logrotate.conf` creado (daily, 14 días, compress). `deploy/setup.sh` lo instala en `/etc/logrotate.d/worksearcher`.

### DEVOPS-3 — Playwright `install-deps` no documentado ✓
`deploy/setup.sh` ejecuta `playwright install chromium` + `playwright install-deps chromium`. README actualizado con sección VPS que apunta al script.

### DEVOPS-7 — DB en raíz del repo ✓
`DB_PATH` configurable via `.env` (default `worksearcher.db` para dev local). En VPS: `DB_PATH=/var/lib/worksearcher/worksearcher.db`. `deploy/setup.sh` crea el directorio. `main.py` pasa `Path(config.DB_PATH)` a `get_connection()`.

### DEVOPS-1 — Sin CI/CD ✓
`.github/workflows/ci.yml` con `jdx/mise-action` — pytest + ruff en cada push/PR.

### DEVOPS-4 — User-Agent macOS en VPS Linux ✓
Ambos scrapers Playwright usan User-Agent Linux Chrome.

### DEVOPS-5 — Sin retry en notificación WhatsApp ✓
Columna `notified` en `jobs`. El pipeline reintenta al inicio cualquier job guardado pero no notificado.

### DEVOPS-6 — jobspy sin pin de versión ✓
Pinado a commit SHA específico en `requirements.txt` + `requirements.lock`.

### DEVOPS-8 — Sin `pyproject.toml` ✓
`pyproject.toml` con `asyncio_mode=strict`, `testpaths=["tests"]`, ruff E/W/F/I/B/UP.

### QA-1 — `FakeSettings` duplicado en 3 archivos ✓
Centralizado en `tests/conftest.py` con interfaz completa (incluye `META_API_VERSION`).

### QA-2 — 4 scrapers sin cobertura de tests ✓
Tests para cybersecjobs (HTML mockeado via respx), bumeran y computrabajo (funciones puras + markers).

### QA-4 — Payload de WhatsApp nunca verificado en tests ✓
`test_send_digest_sends_correct_payload` verifica Authorization header, `to`, `messaging_product` y body.

### QA-5 — `test_fingerprint_is_derived_not_stored` era duplicado vacuo ✓
Reemplazado por `test_fingerprint_differs_by_company` que verifica el comportamiento real.

### QA-6 — Keyword `"soc"` matchea substring — sin test ni documentación ✓
Comportamiento documentado explícitamente en `test_keywords_soc_matches_substring` con comentario de decisión.

### QA-7 — `test_job_source_enum_values` solo verificaba 5 de 9 miembros ✓
`test_job_source_enum_covers_all_platforms` verifica las 9 plataformas target.
