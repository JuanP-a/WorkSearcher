# Convenciones — WorkSearcher

## Naming

| Elemento | Convención | Ejemplo |
|----------|-----------|---------|
| Variables / funciones | `snake_case` | `filter_jobs`, `posted_at` |
| Clases | `PascalCase` | `Job`, `Settings`, `JobSource` |
| Constantes de módulo | `UPPER_SNAKE` | `HIMALAYAS_API`, `_MAX_JOBS_PER_MESSAGE` |
| Privado de módulo | prefijo `_` | `_build_message`, `_SOURCE_MAP` |
| Predicados de filtro | `is_<criterio>` | `is_recent`, `is_not_blacklisted` |
| Scrapers | `<plataforma>_scraper.py` | `himalayas_scraper.py` |

---

## Patrones que usamos

### Interfaz de scraper (obligatoria)
```python
async def scrape(config: Settings) -> list[Job]:
    try:
        ...
    except Exception as exc:
        logger.error("NombreScraper scraper failed: %s", exc)
        return []
```
- Siempre devuelve `[]` en fallo — nunca propaga excepciones al pipeline.
- Per-item `try/except` interno para aislar items malformados.
- Usa el mismo `logger = logging.getLogger(__name__)` en cada módulo.

### Filtros puros
```python
def is_<criterio>(job: Job, threshold) -> bool:
    if job.<campo> is None:
        return True  # fail-open: dato desconocido → pasa
    return job.<campo> <operación> threshold
```
Todos los filtros son funciones puras sin I/O. `None` en el campo relevante siempre pasa.

### Configuración
- Todos los tunables en `.env` → `Settings` (pydantic-settings).
- Listas en Settings: campo `str` comma-separated + `@property` que parsea a `list[str]`.
- `FakeSettings` en `tests/conftest.py` replica la misma interfaz para tests.

### Tests
- Framework: `pytest` + `pytest-asyncio` (modo `strict`).
- Mocks HTTP: `respx` — intercepta al nivel de transporte, no parchea internos.
- `langdetect.detect_langs` siempre se mockea en tests (no-determinista por diseño).
- Mock target: `"worksearcher.core.filters.detect_langs"` (el nombre importado).
- Helpers: `_job(title, description, is_remote)` para construir fixtures inline.
- TDD: test rojo → implementar → test verde → refactor.

---

## Patrones prohibidos

| Prohibido | Por qué | Alternativa |
|-----------|---------|-------------|
| Excepciones desde scraper | rompe `asyncio.gather` | devolver `[]` |
| `detect()` de langdetect | sin umbral de confianza | `detect_langs()[0].prob >= 0.8` |
| `int()` antes de `float()` en salary | crash con strings decimales | `float()` directo |
| `cursor.rowcount` tras `executemany + INSERT OR IGNORE` | valor indefinido en CPython | `SELECT changes()` |
| Mock con `MagicMock` sin `.lang`/`.prob` en tests de idioma | tests pasan con datos incorrectos | usar `_fake_lang(lang, prob)` |
| Hardcodear `is_remote=True` en scrapers | filtra mal en pipeline | detectar desde texto |
| `timedelta.days` para comparar antigüedad | trunca sub-día (off by 24h) | `total_seconds()` |
| Secrets en código | obviamente | `.env` + `pydantic-settings` |

---

## Commits

Formato: `type: descripción concisa en inglés`

| Type | Cuándo |
|------|--------|
| `feat` | nueva funcionalidad |
| `fix` | corrección de bug |
| `test` | solo tests |
| `docs` | solo documentación |
| `refactor` | sin cambio de comportamiento |
| `ci` | cambios en workflows / CI |
| `chore` | dependencias, config |

Regla: cada commit = una unidad reversible y coherente. No mezclar refactor con feature.

---

## Linter

```bash
uvx ruff check worksearcher/ tests/   # verificar
uvx ruff check --fix worksearcher/ tests/  # autofix
```

Reglas activas: E, W, F (pyflakes), I (isort), B (bugbear), UP (pyupgrade).
`B` relajado en `tests/` (`per-file-ignores`).
`E501` ignorado (líneas largas — no hay formatter configurado).
