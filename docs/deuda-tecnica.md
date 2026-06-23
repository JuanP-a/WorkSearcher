# Deuda Técnica — WorkSearcher

Hallazgos consolidados de reviews: backend, QA y DevOps.
Formato: `[archivo:línea]` donde aplica. Ordenado por severidad.

---

## Pendiente — requiere VPS

### DEVOPS-2 — Log sin rotación — llenará el disco de la VPS
**Archivo:** `crontab.example:3`, `README.md:31`
Ambos usan `>> /var/log/worksearcher.log` (append infinito). Con Playwright + 4 scrapers × 4h = disco lleno en semanas. Cuando el disco se llene, SQLite falla silenciosamente.
**Fix:** `/etc/logrotate.d/worksearcher` (daily, compress, 14 días) antes del deploy.

### DEVOPS-3 — Playwright requiere `install-deps` en Ubuntu — no documentado
**Archivo:** `README.md:13`
`playwright install chromium` no instala dependencias del sistema (`libnss3`, `libatk-bridge2.0-0`, etc.). En VPS fresh Ubuntu 22.04 los scrapers LatAm fallarán silenciosamente.
**Fix:** Agregar `playwright install-deps chromium` al setup, o crear `deploy/setup.sh`.

### DEVOPS-7 — DB en raíz del repo — `git clean -fd` destruye historial de dedup
**Archivo:** `worksearcher/storage/database.py:10`
`worksearcher.db` vive junto al código. En la VPS, mover a `/var/lib/worksearcher/`.

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
`asyncio.wait_for(scraper(config), timeout=120)` por scraper. Un navegador colgado no bloquea el pipeline.

### BACK-11 — Dependencias sin lockfile ✓
`requirements.lock` generado con versiones exactas de los 39 paquetes.

### BACK-12 — `wait_for_timeout(3_000)` hardcodeado en Bumeran ✓
Reemplazado por `page.wait_for_selector("a[href*='/empleos/']", timeout=10_000)`.

### BACK-13 — `_slug()` duplicada en Bumeran y Computrabajo ✓
Movida a `worksearcher/core/utils.py` como `slugify()`.

### BACK-14 — `SCRAPE_INTERVAL_HOURS` confundía operadores ✓
Comentado en `.env.example` como referencia humana; no lo lee el código.

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
