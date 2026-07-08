# refactor-017: Módulo compartido para los 3 scrapers Playwright LatAm

## 1. Propósito
`bumeran_scraper.py`, `computrabajo_scraper.py` y `occ_scraper.py` nacieron de
copy-paste y ya divergieron de forma silenciosa (hallazgos de code review,
python-reviewer 2026-07-08):
- Boilerplate de `chromium.launch(...)` + `browser.new_context(...)` +
  stealth init script idéntico byte-por-byte en los 3 archivos.
- Chequeo de bloqueo 403 presente en Computrabajo y OCC, **ausente en Bumeran**
  — si Bumeran empieza a bloquear, quema todos los términos de búsqueda
  contra una página de bloqueo en vez de abortar temprano como sus hermanos.
- Parsing de título/empresa por heurística de texto duplicado entre Bumeran y
  OCC, con umbrales que ya divergieron (`len>5` vs `len>3`, filtro
  "Publicado" solo en Bumeran). El review original también reportó un
  supuesto bug en `lines.index(title)` (re-búsqueda de la primera ocurrencia
  del string) — **verificado con permutaciones exhaustivas y descartado**:
  matemáticamente `next()` y `.index()` convergen siempre al mismo índice
  para este predicado (si el string en la posición `i` satisface el
  predicado, cualquier ocurrencia idéntica anterior también lo satisfaría,
  y `next()` ya la habría elegido primero). El problema real es solo la
  duplicación + divergencia de umbrales, no una corrupción de datos.

## 2. Comportamiento esperado
Nuevo módulo `worksearcher/scrapers/_playwright_common.py`:
- `launch_stealth_browser(playwright) -> Browser` — mismo `chromium.launch`
  con los mismos args anti-detección, extraído literal de los 3 archivos.
- `new_stealth_context(browser) -> BrowserContext` — mismo `new_context` (UA
  Linux Chrome, viewport, `locale="es-MX"`) + init script `webdriver=undefined`.
- `raise_if_blocked(page) -> None` — mismo chequeo `"403" in page.title() or
  "Forbidden" in page.title()`, `raise RuntimeError(...)`.
- `parse_title_and_company(raw_text: str) -> tuple[str, str]` — reemplaza la
  lógica duplicada de `bumeran_scraper.py`/`occ_scraper.py` con una sola
  implementación (vía `enumerate(lines)`, equivalente en comportamiento al
  `lines.index()` original — ver nota de verificación arriba, no es un fix
  de bug sino de duplicación). Unifica el umbral al más estricto (`len > 5`)
  y el filtro `"Publicado"` (ambos ya presentes en Bumeran, ahora aplican
  también a OCC).

Los 3 scrapers importan y usan estas 4 funciones en vez de su copia local.
`computrabajo_scraper.py` no usa `parse_title_and_company` (ya usa selectores
CSS propios — `h2 a`, `p.dFlex a` — más robustos, sin cambios ahí). `bumeran_scraper.py`
gana el chequeo `raise_if_blocked` que no tenía.

## 3. Scope
**In**: extracción de las 4 funciones a `_playwright_common.py`, actualización
de los 3 scrapers para consumirlas, tests unitarios de
`parse_title_and_company` (pura, testable sin Playwright) y de
`raise_if_blocked` (con un objeto `page` fake).
**Out**: arreglar la causa raíz de por qué OCC no encuentra postings
individuales (estructura de URL rota — ver `errores-conocidos.md`, sigue
opt-in). Migrar Bumeran/OCC a selectores CSS estructurales como Computrabajo
— requeriría verificar en vivo la estructura HTML actual de ambos sitios;
posible mejora futura, no bloqueante para este refactor de deduplicación.

## 4. Decisiones de diseño
- **Extraer funciones puras + helpers de setup, no una clase orquestadora.**
  Los 3 scrapers ya tienen su propio loop de reintentos/keywords con
  diferencias reales (Bumeran reusa una sola `page`, Computrabajo/OCC abren
  una por keyword) — forzar una clase común escondería esas diferencias
  legítimas. Extraer solo lo que es literalmente idéntico mantiene cada
  scraper legible por separado.
- **`parse_title_and_company` no intenta usar CSS selectors.** Verificar en
  vivo si bumeran.com.mx/occ.com.mx exponen selectores estructurales
  equivalentes a los de Computrabajo es trabajo adicional no relacionado con
  el bug reportado (duplicación + `lines.index` bug) — se deja como mejora
  futura documentada, no se mezcla en este refactor.
- **Umbral unificado al más estricto (`len > 5`).** Preferir menos falsos
  positivos (títulos de 4-5 caracteres son raros; líneas cortas sueltas en
  una tarjeta sí son comunes — badges, "Nuevo", etc.).

## 5. Criterios de verificación
- [ ] `parse_title_and_company("Backend Dev\nAcme Corp")` → `("Backend Dev", "Acme Corp")`
- [ ] `parse_title_and_company` filtra líneas cortas y líneas "Publicado ..."
      igual que el comportamiento actual de Bumeran (umbral unificado)
- [ ] `raise_if_blocked(page)` lanza `RuntimeError` cuando `page.title()`
      contiene "403" o "Forbidden"; no lanza en título normal
- [ ] `bumeran_scraper.py` llama `raise_if_blocked` (chequeo nuevo que no tenía)
- [ ] Los 3 scrapers importan desde `_playwright_common` — cero duplicación
      del boilerplate de launch/context
- [ ] `uv run pytest` sin regresiones
- [ ] Verificación manual en vivo: bumeran y computrabajo siguen encontrando
      jobs reales tras el refactor (occ ya está opt-in/roto, sin cambio de
      estado)
- [ ] `ruff check` + `ruff format` sin violaciones

## 6. Archivos afectados
| Acción | Archivo |
|--------|---------|
| Create | `worksearcher/scrapers/_playwright_common.py` |
| Modify | `worksearcher/scrapers/bumeran_scraper.py` |
| Modify | `worksearcher/scrapers/computrabajo_scraper.py` |
| Modify | `worksearcher/scrapers/occ_scraper.py` |
| Modify | `tests/test_scrapers.py` |
