# feat-010: OCC Scraper

## 1. Propósito
Añadir OCC (occ.com.mx) como nueva fuente de empleos. OCC es el mayor portal de empleo en México y filtra trabajos remotos server-side vía URL path, lo que simplifica el scraping (sin marcadores de texto).

## 2. Comportamiento esperado
- El scraper itera sobre `config.occ_search_terms_list` (campo independiente `OCC_SEARCH_TERMS`).
- Por cada término construye la URL: `https://www.occ.com.mx/empleos/de-{slugify(term)}/tipo-home-office-remoto/`
- El filtro remoto está embebido en el path — OCC devuelve sólo empleos home office/remoto sin necesidad de verificar texto en las tarjetas.
- Extrae: título, empresa, URL de cada tarjeta de empleo.
- Retorna `list[Job]` con `source=JobSource.OCC, is_remote=True`.
- El scraper se registra en `_ALL_SCRAPERS` y `_KNOWN_SCRAPERS` siguiendo el patrón de Bumeran/Computrabajo.

## 3. Scope
**In**: Playwright scraper, config fields, JobSource enum, registry en main.py, tests de config + URL builder.
**Out**: Tests de parsing HTML (mismo patrón que Bumeran/Computrabajo — lógica Playwright no unit-testable).

## 4. Decisiones de diseño
- `OCC_SEARCH_TERMS` independiente — mismos defaults que Bumeran pero desacoplado para permitir divergencia futura.
- Remote vía URL path `/tipo-home-office-remoto/` — OCC filtra server-side, no se necesita `_REMOTE_MARKERS`.
- Playwright — ya es dependencia, patrón probado en 2 scrapers LatAm existentes.
- Un `_build_url(term)` puro y exportable — único punto testable sin Playwright.

## 5. Criterios de verificación
- [ ] `JobSource.OCC == "occ"`
- [ ] `Settings().occ_search_terms_list` retorna lista correcta desde `OCC_SEARCH_TERMS`
- [ ] `"occ"` presente en `_KNOWN_SCRAPERS` y `ENABLED_SCRAPERS` default
- [ ] `_build_url("desarrollador")` retorna `https://www.occ.com.mx/empleos/de-desarrollador/tipo-home-office-remoto/`
- [ ] `_build_url("seguridad informatica")` retorna URL con slug `seguridad-informatica`
- [ ] OCC no tiene `_REMOTE_MARKERS` (no se necesitan)
- [ ] `"occ"` en `_ALL_SCRAPERS` en main.py
- [ ] Todos los tests existentes siguen pasando (no regresiones)
- [ ] `ruff check` + `ruff format` sin violaciones

## 6. Archivos afectados
| Acción | Archivo |
|--------|---------|
| Modify | `worksearcher/core/models.py` |
| Modify | `worksearcher/config.py` |
| Create | `worksearcher/scrapers/occ_scraper.py` |
| Modify | `worksearcher/main.py` |
| Modify | `tests/conftest.py` |
| Modify | `tests/test_scrapers.py` |
| Modify | `tests/test_pipeline.py` |
| Modify | `.env.example` |
| Modify | `CLAUDE.md` |
