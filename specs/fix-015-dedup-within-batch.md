# fix-015: Deduplicar jobs dentro del mismo batch antes de notificar

## 1. Propósito
`deduplicate()` sólo filtra fingerprints ya persistidos en BD (`seen`) — nunca
deduplica repetidos *dentro* del batch actual (`relevant`). Si dos scrapers (o
dos pases del mismo scraper, ej. `jobspy_scraper.py` con `SEARCH_LOCAL_ENABLED`
haciendo un pase remote + uno local) traen el mismo posting, ambas copias
sobreviven `filter_jobs` y `deduplicate` (ninguna está aún en BD) y
`send_digest(new_jobs, config)` las renderiza **dos veces en el mismo mensaje
de WhatsApp**. Detectado en code review (python-reviewer, 2026-07-08).

## 2. Comportamiento esperado
- Después de `filter_jobs(...)` en `main.py::_run_pipeline`, antes de calcular
  `candidate_fps`, el batch `relevant` se deduplica por `fingerprint`
  conservando la primera ocurrencia.
- Si `relevant` no tiene fingerprints repetidos, el comportamiento es idéntico
  al actual (no-op).
- El fix vive en el pipeline (`main.py`), no en `deduplicate()` — `deduplicate`
  mantiene su contrato actual ("filtra contra un set externo de vistos");
  mezclar ambas responsabilidades en una función la haría menos clara.

## 3. Scope
**In**: dedup por fingerprint del batch `relevant` en `_run_pipeline`, test que
reproduce el bug (dos scrapers devolviendo el mismo job) y confirma que
`send_digest` sólo recibe una copia.
**Out**: cambiar `jobspy_scraper.py` para evitar la superposición remote/local
en origen — eso sigue siendo válido (dos búsquedas distintas pueden
legítimamente traer el mismo posting), el fix correcto es deduplicar en el
punto de convergencia (el pipeline), no en cada scraper individual.

## 4. Decisiones de diseño
- **Dedup en el pipeline, no en cada scraper.** Cualquier combinación futura
  de scrapers puede producir el mismo solapamiento (ej. CyberSecJobs vía
  foorilla y GetOnBoard listando el mismo posting agregado por ambos boards).
  Centralizar el dedup en `_run_pipeline` cubre todos los casos con un solo
  cambio, en vez de parchear cada scraper por separado.
- **`dict.fromkeys`-style dedup (`{j.fingerprint: j for j in relevant}.values()`),
  no un `set` de fingerprints con loop manual.** Una sola línea, preserva el
  primer job visto por cada fingerprint, mismo resultado con menos código.

## 5. Criterios de verificación
- [ ] Dos scrapers fake devolviendo un `Job` con el mismo `title`+`company`+`url`
      (mismo fingerprint) → `send_digest` se llama con una lista de longitud 1
- [ ] La misma prueba confirma que sólo se inserta 1 fila en SQLite (no 2)
- [ ] Batch sin duplicados → comportamiento sin cambios (test existente
      `test_pipeline_saves_new_jobs` sigue pasando tal cual)
- [ ] Todos los tests existentes siguen pasando
- [ ] `ruff check` + `ruff format` sin violaciones

## 6. Archivos afectados
| Acción | Archivo |
|--------|---------|
| Modify | `worksearcher/main.py` |
| Modify | `tests/test_pipeline.py` |
