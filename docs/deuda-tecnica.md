# Deuda Técnica — WorkSearcher

Hallazgos consolidados de reviews: backend, QA y DevOps.
Formato: `[archivo:línea]` donde aplica. Ordenado por severidad.

---

## Crítico

### BACK-1 — Full table scan en fingerprints (performance + memoria)
**Archivo:** `worksearcher/storage/database.py:67-69`
Carga TODOS los fingerprints históricos a memoria en cada ejecución. En la VPS con 2GB RAM corriendo Playwright en paralelo, esto provocará OOM con meses de datos.
**Fix:** `SELECT fingerprint FROM jobs WHERE fingerprint IN (?, ?, ...)` pasando solo los fingerprints del scrape actual.

### BACK-2 — Bumeran/Computrabajo marcan `is_remote=True` sin verificarlo
**Archivo:** `worksearcher/scrapers/bumeran_scraper.py:82-88`, `computrabajo_scraper.py:80-87`
Son plataformas generales LatAm. No filtran por modalidad remota — todos los jobs reciben `is_remote=True` hardcodeado y pasan el filtro.
**Fix:** Buscar texto "Remoto" / "Home office" en la card antes de marcar, o agregar parámetro de URL si la plataforma lo soporta.

### BACK-3 — Regex de experiencia no cubre todos los guiones Unicode
**Archivo:** `worksearcher/core/filters.py:6-9`
`_RANGE_PATTERN` cubre `-` y `–` pero no figure dash (`‒`) ni minus sign (`−`). Texto copiado de PDF puede contener esos caracteres, haciendo caer al `_YEARS_PATTERN` que toma el número mayor del rango.
**Fix:** `re.compile(r'(\d+)\s*[-‒–—−]\s*(\d+)')` para cubrir todos los variantes.

### DEVOPS-1 — Sin CI/CD — los 73 tests nunca se ejecutan automáticamente
**Archivo:** raíz del proyecto — no existe `.github/workflows/`
Cualquier regresión llega a main sin validación. Los tests existen pero nadie los corre en cada PR.
**Fix:** GitHub Actions con `jdx/mise-action` — `pytest` + `ruff check` en cada push/PR (~20 líneas).

### DEVOPS-2 — Log sin rotación — llenará el disco de la VPS
**Archivo:** `crontab.example:3`, `README.md:31`
Ambos usan `>> /var/log/worksearcher.log` (append infinito). Con Playwright + 4 scrapers × 4h = disco lleno en semanas. Cuando el disco se llene, SQLite falla silenciosamente.
**Fix:** `/etc/logrotate.d/worksearcher` (daily, compress, 14 días) antes del deploy.

---

## Importante

### BACK-4 — `save_jobs` usa dos `COUNT(*)` en vez de `cursor.rowcount`
**Archivo:** `worksearcher/storage/database.py:40-64`
Patrón before/after con dos queries. Basta con `cursor = conn.executemany(...)` y retornar `cursor.rowcount`.

### BACK-5 — `DB_PATH` hardcodeado — dificulta tests sin monkeypatch
**Archivo:** `worksearcher/storage/database.py:10`, `worksearcher/main.py:61`
`get_connection()` siempre abre un archivo en disco. Pasar `db_path` como parámetro a `_run_pipeline` permitiría tests con `tmp_path` sin monkeypatch.

### BACK-6 — Playwright reutiliza `page` entre keywords — una CAPTCHA bloquea todo
**Archivo:** `worksearcher/scrapers/computrabajo_scraper.py:44-94`
Si `page.goto()` es bloqueado en keyword N, las siguientes keywords corren en la misma página comprometida.
**Fix:** `page = context.new_page()` por keyword (y cerrar después).

### BACK-7 — CyberSecJobs no extrae `company` — fingerprints menos robustos
**Archivo:** `worksearcher/scrapers/cybersecjobs_scraper.py:43-51`
`company=""` en todos los jobs de isecjobs. El fingerprint es `sha256(title + "" + url)`.

### BACK-8 — Versión Meta API hardcodeada
**Archivo:** `worksearcher/notifier/whatsapp.py:9`
`v21.0` embebido en la URL. Meta depreca versiones cada ~2 años.
**Fix:** `META_API_VERSION: str = "v21.0"` en `Settings`.

### BACK-9 — jobspy fallback silencioso a `LINKEDIN` para fuentes desconocidas
**Archivo:** `worksearcher/scrapers/jobspy_scraper.py:38`
`_SOURCE_MAP.get(source_str, JobSource.LINKEDIN)` — fuentes nuevas de jobspy se atribuyen a LinkedIn sin warning.

### BACK-10 — Sin timeout por scraper — Playwright colgado bloquea el pipeline
**Archivo:** `worksearcher/main.py:44`
`asyncio.gather` no tiene timeout. Un navegador colgado bloquea indefinidamente, y el siguiente cron lanza otro proceso encima.
**Fix:** `asyncio.wait_for(scraper(config), timeout=120)` por scraper.

### DEVOPS-3 — Playwright requiere `install-deps` en Ubuntu — no documentado
**Archivo:** `README.md:13`
`playwright install chromium` no instala dependencias del sistema (`libnss3`, `libatk-bridge2.0-0`, etc.). En VPS fresh Ubuntu 22.04 los scrapers LatAm fallarán silenciosamente.
**Fix:** Agregar `playwright install-deps chromium` al setup, o crear `deploy/setup.sh`.

### DEVOPS-4 — User-Agent macOS en VPS Linux — fingerprint inconsistente
**Archivo:** `worksearcher/scrapers/computrabajo_scraper.py:31-33`, `bumeran_scraper.py:38-40`
Ambos usan `Macintosh; Intel Mac OS X` en VPS Linux. Cloudflare/DataDome detecta la contradicción OS vs TCP stack.
**Fix:** Cambiar a User-Agent Linux Chrome.

### DEVOPS-5 — Sin retry en notificación WhatsApp — jobs guardados pero no notificados
**Archivo:** `worksearcher/notifier/whatsapp.py:41-50`, `worksearcher/main.py:71-73`
Un 5xx transitorio de Meta causa que los jobs queden en DB pero el usuario nunca sea notificado. La siguiente ejecución los ignorará (ya están en `seen_fingerprints`).
**Fix:** Tabla `pending_notifications` o columna `notified` en `jobs`.

### DEVOPS-6 — Dependencias sin pin — `jobspy` desde git HEAD sin SHA
**Archivo:** `requirements.txt:1`
`git+https://github.com/Bunsly/JobSpy.git` instala HEAD en cada deploy. Un breaking change upstream rompe LinkedIn/Indeed/Glassdoor silenciosamente.
**Fix:** Pin a commit SHA específico + `uv pip compile requirements.txt -o requirements.lock`.

### QA-1 — `FakeSettings` duplicado en 3 archivos de tests — divergencia garantizada
**Archivo:** `tests/test_pipeline.py:27`, `tests/test_scrapers.py:72`, `tests/test_whatsapp.py:8`
Tres clases distintas implementando parcialmente `Settings`. Un campo nuevo en `Settings` que el pipeline use causará `AttributeError` que los tests no detectarán.
**Fix:** `conftest.py` con un único `FakeSettings` que implemente la interfaz completa.

### QA-2 — 4 scrapers sin cobertura de tests
No hay tests para: `cybersecjobs_scraper.py`, `bumeran_scraper.py`, `computrabajo_scraper.py`, `jobspy_scraper.py` (lógica de row-mapping).
CyberSecJobs en particular acaba de ser reescrito y no tiene protección ante regresiones.

### QA-3 — `get_connection` mockeado en pipeline tests — no verifica factory real
**Archivo:** `tests/test_pipeline.py:60,92,119,151,178`
El lambda de reemplazo omite `PRAGMA journal_mode=WAL`. Si `get_connection` gana configuración importante, los tests no lo detectarán.

### QA-4 — Payload de WhatsApp nunca verificado en tests
**Archivo:** `tests/test_whatsapp.py:77-84`
`test_send_digest_returns_true_on_success` solo verifica el valor de retorno. No verifica que el `Authorization` header, el `to` ni el body sean correctos.

---

## Menor

### BACK-11 — `requirements.txt` sin upper bounds ni lockfile
Cualquier major bump de pydantic/httpx puede romper silenciosamente.

### BACK-12 — `bumeran_scraper` tiene `page.wait_for_timeout(3_000)` hardcodeado
**Archivo:** `worksearcher/scrapers/bumeran_scraper.py:54`
Sleep fijo de 3s. Frágil en conexiones lentas, desperdicio en rápidas.
**Fix:** `page.wait_for_selector(...)` con selector relevante.

### BACK-13 — `_slug()` duplicada en Bumeran y Computrabajo
Misma función en dos archivos. Un bug fix en una no aplica a la otra.
**Fix:** Mover a `worksearcher/core/utils.py`.

### BACK-14 — `SCRAPE_INTERVAL_HOURS` nunca se lee — confunde operadores
**Archivo:** `worksearcher/config.py:24`
El campo existe en config pero nada lo lee. El cron siempre es `*/4` hardcodeado.
**Fix:** Documentar en `.env.example` que es referencia humana, no config activa.

### DEVOPS-7 — DB en raíz del repo — `git clean -fd` destruye historial de dedup
**Archivo:** `worksearcher/storage/database.py:10`
`worksearcher.db` vive junto al código. En la VPS, mover a `/var/lib/worksearcher/`.

### DEVOPS-8 — Sin `pyproject.toml` — sin config de pytest ni linter
No hay `ruff`, no hay `pre-commit`, no hay `asyncio_mode = "strict"` en pytest.
Un test async sin `@pytest.mark.asyncio` falla silenciosamente.

### QA-5 — `test_fingerprint_is_derived_not_stored` es duplicado vacuo
**Archivo:** `tests/test_models.py:59-78`
Mismo assert que `test_same_data_produces_same_fingerprint`. No verifica lo que dice su nombre.

### QA-6 — Keyword `"soc"` matchea "Social Media Manager" (substring)
**Archivo:** `worksearcher/core/filters.py` — comportamiento no documentado ni testeado.
¿Intencional o bug? Necesita test que documente la decisión.

### QA-7 — `test_job_source_enum_values` solo verifica 5 de 9 miembros
**Archivo:** `tests/test_models.py:51-56`
WWR, CYBERSECJOBS, COMPUTRABAJO, BUMERAN no verificados.

---

## Resumen por prioridad de ataque

| # | Item | Impacto |
|---|------|---------|
| 1 | BACK-1 / DEVOPS-1 (fingerprint scan + logrotate) | OOM + disco lleno en VPS |
| 2 | BACK-2 (is_remote falso en LatAm) | Jobs no-remotos en WhatsApp |
| 3 | DEVOPS-1 (CI/CD) | Regresiones sin detección |
| 4 | BACK-10 / DEVOPS-2 (timeout + logrotate) | Pipeline colgado |
| 5 | QA-1 (conftest.py) | Tests que no detectan regresiones |
| 6 | DEVOPS-6 (pin dependencias) | Deploy roto por upstream |
