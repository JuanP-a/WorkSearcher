---
spec_id: FEAT-001
title: "Core Scraping Pipeline"
version: 1.0
status: implemented
priority: high
created: 2026-06-18
author: JuanP-a
complexity: L
---

# Spec: Core Scraping Pipeline

Pipeline central que orquesta scrapers, filtra ofertas, deduplica, persiste en SQLite y notifica vía WhatsApp. Es el corazón del sistema.

## Outcomes

- [x] El pipeline extrae ofertas de al menos 3 plataformas (LinkedIn, Indeed, RemoteOK)
- [x] Solo pasan ofertas que contengan al menos 1 keyword de dev o cyber Y sean remotas
- [x] Ofertas ya vistas (mismo fingerprint) no generan notificación ni se reinsertan
- [x] Al finalizar, si hay ofertas nuevas, se envía digest WhatsApp con título, empresa y URL
- [x] El pipeline es invocable desde CLI: `python -m worksearcher run`
- [x] El pipeline corre sin errores en VPS Ubuntu 22.04 con cron cada 4h

## Scope Boundaries

### Dentro del alcance
- Scraping de LinkedIn, Indeed, Glassdoor (via jobspy)
- Scraping de RemoteOK (API JSON pública)
- Scraping de Remotive (API JSON pública)
- Modelo `Job` con Pydantic
- Filtrado por keywords + remote flag
- Deduplicación por hash(title + company + url)
- Persistencia en SQLite
- Notificación WhatsApp via Meta Cloud API (digest, no mensaje por oferta)
- CLI entry point con Click
- Configuración via `.env` + Pydantic Settings

### Fuera del alcance
- Computrabajo, Bumeran, CyberSecJobs (specs separadas — playwright más complejo)
- Auto-aplicar a ofertas
- Dashboard web
- Notificaciones por email
- Rate limiting avanzado / proxy rotation (se añade si hay bloqueos)
- Tests de integración contra plataformas reales

## Constraints & Assumptions

### Stack y dependencias
- Stack: Python 3.12, SQLite (stdlib), asyncio
- Librerías: `jobspy`, `httpx`, `pydantic` v2, `pydantic-settings`, `playwright`, `click`, `python-dotenv`
- Librerías a NO usar: SQLAlchemy (overkill), APScheduler (cron es suficiente), Celery
- No introducir dependencias nuevas sin consenso

### Suposiciones sobre el entorno
- `.env` existe con `META_PHONE_NUMBER_ID`, `META_ACCESS_TOKEN`, `META_RECIPIENT_PHONE`
- Playwright instalado con `playwright install chromium`
- Cron configurado en VPS para ejecutar cada 4h

### Requisitos no funcionales
- Pipeline completo < 5 minutos por ejecución
- Scrapers corren concurrentemente (`asyncio.gather`)
- Si un scraper falla, el pipeline continúa con el resto (fail gracefully)
- Logs a stdout (cron redirige a archivo)

## Prior Decisions

- [ADR-001] Python sobre Node.js — ecosistema scraping superior
- [ADR-002] Meta Cloud API — oficial, free tier, sin riesgo de ban
- [ADR-003] SQLite — costo cero, suficiente para uso personal
- [ADR-004] cron del sistema — simplicidad y resiliencia
- [ADR-005] Arquitectura modular — scrapers independientes del core
- Patrón: functional core (filters, dedup) / imperative shell (scrapers, DB, notifier)
- Patrón: Pydantic models en boundary, validación solo ahí
- Patrón: `ON CONFLICT DO NOTHING` para deduplicación en DB

## Task Breakdown

1. **Modelo de datos** (`worksearcher/core/models.py`):
   - Definir `Job` Pydantic model con todos los campos
   - Definir `JobSource` enum (linkedin, indeed, glassdoor, remoteok, remotive)
   - Calcular `fingerprint` en validator (`hash(title + company + url)`)

2. **Configuración** (`worksearcher/config.py`):
   - `Settings` con Pydantic Settings
   - Campos: `META_PHONE_NUMBER_ID`, `META_ACCESS_TOKEN`, `META_RECIPIENT_PHONE`, `SEARCH_KEYWORDS`, `SCRAPE_INTERVAL_HOURS`

3. **Storage** (`worksearcher/storage/database.py`):
   - Crear tabla `jobs` si no existe
   - `save_jobs(jobs: list[Job]) -> int` — retorna count de nuevos insertados
   - `ON CONFLICT(fingerprint) DO NOTHING`
   - `get_seen_fingerprints() -> set[str]`

4. **Filtros** (`worksearcher/core/filters.py`):
   - `is_relevant(job: Job, keywords: list[str]) -> bool` — pure function
   - `filter_jobs(jobs: list[Job], keywords: list[str]) -> list[Job]` — pure function
   - Match case-insensitive en title + description

5. **Deduplicador** (`worksearcher/core/deduplicator.py`):
   - `deduplicate(jobs: list[Job], seen: set[str]) -> list[Job]` — pure function

6. **Scrapers** (`worksearcher/scrapers/`):
   - `jobspy_scraper.py`: async wrapper sobre jobspy para LinkedIn/Indeed/Glassdoor
   - `remoteok_scraper.py`: GET `https://remoteok.com/api` → parse JSON → list[Job]
   - `remotive_scraper.py`: GET `https://remotive.com/api/remote-jobs` → parse JSON → list[Job]
   - Cada scraper: `async def scrape(config: Settings) -> list[Job]`
   - Fail gracefully: si falla, log error, retornar `[]`

7. **Notifier** (`worksearcher/notifier/whatsapp.py`):
   - `send_digest(jobs: list[Job], config: Settings) -> None`
   - Formato mensaje: lista de `{título} @ {empresa}\n{url}` (max 10 ofertas por mensaje)
   - POST a Meta Cloud API messages endpoint

8. **CLI + Orquestador** (`worksearcher/main.py`):
   - `@click.command() run()` — ejecuta pipeline completo
   - `asyncio.gather(*[scraper(config) for scraper in SCRAPERS])`
   - Orquesta: scrape → filter → dedup → save → notify

9. **Tests** (`tests/`):
   - `test_filters.py`: unit tests para `is_relevant` y `filter_jobs`
   - `test_deduplicator.py`: unit tests para `deduplicate`
   - `test_models.py`: validación Pydantic + fingerprint calculation
   - `test_database.py`: SQLite insert + dedup con DB en memoria

## Verification Criteria

### Functional
- `run` CLI con `.env` válido → pipeline ejecuta sin error
- Oferta con keyword "python" + remote=True → pasa filtro
- Oferta con keyword "marketing" + remote=True → no pasa filtro
- Oferta con keyword "cybersecurity" + remote=False → no pasa filtro
- Misma oferta insertada dos veces → DB solo tiene 1 registro
- Pipeline con 5 ofertas nuevas → WhatsApp recibe 1 mensaje con las 5
- Pipeline con 0 ofertas nuevas → WhatsApp no recibe ningún mensaje
- Si RemoteOK scraper falla → pipeline continúa con los demás scrapers

### Non-functional
- Pipeline completo < 5 minutos
- Logs muestran: plataforma, cantidad de resultados, nuevas insertadas

### Edge cases
- `.env` faltante → error descriptivo al inicio, no en medio del pipeline
- Título con caracteres especiales (ñ, tildes) → se guarda correctamente en SQLite
- Oferta sin URL → no se inserta

### Security
- Tokens de Meta API solo en `.env`, nunca en logs ni en código
- `.env` en `.gitignore` — nunca commiteado

## Preguntas Abiertas
- ¿Cuántas ofertas máximo por notificación WhatsApp? → Asumir 10, configurable después
- ¿Notificar una vez al día resumen o inmediatamente? → Inmediatamente al correr el cron

## Notas de Implementación
- `jobspy` es síncrono internamente — wrappear con `asyncio.to_thread()`
- RemoteOK y Remotive tienen APIs JSON públicas sin auth — los más simples de implementar primero
- Meta Cloud API endpoint: `POST https://graph.facebook.com/v18.0/{phone_id}/messages`
