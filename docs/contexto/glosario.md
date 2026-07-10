# Glosario — WorkSearcher

## Entidades del dominio

**Job**
Oferta de trabajo scrapeada. Entidad central del sistema. Modelo Pydantic con campos:
`title`, `company`, `location`, `url`, `source`, `is_remote`, `description`,
`posted_at`, `min_salary_usd_monthly`, `fingerprint`.

**fingerprint**
Clave de deduplicación. SHA-256 de `lower(title + company + url)`. Se calcula automáticamente
como `@computed_field`. Dos jobs con mismo fingerprint = mismo trabajo visto antes.

**JobSource**
`StrEnum` con 13 valores: `linkedin`, `indeed`, `glassdoor`, `remoteok`, `remotive`,
`weworkremotely`, `cybersecjobs`, `computrabajo`, `bumeran`, `himalayas`, `hackernews`,
`occ`, `getonboard`.
Identifica de qué plataforma viene cada job.

**digest**
El mensaje de WhatsApp que se envía al usuario. Lista de hasta 10 jobs nuevos.
Si hay más de 10, el mensaje indica cuántos más quedaron en BD.

**scraper**
Módulo Python que consulta una plataforma y devuelve `list[Job]`.
Interfaz: `async def scrape(config: Settings) -> list[Job]`.

**pipeline**
La función `_run_pipeline` en `main.py`. Orquesta scrapers → filtros → dedup → BD → WhatsApp.
Se ejecuta completa cada vez que cron dispara `python -m worksearcher run`.

**Company**
Empresa descubierta por el pipeline de outreach (`worksearcher/outreach/`). Modelo Pydantic
separado de `Job` — no es una vacante. Campos: `name`, `website`, `email`,
`email_is_hr_context`, `status`, `fingerprint`. Persistida en tabla `companies`
sin expiración (a diferencia de `jobs`).

**outreach**
Pipeline separado del buscador de vacantes (`worksearcher outreach`, cadencia semanal).
Descubre empresas por coordenadas (Overpass API) y extrae correo de RH — el envío es
manual, fuera de la app (ADR-007, ver `decisiones.md`). No comparte ciclo con `run`.

**email_is_hr_context**
Bool en `Company`. `True` si el correo extraído estaba cerca de contexto textual de RH
("recursos humanos", "bolsa de trabajo", etc.); `False` si fue un fallback genérico
(primer `mailto:` encontrado sin contexto). Mostrado en el digest WhatsApp como
"✅ RH confirmado" / "⚠️ contacto general".

---

## Conceptos técnicos internos

**posted_at**
`datetime` UTC de cuándo fue publicado el job. `None` si el scraper no expone fecha.
Jobs con `posted_at=None` siempre pasan el filtro de fecha (fail-open).

**min_salary_usd_monthly**
Salario mínimo en USD por mes, normalizado. `None` si el scraper no expone salario o no es USD.
Fuentes con datos: Himalayas (anual ÷ 12 si USD) y RemoteOK (anual ÷ 12).
No se persiste en BD.

**unnotified**
Jobs en BD con `notified=0`. Se reenvían al inicio del siguiente ciclo si el envío anterior falló.

**FakeSettings**
Test double de `Settings` definido en `tests/conftest.py`. Clase Python simple (no mock)
con los mismos atributos que usa el código. Se actualiza manualmente cuando `Settings` crece.

**blacklist**
Lista de keywords que descalifican un job. Substring match case-insensitive sobre `title + description`.
Defaults en `BLACKLIST_KEYWORDS`: clearances de seguridad, requisitos de ciudadanía US, roles de ventas, etc.

**seen / fingerprints**
`set[str]` de fingerprints ya en BD. `get_seen_fingerprints(candidates, conn)` consulta solo
los fingerprints del batch actual (no full scan) — optimización de memoria.

**WAL mode**
SQLite journal mode activado en cada conexión. Permite lecturas concurrentes sin bloquear escrituras.
Relevante porque el pipeline futuro podría tener lectura y escritura concurrentes.

---

## Siglas y abreviaciones

| Sigla | Significado |
|-------|------------|
| HN | HackerNews |
| WWR | We Work Remotely |
| SOC | Security Operations Center |
| SRE | Site Reliability Engineer |
| SDD | Spec-Driven Development (workflow de desarrollo del proyecto) |
| BS4 | BeautifulSoup4 |
| fp / fps | fingerprint / fingerprints |
| ADR | Architecture Decision Record |
| VPS | Virtual Private Server (donde corre en producción) |
| Meta API | Meta Cloud API — la API oficial de WhatsApp Business |

---

## Plataformas scrapeadas

| Nombre | Código `JobSource` | Método | Región |
|--------|--------------------|--------|--------|
| LinkedIn | `linkedin` | jobspy | Global |
| Indeed | `indeed` | jobspy | Global |
| Glassdoor | `glassdoor` | jobspy | Global |
| RemoteOK | `remoteok` | httpx JSON | Global remoto |
| Remotive | `remotive` | httpx JSON | Global remoto |
| We Work Remotely | `weworkremotely` | httpx + BS4 | Global remoto |
| CyberSecJobs (foorilla.com) | `cybersecjobs` | httpx + BS4 | Global cyber |
| Himalayas | `himalayas` | httpx JSON | Global remoto |
| HackerNews Who's Hiring | `hackernews` | Algolia API | Global dev |
| Computrabajo | `computrabajo` | playwright | LatAm |
| Bumeran | `bumeran` | playwright | LatAm |
| OCC | `occ` | playwright | LatAm (MX) — opt-in |
| GetOnBoard | `getonboard` | httpx + BS4 | LatAm |
