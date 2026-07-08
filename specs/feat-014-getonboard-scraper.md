# feat-014: GetOnBoard (getonbrd.com) scraper

## 1. Propósito
Añadir GetOnBoard (getonbrd.com) como fuente LatAm — job board curado, salarios
en USD, moderación manual, con categorías dedicadas de programación y
ciberseguridad. A diferencia de OCC/Bumeran/Computrabajo, GetOnBoard renderiza
el listado completo server-side — no requiere Playwright.

## 2. Comportamiento esperado
- El scraper itera sobre `config.getonboard_categories_list` (campo
  `GETONBOARD_CATEGORIES`, default `"programming,cybersecurity,sysadmin-devops-qa"`).
- Por cada categoría: `GET https://www.getonbrd.com/jobs/{categoria}` (httpx,
  sin Playwright — verificado en vivo: HTML completo con jobs ya renderizado).
- Cada tarjeta de empleo es un `<a class="results-item" href="...">`. Se extrae:
  - `title`: `h4.results-list-title strong`
  - `company`: primer `strong` dentro de `div.results-list-info div.size0`
  - `url`: atributo `href` (ya absoluto)
  - `description`: atributo `title` del `<a>` (blurb corto, puede estar vacío)
- **Filtro remoto: el badge `i.perk-remote_full`, no el sufijo `-remote` de la
  URL.** Se verificó en vivo que GetOnBoard sufija `-remote` en las URLs de
  *todos* los jobs de una categoría (incluyendo híbridos) — no es señal
  confiable. El badge `perk-remote_full` (tooltip "Fully remote") sí distingue
  correctamente full-remote de híbrido/on-site. Jobs sin ese badge se descartan.
- `location="Remote"`, `is_remote=True`, `source=JobSource.GETONBOARD` para
  los jobs que pasan el filtro.
- Dedup vía `seen_urls` entre categorías (un job puede aparecer en más de una,
  ej. un DevOps Engineer en `programming` y `sysadmin-devops-qa`).
- Sin paginación — sólo la primera carga por categoría (~22-330 jobs por
  categoría en la verificación en vivo, de los cuales ~15-30% son fully
  remote). Suficiente dado `SCRAPE_INTERVAL_HOURS=4` + deduplicación global
  por fingerprint.
- Si una categoría falla (HTTP error) o no tiene `a.results-item`, se loguea
  warning y se continúa con las demás categorías (no aborta el scraper completo).
- `follow_redirects=False` (mismo patrón de seguridad que el resto de scrapers httpx).
- Se registra en `_ALL_SCRAPERS`, `_KNOWN_SCRAPERS` y **sí** en `ENABLED_SCRAPERS`
  por default (a diferencia de OCC) — verificado en vivo que funciona sin
  Playwright ni bloqueos anti-bot.

## 3. Scope
**In**: Scraper httpx+BS4, `JobSource.GETONBOARD`, config field
`GETONBOARD_CATEGORIES`, registro en `main.py`, tests de parsing con HTML
fixture mockeado, tests de configuración.
**Out**: Paginación más allá de la primera carga. Parseo de salario (formato
variable, no visible en la tarjeta de listado — sólo en el detalle del job).
Ciudades/on-site (`SEARCH_LOCAL_ENABLED`) — GetOnBoard no tiene un concepto de
"ciudad de búsqueda" equivalente a Bumeran/Computrabajo/OCC.

## 4. Decisiones de diseño
- **httpx + BeautifulSoup, no Playwright.** Verificado en vivo: el HTML de
  `/jobs/{categoria}` ya contiene todas las tarjetas de empleo renderizadas
  server-side (sin contenido cargado vía JS). Más liviano y rápido que el
  patrón Playwright usado por Bumeran/Computrabajo/OCC.
- **Categorías fijas vía config, no términos de búsqueda libres.** GetOnBoard
  organiza su listado por categoría (`/jobs/programming`,
  `/jobs/cybersecurity`, `/jobs/sysadmin-devops-qa`), no por query de texto —
  un campo `*_SEARCH_TERMS` no aplica aquí. `GETONBOARD_CATEGORIES` sigue el
  mismo patrón de configurabilidad (CSV) que el resto de campos de `Settings`.
- **Badge `perk-remote_full` como filtro remoto, no el sufijo de URL.** Fue el
  hallazgo clave de la verificación en vivo — confiar en la URL habría incluido
  jobs híbridos incorrectamente marcados como remotos.
- **Habilitado por default (no opt-in como OCC).** A diferencia de OCC, se
  verificó en vivo end-to-end antes de escribir código: HTML estático,
  selectores estables, sin bloqueo anti-bot detectado.

## 5. Criterios de verificación
- [ ] `JobSource.GETONBOARD == "getonboard"`
- [ ] `Settings().getonboard_categories_list == ["programming", "cybersecurity", "sysadmin-devops-qa"]`
- [ ] `"getonboard"` presente en `_KNOWN_SCRAPERS` y en `ENABLED_SCRAPERS` default
- [ ] Con HTML mockeado (fixture con 1 job fully-remote + 1 híbrido), el
      scraper retorna sólo el job fully-remote
- [ ] `company` y `title` se extraen correctamente del fixture
- [ ] Jobs duplicados entre categorías se deduplican (mismo `url`)
- [ ] Si una categoría retorna HTTP error, las demás categorías se siguen procesando
- [ ] `"getonboard"` en `_ALL_SCRAPERS` en `main.py`
- [ ] Todos los tests existentes siguen pasando (no regresiones)
- [ ] `ruff check` + `ruff format` sin violaciones

## 6. Archivos afectados
| Acción | Archivo |
|--------|---------|
| Modify | `worksearcher/core/models.py` |
| Modify | `worksearcher/config.py` |
| Create | `worksearcher/scrapers/getonboard_scraper.py` |
| Modify | `worksearcher/main.py` |
| Modify | `tests/conftest.py` |
| Modify | `tests/test_scrapers.py` |
| Modify | `tests/test_pipeline.py` |
| Modify | `.env.example` |
| Modify | `CLAUDE.md` |
