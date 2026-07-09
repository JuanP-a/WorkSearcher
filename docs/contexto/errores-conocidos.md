# Errores conocidos y gotchas — WorkSearcher

## Críticos / Data-corrupting

### `cursor.rowcount` tras `executemany + INSERT OR IGNORE` es indefinido
**Archivo:** `worksearcher/storage/database.py:68`
CPython no garantiza `cursor.rowcount` después de `executemany`. Con `INSERT OR IGNORE`,
los duplicados silenciados tampoco cuentan. El log `"Inserted N jobs"` puede mostrar `-1`.
**Workaround actual:** Ninguno. El pipeline funciona correctamente; solo el log de conteo es incorrecto.
**Fix correcto:** `conn.execute("SELECT changes()").fetchone()[0]` inmediatamente después del `executemany`.

### `get_unnotified_jobs` descarta jobs si `JobSource` no reconoce el valor
**Archivo:** `worksearcher/storage/database.py:88`
El `except Exception: continue` silencia `ValueError` si la columna `source` tiene un valor
que ya no está en el enum (e.g. plataforma eliminada). El job queda en BD con `notified=0` para siempre.
**Workaround:** Ninguno. Si se elimina un `JobSource`, limpiar la BD manualmente.

---

## Comportamientos no obvios

### `langdetect` es no-determinista
Llamadas sucesivas a `detect_langs()` con el mismo texto pueden devolver resultados distintos.
**En tests:** siempre mockear `"worksearcher.core.filters.detect_langs"` — nunca llamar la función real.
**En producción:** el umbral de 0.8 mitiga inconsistencias, pero un mismo job podría pasar o fallar entre runs.

### `salary_min` de RemoteOK es USD anual, no mensual
La API devuelve `salary_min: 60000` para un job de $60k/año ($5k/mes).
El código ya divide por 12, pero cualquier fixture de test debe usar valores anuales realistas
(ej: `60000`), no `1500` (que sería $18k/año).

### `posted_at` de jobspy tiene granularidad de día (no hora)
`date_posted` del DataFrame de jobspy es `datetime.date`, no `datetime`. Se convierte a
`datetime(year, month, day, tzinfo=UTC)` — medianoche UTC. Esto introduce hasta 24h de imprecisión
en el filtro de antigüedad para jobs de LinkedIn/Indeed/Glassdoor.

### `JOBSPY_SEARCH_TERMS` tiene límite duro de 5 términos
El validator en `config.py` lanza `ValueError` en startup si hay más de 5.
El pipeline no arranca — no falla silenciosamente.

### HackerNews: "REMOTE" como substring (case-insensitive)
`is_remote` se detecta buscando `"REMOTE"` en el texto plano del comentario.
No detecta: "remote-friendly", "fully distributed", "async-first", "work from anywhere".
Jobs con esas frases se marcan `is_remote=False` y el pipeline los descarta en `is_relevant`.

### HackerNews usaba `/search` (relevancia) en vez de `/search_by_date` — traía un thread de 2020 (fix-013)
**Archivo:** `worksearcher/scrapers/hackernews_scraper.py`
Verificado en vivo contra la API real de Algolia: `/api/v1/search` ordena por
relevancia de texto, no por fecha. Con `hitsPerPage=1`, la query fija
`"Ask HN: Who is hiring?"` devolvía un thread de **marzo 2020**
(`objectID=22665398`, "Coronavirus Economy") en vez del thread mensual actual.
El scraper llevaba tiempo indeterminado trayendo comentarios de hace 6 años.
Corregido a `/api/v1/search_by_date` (mismos parámetros, orden cronológico).
Verificado: primer hit ahora es `48747976` — "Ask HN: Who is hiring? (July 2026)".

### We Work Remotely — verificado sano (fix-013), sin cambios de código
`https://weworkremotely.com/remote-jobs.rss` responde 200, XML válido (~820KB),
items con `pubDate` del mismo día de la verificación. El parsing
(`_parse_title_and_company`, extracción de `link`/`description`/`pubDate`)
sigue siendo correcto contra la estructura RSS real. Ningún fix necesario.

### Títulos "Senior" sin años explícitos asumen 5 años implícitos (fix-012)
**Archivo:** `worksearcher/core/filters.py::title_implies_senior`
Antes de este fix, un job titulado "Senior Backend Engineer" sin ningún número de años
en el texto pasaba el filtro de experiencia (min_years=None → "accesible"). Ahora, si
el título matchea un patrón senior (EN: senior/sr/staff/principal/lead/architect/director/
head of/chief/vp — ES: líder/arquitecto) y no hay años explícitos, se asume un mínimo
implícito de 5 años antes de comparar contra `MAX_YEARS_EXPERIENCE`. Años explícitos en
el texto (incluido "entry level") siempre tienen prioridad sobre esta heurística.
La heurística sólo mira el título, nunca la descripción, para evitar falsos positivos
de frases como "collaborate with senior engineers" en el cuerpo del job.

### `worksearcher.db` — ubicación configurable via `DB_PATH`
La ruta por defecto (`worksearcher.db`) es relativa al cwd. En VPS se configura vía `.env`:
`DB_PATH=/var/lib/worksearcher/worksearcher.db`. `deploy/setup.sh` crea el directorio con el owner correcto.
En dev local, la BD queda en la raíz del repo (comportamiento anterior, sin cambio).

### Himalayas solo procesa salarios en USD
Si `currency != "USD"`, `min_salary_usd_monthly` queda en `None` aunque el salario esté disponible.
Esto es intencional (no hay conversión de divisas), pero puede hacer que jobs de EUR/GBP pasen
el filtro de salario incluso si pagan menos del mínimo configurado.

### Salario con `salaryPeriod` no reconocido (ej: "hourly") se descarta silenciosamente
El scraper de Himalayas solo maneja `"annual"` y `"monthly"`. Cualquier otro valor emite
un `logger.debug` y deja `min_salary_usd_monthly = None`. El job pasa el filtro de salario.

### OCC (occ.com.mx) está opt-in — no se ejecuta por default
**Archivos:** `worksearcher/config.py:42`, `worksearcher/scrapers/occ_scraper.py`
OCC cambió la estructura de URLs: las páginas de categoría usan `/empleos/` (plural),
y los anuncios individuales están un click más abajo (cada empresa tiene su
"bolsa de trabajo" en `/empleos/bolsa-de-trabajo-COMPANY/`). El selector actual
`a[href*='/empleo/']` (singular con slash) matchea 0 elementos en una página
de búsqueda. Aún corrigiendo el selector a `/empleo` (sin slash), los 95 matches
encontrados son subcategorías y empresas, no ofertas individuales.

**Diagnóstico:** `/tmp/occ_diag2.py` (Playwright + stealth, sincronizado con
`occ_scraper.py` args). Correr si se re-intenta: `scp /tmp/occ_diag2.py deploy@<vps>:/tmp/`
y `sudo -u worksearcher bash -c "cd /opt/worksearcher && .venv/bin/python /tmp/occ_diag2.py"`.

**Caminos posibles** (no implementados):
1. **Click-through:** navegar a cada página de categoría y extraer los links de
   ofertas individuales. Patrón de URL de oferta individual aún desconocido
   (requeriría diag v3 sobre una página de bolsa de trabajo).
2. **API JSON:** OCC probablemente expone un endpoint interno que usa el JS
   de la página. Capturable con Playwright network listener.
3. **Mantener como opt-in** (estado actual): `OCC` removido del default
   `ENABLED_SCRAPERS`. Sigue registrado en `_KNOWN_SCRAPERS` para validación.
   Para re-habilitar: `ENABLED_SCRAPERS=...occ` en `.env`.

**Cobertura LatAm actual sin OCC:** Bumeran y Computrabajo siguen activas
(2 y 32 jobs en última corrida respectivamente). OCC contribuía 0 jobs antes
del cambio, así que la pérdida neta de cobertura es nula.

### CyberSecJobs (foorilla.com): `company` siempre vacío y URL no es el apply link real
**Archivos:** `worksearcher/scrapers/cybersecjobs_scraper.py`
isecjobs.com (fuente anterior) fue dado de baja el 30 jun 2026. El reemplazo,
foorilla.com, tiene dos limitaciones aceptadas por diseño (ver `specs/fix-011-cybersecjobs-foorilla.md`):

1. **`company` vacío.** foorilla trunca el nombre de la empresa (`"@ M..."`) para
   usuarios sin sesión PRO+ ($295+/mes). No hay forma gratuita de obtenerlo.
2. **`url` apunta a la página interna de foorilla, no al apply link externo real.**
   `GET /hiring/jobs/<id>/apply/` sí redirige a la URL externa (ej. Workday), pero
   solo con cookie de sesión + `Referer` del job detail — resolverlo agregaría
   1-2 requests HTTP extra por job (~100+ por corrida) y reintroduce superficie de
   redirect-following que un ADR de seguridad previo (SSRF, ver arriba) recomendó
   evitar. El usuario hace click en el link de foorilla y aplica desde ahí — su
   propio browser genera la sesión necesaria para que el botón "Apply" funcione.

**API paga descartada:** foorilla y su backend (jobdataapi.com) sólo ofrecen API
key vía suscripción — plan más barato $295/mes. Inviable para este proyecto de
costo cero (ADR-003). El scraping de la página pública HTML es gratuito y no
requiere autenticación.

### Overpass API (`overpass-api.de`) responde `406 Not Acceptable` intermitentemente
**Archivo:** `worksearcher/outreach/discovery.py`
Detectado en el primer smoke test en producción (radio 80km). No es un bug de
nuestro request: reproducido localmente contra el endpoint real, mismo 406 sin
importar headers (`Accept`, `Accept-Encoding`, `User-Agent` de browser real) ni
método (GET/POST) ni encoding del body. Confirmado vía búsqueda que es un
problema del lado del servidor que afecta a toda la comunidad de Overpass en
estos días (issue reportado en GitHub del proyecto y foros de OSM), no algo
específico de este cliente.

**Fix:** `OUTREACH_OVERPASS_URL` es ahora un campo de `Settings` (antes era una
constante hardcodeada `OVERPASS_API` en `discovery.py`). Si `overpass-api.de`
vuelve a fallar, cambiar a un mirror en `.env` sin tocar código:
```
OUTREACH_OVERPASS_URL=https://overpass.kumi.systems/api/interpreter
```
**Sin fix de código para el 406 en sí** — es un problema de infraestructura de
terceros fuera de nuestro control; solo se mitigó la rigidez de apuntar a un
único endpoint fijo.

---

## Deuda técnica pendiente

Ver `docs/deuda-tecnica.md` para detalle completo. Sin items pendientes — todos los issues de VPS resueltos.

---

## Tests que no existen (cobertura conocida cero)

- `jobspy_scraper.py` — testear requiere mockear un DataFrame de pandas; nunca se hizo.
- Scrapers Playwright (`computrabajo`, `bumeran`) — solo se testean funciones puras extraídas;
  el flujo completo requiere browser real.
- `_run_pipeline` con config real (`.env`) — solo se testea con `FakeSettings` + mocks.
