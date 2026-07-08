# fix-011: CyberSecJobs — migrar de isecjobs.com a foorilla.com

## 1. Propósito
isecjobs.com fue dado de baja el 30 jun 2026 (`_ISECJOBS_URL` ahora 404/dead). El scraper `cybersecjobs_scraper.py` retorna `[]` en cada corrida. Reemplazar la fuente por foorilla.com — job board "all coding" con filtro por topic "InfoSec & Privacy" (id 102), que cubre el mismo nicho (cybersecurity/infosec) sin costo.

## 2. Comportamiento esperado
- El scraper mantiene `source=JobSource.CYBERSECJOBS` (no se agrega un `JobSource` nuevo — es un fix de fuente, no una plataforma nueva).
- Flujo HTTP con sesión persistente (`httpx.AsyncClient`, cookies automáticas dentro del `async with`):
  1. `GET https://foorilla.com/` → establece cookie `csrftoken` + `sessionid`.
  2. `POST https://foorilla.com/topics/hiring/` con `topic=102` (InfoSec & Privacy), headers `X-CSRFToken: <csrftoken cookie>`, `Referer: https://foorilla.com/`, `HX-Request: true`.
  3. `POST https://foorilla.com/regions/hiring/` con `remote_only=on`, mismos headers — filtro remoto server-side, persiste en `sessionid`.
  4. `GET https://foorilla.com/hiring/jobs/` con `HX-Request: true` → fragmento HTML con `<li class="list-group-item">` por job (sólo la primera página/"latest", sin paginación — suficiente dado `SCRAPE_INTERVAL_HOURS=4` + deduplicación por fingerprint).
- Por cada `<li class="list-group-item">`: extraer título (texto del `<a class="stretched-link">`), slug de la URL (`hx-get="/hiring/jobs/<slug>/"` → `url = f"https://foorilla.com/hiring/jobs/{slug}/"`), timestamp relativo (ignorar — no parsear a `posted_at`, ver §4).
- `company` queda `""` (vacío) — foorilla oculta el nombre completo de la empresa a usuarios anónimos/free (ver §4, limitación conocida).
- `location="Remote"`, `is_remote=True` siempre (garantizado por el filtro `remote_only` de sesión, no por texto).
- Si cualquier paso de la sesión (GET inicial, POST topic, POST region) falla (status ≠ 200) o el GET final no devuelve `list-group-item`, loguear warning y retornar `[]` — mismo patrón defensivo que el resto de scrapers.
- `follow_redirects=False` en el cliente (no se siguen redirects en ningún paso — ver ADR de seguridad previo sobre SSRF en este mismo scraper).

## 3. Scope
**In**: Reescritura completa de `cybersecjobs_scraper.py` (nueva fuente, mismo `JobSource`), tests con `respx` mockeando los 4 requests de la sesión, actualización de `docs/contexto/errores-conocidos.md` documentando la limitación de `company` vacío.
**Out**: Obtener la URL de aplicación externa real (requiere una request adicional por job a `/hiring/jobs/<id>/apply/` con cookie+referer de sesión — ver §4, decisión de no implementarlo). Paginación más allá de la primera página. Parseo de salario (multi-moneda, fuera de scope). Parseo de `posted_at` desde texto relativo ("4h ago").

## 4. Decisiones de diseño
- **No se resuelve la URL de aplicación externa real.** Se comprobó en vivo que `GET /hiring/jobs/<id>/apply/` sí redirige a la URL externa real (ej. Workday) — pero sólo con cookie de sesión + `Referer` del job detail. Implementarlo agregaría 1-2 requests HTTP extra *por cada job* (con ~50 jobs/corrida, eso son 100+ requests adicionales cada 4h) y reintroduce superficie de redirect-following que el ADR de seguridad previo (SSRF, ver `errores-conocidos.md`) recomendó evitar. En su lugar, `Job.url` apunta a la página interna de foorilla (`/hiring/jobs/<slug>/`) — el usuario hace click, foorilla setea su propia sesión de browser normalmente, y el botón "Apply" funciona igual que en un uso normal del sitio.
- **`company` queda vacío.** foorilla trunca el nombre de la empresa (`"@ M..."`) para usuarios sin sesión PRO+. No hay workaround gratuito. Mismo patrón de degradación que el scraper anterior de isecjobs (`missing_company` ya era tolerado).
- **No se usa jobdataapi.com ni la API PRO+ de foorilla.** Ambos requieren suscripción paga (mínimo $295/mes) — inviable para este proyecto de costo cero (ADR-003). El scraping de la página pública HTML cubre el caso de uso sin costo.
- **Filtro remoto: `remote_only` (checkbox "Only jobs with remote option [R]"), no `work_mode=3` ("Remote Anywhere").** Se prioriza volumen — mismo criterio que ya se aplica en otros scrapers LatAm (Bumeran/Computrabajo/OCC no garantizan "remoto desde cualquier país" sino "con opción remota"). `is_remote=True` es una etiqueta de la fuente, no una verificación geográfica — consistente con el resto del pipeline.
- **Sesión nueva por corrida.** No se persiste `sessionid` entre ejecuciones del scraper — cada `scrape()` abre su propio `httpx.AsyncClient` y repite el flujo de 3 requests (GET + 2×POST) antes de leer el listado. Es barato (4 requests total) y evita manejar expiración de sesión.
- **HTML parseado vía `HX-Request: true`** (fragmento parcial, sin el layout completo) — más liviano para BeautifulSoup que la página completa.

## 5. Criterios de verificación
- [ ] `cybersecjobs_scrape()` ya no referencia `isecjobs.com` en ningún lado
- [ ] Con las 4 requests mockeadas (`respx`), el scraper devuelve `list[Job]` con `source=JobSource.CYBERSECJOBS`, `is_remote=True`, `location="Remote"`, `company=""`
- [ ] `url` de cada job tiene el formato `https://foorilla.com/hiring/jobs/<slug>/`
- [ ] Si el POST de `topic` o `region` falla (status ≠ 200), el scraper retorna `[]` sin excepción
- [ ] Si el GET final no tiene `list-group-item`, retorna `[]` con warning logueado
- [ ] Test que confirma `follow_redirects=False` en el cliente (mismo patrón que `test_cybersecjobs_does_not_follow_redirects` existente)
- [ ] Todos los tests existentes siguen pasando (no regresiones)
- [ ] `ruff check` + `ruff format` sin violaciones
- [ ] `docs/contexto/errores-conocidos.md` documenta: (a) company vacío por paywall, (b) por qué no se resuelve apply URL externa

## 6. Archivos afectados
| Acción | Archivo |
|--------|---------|
| Rewrite | `worksearcher/scrapers/cybersecjobs_scraper.py` |
| Modify | `tests/test_scrapers.py` (reemplazar fixtures/tests de isecjobs por foorilla) |
| Modify | `docs/contexto/errores-conocidos.md` |
