# fix-013: Verificar HackerNews y WeWorkRemotely — HN usa thread obsoleto

## 1. Propósito
Verificar en vivo que los scrapers de HackerNews y We Work Remotely siguen
funcionando contra sus fuentes reales (ninguno había sido re-verificado desde
su implementación original). La verificación de WWR confirma que está sano.
La verificación de HackerNews encontró un bug real: el scraper trae un thread
de **marzo 2020**, no el thread mensual actual.

## 2. Comportamiento esperado

### HackerNews — bug encontrado y corregido
`HN_SEARCH_URL` apunta a `/api/v1/search` (Algolia), que ordena por
**relevancia de texto**, no por fecha. Con `hitsPerPage=1`, el hit más
"relevante" para la query `"Ask HN: Who is hiring?"` es un thread de marzo
2020 (verificado en vivo: `objectID=22665398`, contenido menciona "Coronavirus
Economy"), no el thread de julio 2026 (`objectID=48747976`). El scraper lleva
tiempo indeterminado trayendo comentarios de un thread de hace 6 años en vez
del actual.

**Fix:** cambiar `HN_SEARCH_URL` a `https://hn.algolia.com/api/v1/search_by_date`
— mismo endpoint de Algolia, mismos parámetros (`query`, `tags`,
`hitsPerPage`), pero ordenado por fecha descendente. Verificado en vivo:
con `search_by_date` el primer hit es `48747976` — "Ask HN: Who is hiring?
(July 2026)", `created_at=2026-07-01`.

### We Work Remotely — verificado, sin cambios
`WWR_RSS_URL` responde 200, XML válido, ~820KB, items con `pubDate` del día
de la verificación (2026-07-07). El parsing (`_parse_title_and_company`,
extracción de `link`/`description`/`pubDate`) sigue siendo correcto contra
la estructura RSS real. No se requiere ningún cambio de código — se documenta
el resultado de la verificación.

## 3. Scope
**In**: Cambio de endpoint de HackerNews (`search` → `search_by_date`),
actualización de tests que mockean la URL, documentación de la verificación
de ambos scrapers en `errores-conocidos.md`.
**Out**: Cualquier otro cambio de parsing/lógica en HN o WWR — ambos ya
producen `Job` válidos una vez corregido el endpoint de HN.

## 4. Decisiones de diseño
- **`search_by_date`, no un `numericFilters` sobre `/search`.** Algolia ya
  expone un endpoint dedicado a orden cronológico — es la solución idiomática
  documentada por HN Algolia API, más simple que forzar sort vía filtros en
  el endpoint de relevancia.
- **No se cachea ni persiste el `thread_id` esperado.** Cada corrida
  simplemente pide el hit más reciente — coherente con el resto del pipeline
  (sin estado entre corridas, ver ADR-004 sobre cron sin estado).

## 5. Criterios de verificación
- [ ] `HN_SEARCH_URL == "https://hn.algolia.com/api/v1/search_by_date"`
- [ ] Test mockea `search_by_date` (no `search`) y confirma que el scraper
      lo usa
- [ ] Todos los tests existentes de HackerNews siguen pasando (fixtures
      actualizadas al nuevo endpoint)
- [ ] `uv run pytest` completo sin regresiones
- [ ] `ruff check` + `ruff format` sin violaciones
- [ ] `errores-conocidos.md` documenta: (a) el bug de HN y su fix,
      (b) que WWR fue verificado sano sin cambios

## 6. Archivos afectados
| Acción | Archivo |
|--------|---------|
| Modify | `worksearcher/scrapers/hackernews_scraper.py` |
| Modify | `tests/test_scrapers.py` |
| Modify | `docs/contexto/errores-conocidos.md` |
