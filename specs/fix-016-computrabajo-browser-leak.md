# fix-016: Fuga de proceso Chromium en Computrabajo por falta de try/finally

## 1. Propósito
`computrabajo_scraper.py::_blocking_scrape` llama `browser.close()` al final
del bloque `with sync_playwright() as p:`, **fuera de cualquier `try/finally`**.
`bumeran_scraper.py` y `occ_scraper.py` sí envuelven todo el uso del browser en
`try: ... finally: browser.close()`. Si algo lanza excepción antes de llegar a
esa línea (`browser.new_context()`, `context.add_init_script()`, o
`context.new_page()` — este último se llama fuera de cualquier `try` en el
loop), el proceso Chromium queda huérfano en el VPS. Detectado en code review
(python-reviewer, 2026-07-08).

## 2. Comportamiento esperado
- `_blocking_scrape` envuelve desde `context = browser.new_context(...)` hasta
  el final del loop `for keyword in ...` en un único `try`, con
  `finally: browser.close()` — mismo patrón exacto que `bumeran_scraper.py`.
- Ningún cambio de comportamiento en el happy path: mismos jobs, mismos logs,
  mismo manejo de 403/timeout por keyword (los `try/except` internos por
  keyword no se tocan).
- Si `browser.new_context()`, `context.add_init_script()`, o `context.new_page()`
  lanzan una excepción no manejada, `browser.close()` se ejecuta igual antes
  de que la excepción se propague hacia `scrape()` (que ya la captura y
  retorna `[]`).

## 3. Scope
**In**: refactor estructural de `_blocking_scrape` (indentación + try/finally),
verificación manual end-to-end contra computrabajo.com.
**Out**: unificar el boilerplate de Playwright entre los 3 scrapers LatAm en un
módulo compartido (`_playwright_common.py`) — señalado en el mismo review como
mejora de impacto medio, se aborda en un fix separado.

## 4. Decisiones de diseño
- **Sin test automatizado nuevo.** Ya es convención documentada del proyecto
  que el flujo Playwright completo de Bumeran/Computrabajo/OCC no es
  unit-testable sin mockear `sync_playwright` (ver scope de
  `specs/feat-010-occ-scraper.md`: "Out: Tests de parsing HTML — lógica
  Playwright no unit-testable"). Mockear el árbol completo de
  `sync_playwright().chromium.launch().new_context().new_page()` solo para
  probar que `finally` corre añade complejidad de mocking desproporcionada
  al riesgo — el fix es un cambio estructural de 5 líneas, verificable por
  inspección directa contra el patrón ya probado de `bumeran_scraper.py`.
- **Verificación: correr el scraper real contra computrabajo.com** antes de
  hacer commit — confirma que el refactor no rompe el happy path (mismos
  selectores, mismo flujo, solo cambia el manejo de errores).

## 5. Criterios de verificación
- [ ] `browser.close()` vive dentro de un `finally` que envuelve todo el uso
      de `context`/`page` (paridad estructural con `bumeran_scraper.py`)
- [ ] `uv run pytest` — sin regresiones (no se tocan tests existentes, ninguno
      ejercía el flujo Playwright completo)
- [ ] Corrida manual contra computrabajo.com real retorna `list[Job]` no vacío
- [ ] `ruff check` + `ruff format` sin violaciones

## 6. Archivos afectados
| Acción | Archivo |
|--------|---------|
| Modify | `worksearcher/scrapers/computrabajo_scraper.py` |
