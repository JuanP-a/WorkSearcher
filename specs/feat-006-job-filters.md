# Spec: Job Filters — fecha, blacklist, idioma, salario mínimo

## Outcomes

- Jobs con `posted_at` conocido y antigüedad > 30 días son descartados antes de notificación
- Jobs con keywords de blacklist en título o descripción son descartados
- Jobs cuyo idioma detectado no es `en` ni `es` son descartados; si la detección falla, el job pasa
- Jobs con salario mensual conocido en USD por debajo de $1,200 son descartados; si el salario es desconocido, el job pasa
- Los 4 filtros son configurables vía `.env` y tienen defaults funcionales
- Los scrapers Himalayas, RemoteOK y HackerNews populan `posted_at`; jobspy popula `posted_at` desde `date_posted`
- Los scrapers Himalayas y RemoteOK populan `min_salary_usd_monthly` donde el dato está disponible

## Scope Boundaries

### Dentro del alcance
- Filtro de fecha: descartar jobs con `posted_at` > `MAX_JOB_AGE_DAYS` días (default 30)
- Filtro de blacklist: case-insensitive substring match en `title + description`; keywords configurables vía `BLACKLIST_KEYWORDS` en `.env`
- Filtro de idioma: detección con `langdetect` sobre `title + description[:500]`; pasar si confidence < 0.8 o si falla
- Filtro de salario: campo `min_salary_usd_monthly: float | None` en modelo `Job`; filtrar si valor presente y < `MIN_SALARY_USD_MONTHLY`
- Normalización de salario: anual → mensual (/12); otras monedas solo si son USD (campo `currency`)
- Actualizar scrapers: Himalayas (`pubDate`, `minSalary`/`currency`/`salaryPeriod`), RemoteOK (`epoch`, `salary_min`), jobspy (`date_posted`), HackerNews (`created_at_i`)

### Fuera del alcance
- Conversión de divisas (EUR→USD, GBP→USD, etc.) — solo procesar salarios en USD
- Detección de idioma con librería distinta a `langdetect`
- UI o configuración interactiva de filtros
- Filtrado de salario en Remotive, CyberSecJobs, Bumeran, Computrabajo, WWR (no exponen salario estructurado)
- Modificar `jobspy`'s `hours_old` (ya filtra a 24h internamente; se popula `posted_at` pero no se cambia la ventana)

## Constraints & Assumptions

### Técnicas
- Python 3.12, `pydantic` v2, `pydantic-settings`
- Nueva dependencia aprobada: `langdetect` — agregar a `pyproject.toml`
- Idiomas permitidos: `["en", "es"]` — configurable vía `FILTER_LANGUAGES` en `.env` (comma-separated codes ISO 639-1)
- Confidence mínimo de `langdetect` para aplicar el filtro: `0.8` (hardcoded, no configurable)
- Jobs sin `posted_at` → pasan el filtro de fecha siempre
- Jobs sin `min_salary_usd_monthly` → pasan el filtro de salario siempre
- `langdetect` es no-determinista por diseño; no afecta tests (mockear en tests)
- La detección de idioma se aplica sobre `(title + " " + description)[:500]` para limitar costo

### Blacklist defaults
```
security clearance,active clearance,top secret,ts/sci,dod clearance,
secret clearance,public trust,us citizens only,
must be authorized to work in the us,us work authorization,
must be a us citizen,green card required,
sales executive,account executive,must relocate,relocation required,
staffing agency,recruiting firm
```

### Settings nuevos en `config.py`
```python
MAX_JOB_AGE_DAYS: int = 30
BLACKLIST_KEYWORDS: str = "<defaults arriba>"
MIN_SALARY_USD_MONTHLY: int | None = None   # None = no filtrar
FILTER_LANGUAGES: str = "en,es"
```

### Properties nuevas en Settings
```python
@property
def blacklist_list(self) -> list[str]:
    return [k.strip().lower() for k in self.BLACKLIST_KEYWORDS.split(",") if k.strip()]

@property
def filter_languages_list(self) -> list[str]:
    return [l.strip().lower() for l in self.FILTER_LANGUAGES.split(",") if l.strip()]
```

## Prior Decisions

- [ADR-005] Arquitectura modular — filtros viven en `worksearcher/core/filters.py`
- `filter_jobs(jobs, keywords, max_years)` ya existe — extender su firma, no crear función nueva
- `Job` model en `worksearcher/core/models.py` ya tiene `posted_at: datetime | None`
- Tests en `tests/test_filters.py` (ya existe) y `tests/test_scrapers.py`
- `MAX_YEARS_EXPERIENCE` ya sigue el patrón `int | None` con None = no filtrar — seguir mismo patrón para `MIN_SALARY_USD_MONTHLY`
- Convención: cada filtro = función pura `is_<criterio>(job, config_value) -> bool`

## Task Breakdown

### T1: Modelo — agregar `min_salary_usd_monthly`
- Añadir `min_salary_usd_monthly: float | None = None` a `Job` en `models.py`
- Añadir assert en `test_models.py` que verifica el campo existe y es opcional
- Commit: `feat: add min_salary_usd_monthly field to Job model`

### T2: Settings — agregar 4 nuevas variables
- Añadir `MAX_JOB_AGE_DAYS`, `BLACKLIST_KEYWORDS`, `MIN_SALARY_USD_MONTHLY`, `FILTER_LANGUAGES` a `config.py`
- Añadir properties `blacklist_list` y `filter_languages_list`
- Actualizar `FakeSettings` en `tests/conftest.py`
- Commit: `feat: add filter settings (age, blacklist, salary, language)`

### T3: Filtros puros en `filters.py`
- `is_recent(job, max_days) -> bool` — basado en `posted_at`
- `is_not_blacklisted(job, blacklist) -> bool` — substring match
- `is_language_allowed(job, allowed_langs) -> bool` — langdetect
- `has_minimum_salary(job, min_usd_monthly) -> bool` — basado en `min_salary_usd_monthly`
- Extender `filter_jobs` para recibir y aplicar los 4 nuevos criterios
- Tests en `test_filters.py` para cada función (mockear `langdetect.detect`)
- Commit: `feat: add date/blacklist/language/salary filters to filter_jobs`

### T4: Scrapers — poblar `posted_at`
- **Himalayas**: mapear `pubDate` (Unix int) → `datetime`
- **RemoteOK**: mapear `epoch` (Unix int) → `datetime`
- **HackerNews**: mapear `created_at_i` (Unix int) → `datetime` en cada comment child
- **jobspy**: mapear `date_posted` (columna del dataframe) → `datetime`
- Tests: añadir campo en fixtures existentes, assert `posted_at is not None`
- Commit: `feat: populate posted_at in Himalayas, RemoteOK, HackerNews, jobspy scrapers`

### T5: Scrapers — poblar `min_salary_usd_monthly`
- **Himalayas**: si `currency == "USD"`, normalizar `minSalary` según `salaryPeriod` (`annual` /12, `monthly` as-is)
- **RemoteOK**: si `salary_min` presente (viene en USD), usar directamente (ya es mensual en su API)
- Tests: añadir casos con y sin salario en fixtures
- Commit: `feat: populate min_salary_usd_monthly in Himalayas and RemoteOK scrapers`

### T6: Instalar `langdetect` y wiring en pipeline
- `uv add langdetect` (agrega a `pyproject.toml` y `requirements.lock`)
- Verificar que `filter_jobs` en `main.py` pasa los nuevos parámetros desde `config`
- Commit: `feat: install langdetect and wire all filters into pipeline`

## Verification Criteria

### Filtro de fecha
- `is_recent(job_with_posted_at_31_days_ago, max_days=30)` → `False`
- `is_recent(job_with_posted_at_29_days_ago, max_days=30)` → `True`
- `is_recent(job_with_posted_at_none, max_days=30)` → `True` (pasa siempre)

### Filtro de blacklist
- Job con `title="Security Clearance Required"` y blacklist=`["security clearance"]` → `False`
- Job con `title="Python Developer"` → `True`
- Case-insensitive: `"TOP SECRET"` matchea `"top secret"` en blacklist

### Filtro de idioma
- `langdetect.detect` retorna `"en"` → `True`
- `langdetect.detect` retorna `"es"` → `True`
- `langdetect.detect` retorna `"fr"` → `False`
- `langdetect.detect` lanza excepción → `True` (pasa, no excluir)

### Filtro de salario
- Job con `min_salary_usd_monthly=1000.0`, `MIN_SALARY_USD_MONTHLY=1200` → `False`
- Job con `min_salary_usd_monthly=1500.0`, `MIN_SALARY_USD_MONTHLY=1200` → `True`
- Job con `min_salary_usd_monthly=None`, `MIN_SALARY_USD_MONTHLY=1200` → `True`
- `MIN_SALARY_USD_MONTHLY=None` → todos pasan (filtro desactivado)

### Scrapers con `posted_at`
- Himalayas fixture con `pubDate=<unix>` → `job.posted_at` es `datetime` no nulo
- RemoteOK fixture con `epoch=<unix>` → `job.posted_at` es `datetime` no nulo
- HackerNews comment con `created_at_i=<unix>` → `job.posted_at` es `datetime` no nulo

### Scrapers con `min_salary_usd_monthly`
- Himalayas fixture con `currency="USD"`, `minSalary=2000`, `salaryPeriod="monthly"` → `job.min_salary_usd_monthly == 2000.0`
- Himalayas fixture con `currency="USD"`, `minSalary=24000`, `salaryPeriod="annual"` → `job.min_salary_usd_monthly == 2000.0`
- Himalayas fixture con `currency="EUR"`, `minSalary=2000` → `job.min_salary_usd_monthly is None`
- RemoteOK fixture con `salary_min=1500` → `job.min_salary_usd_monthly == 1500.0`

### Pipeline
- `pytest -v` — todos los tests pasan
- `uvx ruff check worksearcher/ tests/` — sin errores
- `filter_jobs` en `main.py` recibe y aplica los 4 filtros nuevos via `config`
