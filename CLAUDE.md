# WorkSearcher

## Propósito
Buscador de empleos automatizado para un ingeniero en sistemas (dev + ciberseguridad) que busca trabajo remoto en LatAm y globalmente. Scraping de múltiples plataformas, filtrado por intereses, notificación vía WhatsApp.

## Stack
- Lenguaje: Python 3.12
- Scraping (major boards): `jobspy`
- Scraping (niche boards): `playwright` + `httpx` + `BeautifulSoup4`
- Modelos de datos: `pydantic` v2
- Configuración: `pydantic-settings` (lee desde `.env`)
- Base de datos: SQLite (via `sqlite3` stdlib)
- Scheduler: cron del sistema (no daemon)
- Notificaciones: Meta Cloud API (WhatsApp) — free tier
- CLI: `click`
- Tests: `pytest`

## Plataformas target
| Plataforma | Método | Región |
|---|---|---|
| LinkedIn | jobspy | Global |
| Indeed | jobspy | Global |
| Glassdoor | jobspy | Global |
| RemoteOK | API JSON pública | Global remoto |
| Remotive | API JSON pública | Global remoto |
| Himalayas | API JSON pública | Global remoto |
| HackerNews "Who's Hiring" | Algolia API | Global dev |
| Computrabajo | playwright scraping | LatAm |
| Bumeran | playwright scraping | LatAm |
| OCC | playwright scraping | LatAm (MX) — opt-in (ver `docs/contexto/errores-conocidos.md`) |
| CyberSecJobs | httpx + BS4 | Global cyber |
| We Work Remotely | httpx + BS4 | Global remoto |
| GetOnBoard | httpx + BS4 | LatAm |

## Keywords de búsqueda (intereses del usuario)

Campos configurables — ver `worksearcher/config.py` y `.env.example`:

- **`SEARCH_KEYWORDS`** (filtro post-scraping, todos los scrapers, sin límite):
  - Desarrollo: python, javascript, typescript, react, node.js, frontend, backend, fullstack, software engineer, developer, web developer
  - Ciberseguridad: cybersecurity, security engineer, SOC analyst, pentester, infosec, ethical hacker, red team, blue team, cloud security
  - Automatización: devops, automation, SRE
- **`JOBSPY_SEARCH_TERMS`** (query a LinkedIn/Indeed/Glassdoor, máx 5 términos):
  - Default: python, cybersecurity, software engineer, devops, javascript
- **`BUMERAN_SEARCH_TERMS`** (términos en español para Bumeran MX):
  - Default: desarrollador, programador, backend, ciberseguridad, seguridad informatica
- **`COMPUTRABAJO_SEARCH_TERMS`** (términos en español para Computrabajo MX):
  - Default: desarrollador, programador, backend, ciberseguridad, seguridad informatica
- **`OCC_SEARCH_TERMS`** (términos en español para OCC MX):
  - Default: desarrollador, programador, backend, ciberseguridad, seguridad informatica
- **`GETONBOARD_CATEGORIES`** (categorías de getonbrd.com — no es búsqueda libre):
  - Default: programming, cybersecurity, sysadmin-devops-qa
- **Siempre**: remote (todos los resultados deben ser remotos — enforced en `filters.py`)

## Outreach en frío (feature separada)

Pipeline **distinto** del buscador de vacantes — no busca empleo, extrae correo
de RH de empresas medianamente grandes (con o sin vacante publicada) cerca de
unas coordenadas configurables, para que el usuario haga outreach manual.
Ver `specs/feat-018-outreach-empresas.md` para el diseño completo.

- Comando: `worksearcher outreach` (cron **semanal**, separado del `run` de 4h)
- Discovery: Overpass API (OSM), tag `website` como proxy de tamaño de negocio
- Extracción: httpx + BeautifulSoup4, home + rutas de contacto configurables,
  heurística de contexto RH (no solo regex `mailto:`), respeta `robots.txt`
- **El sistema SOLO EXTRAE — el envío de correo es manual, fuera de la app**
  (decisión explícita: reduce el riesgo legal de comunicaciones comerciales
  no solicitadas)
- Tabla `companies` en SQLite: sin expiración (a diferencia de `jobs`, un
  lead de negocio local no vence)
- Notificación WhatsApp separada (`send_outreach_digest`), header distinto
  al digest de vacantes, tope `OUTREACH_MAX_COMPANIES_PER_MESSAGE`
- Config: `OUTREACH_LAT`, `OUTREACH_LON`, `OUTREACH_RADIUS_KM` (default 80),
  `OUTREACH_CONTACT_PATHS`, `OUTREACH_MAX_COMPANIES_PER_RUN`,
  `OUTREACH_MAX_COMPANIES_PER_MESSAGE`

## Convenciones
- snake_case para variables y funciones, PascalCase para clases
- async/await para operaciones I/O (scraping)
- `Result` pattern para errores en lógica de dominio (no excepciones)
- No introducir dependencias nuevas sin consenso
- Todos los secrets via `.env` — nunca hardcodeados
- Commits en inglés, formato: `type: descripción concisa`

## Workflow de desarrollo (SDD)

Este proyecto usa Spec-Driven Development. Antes de implementar cualquier feature:

1. Crear la spec en `specs/<nombre-feature>.md` siguiendo el formato de 6 elementos
2. Revisar la spec contra el wiki SDD local (ver ruta en el AGENTS.md global)
3. Implementar contra la spec
4. Verificar que la implementación cumple los Verification Criteria de la spec

## Estructura del proyecto
```
specs/              ← specs de features (crear aquí ANTES de implementar)
docs/               ← documentación técnica y arquitectura
  contexto/         ← decisiones (ADRs), errores conocidos, glosario
  superpowers/
    plans/          ← planes de implementación generados por el skill writing-plans
  post-deploy-checklist.md  ← guía de hardening post-deploy
deploy/             ← scripts de setup + hardening para VPS
  setup.sh          ← instala app (uv, playwright, worksearcher user)
  harden.sh         ← hardening SO (SSH, UFW, fail2ban, unattended-upgrades)
worksearcher/       ← código fuente
  scrapers/         ← un scraper por plataforma
  core/             ← lógica pura (modelos, filtros, deduplicación)
  storage/          ← SQLite access layer
  notifier/         ← WhatsApp via Meta Cloud API
  outreach/         ← pipeline separado: discovery + extracción de correo RH
  config.py         ← Pydantic Settings
  main.py           ← CLI entry point (Click)
tests/              ← pytest
```

## Decisiones previas (ADRs)
- [ADR-001] Python elegido sobre Node.js por ecosistema de scraping (jobspy, playwright-stealth) y ausencia de equivalente a jobspy en Node.
- [ADR-002] Meta Cloud API elegida sobre whatsapp-web.js por ser oficial (sin riesgo de ban) y gratuita para uso personal.
- [ADR-003] SQLite elegida sobre Postgres para mantener costo cero (sin infra adicional).
- [ADR-004] cron del sistema elegido sobre APScheduler/Celery por simplicidad y resiliencia ante reboots.
- [ADR-005] Arquitectura modular (scrapers / core / storage / notifier) para poder añadir/quitar plataformas sin tocar la lógica central.
- [ADR-006] Hardening de seguridad post-deploy (deploy/harden.sh + drop-in SSH). Detalle y addenda v1+v2 con bugs de producción en `docs/contexto/decisiones.md`.
- [ADR-007] Outreach en frío: extracción de correo únicamente, envío manual por el usuario — no automatizado. Reduce el riesgo legal de comunicaciones comerciales no solicitadas (LFPDPPP) al tratar el sistema como herramienta de research personal, no remitente. Detalle en `docs/contexto/decisiones.md` y `specs/feat-018-outreach-empresas.md`.
