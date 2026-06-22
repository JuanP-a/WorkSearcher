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
| Computrabajo | playwright scraping | LatAm |
| Bumeran | playwright scraping | LatAm |
| CyberSecJobs | httpx + BS4 | Global cyber |
| We Work Remotely | httpx + BS4 | Global remoto |

## Keywords de búsqueda (intereses del usuario)

Dos campos separados — ver `worksearcher/config.py` y `.env.example`:

- **`SEARCH_KEYWORDS`** (filtro post-scraping, todos los scrapers, sin límite):
  - Desarrollo: python, javascript, typescript, react, node.js, frontend, backend, fullstack, software engineer, developer, web developer
  - Ciberseguridad: cybersecurity, security engineer, SOC analyst, pentester, infosec, ethical hacker, red team, blue team, cloud security
  - Automatización: devops, automation, SRE
- **`JOBSPY_SEARCH_TERMS`** (query a LinkedIn/Indeed/Glassdoor, máx 5 términos):
  - Default: python, cybersecurity, software engineer, devops, javascript
- **Siempre**: remote (todos los resultados deben ser remotos — enforced en `filters.py`)

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
2. Revisar la spec contra el wiki SDD local:
   `/Users/slokbaccmac/ObsidianSDD-local/`
3. Implementar contra la spec
4. Verificar que la implementación cumple los Verification Criteria de la spec

## Estructura del proyecto
```
specs/              ← specs de features (crear aquí ANTES de implementar)
docs/               ← documentación técnica y arquitectura
  superpowers/
    specs/          ← design docs generados en sesiones de brainstorming
worksearcher/       ← código fuente
  scrapers/         ← un scraper por plataforma
  core/             ← lógica pura (modelos, filtros, deduplicación)
  storage/          ← SQLite access layer
  notifier/         ← WhatsApp via Meta Cloud API
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
