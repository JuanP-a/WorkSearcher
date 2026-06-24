# Decisiones técnicas — WorkSearcher

Decisiones que se ven en el código/commits/docs, con contexto de porqué y qué se descartó.

---

## ADR-001 · Python sobre Node.js

**Decisión:** Python 3.12.
**Porqué:** `jobspy` no tiene equivalente en Node; ecosistema de scraping (playwright-stealth, BS4, httpx) más maduro.
**Descartado:** Node.js — falta de jobspy, ecosistema playwright más complejo para scraping anti-bot.

---

## ADR-002 · Meta Cloud API sobre whatsapp-web.js

**Decisión:** Meta Cloud API (System User token permanente).
**Porqué:** API oficial → sin riesgo de ban por automatización. Free tier cubre uso personal.
**Descartado:** `whatsapp-web.js` — usa sesión del teléfono, susceptible a ban, requiere mantener browser abierto.

---

## ADR-003 · SQLite sobre Postgres

**Decisión:** SQLite stdlib con WAL mode.
**Porqué:** Costo cero, sin infra adicional, suficiente para volúmenes de cientos de jobs/día.
**Descartado:** Postgres — requiere servidor adicional, coste mensual innecesario para este uso.

---

## ADR-004 · Cron del sistema sobre APScheduler / Celery

**Decisión:** `crontab` estándar del SO.
**Porqué:** Más simple, sobrevive reboots sin configuración extra, sin dependencias en memoria.
**Descartado:** APScheduler, Celery — overhead injustificado para una tarea periódica simple.

---

## ADR-005 · Scrapers modulares (un archivo por plataforma)

**Decisión:** Cada plataforma = un módulo con interfaz `async def scrape(config) -> list[Job]`.
**Porqué:** Añadir o quitar plataformas sin tocar el pipeline central. Fallos aislados por scraper.
**Descartado:** Scraper monolítico — acoplamiento total, un fallo tira todo.

---

## jobspy pinado a commit SHA, no a versión semver

**Decisión:** `git+https://github.com/Bunsly/JobSpy.git@fda080a...`
**Porqué:** jobspy no publica releases estables con semver. Versión en PyPI puede estar desactualizada o rota.
**Coste:** Actualizar requiere encontrar manualmente el SHA del commit deseado.

---

## langdetect con `detect_langs()` y umbral 0.8

**Decisión:** Usar `detect_langs()` (no `detect()`), aplicar filtro solo si `prob >= 0.8`.
**Porqué:** `detect()` no expone confianza. Textos cortos o mixtos tienen detección poco fiable.
Con umbral: texto ambiguo pasa en lugar de ser descartado silenciosamente (fail-open).
**Coste:** `langdetect` es no-determinista — todos los tests que lo usan deben mockearlo.

---

## Salario normalizado a USD/mes en memoria, no persistido

**Decisión:** `min_salary_usd_monthly` existe en el modelo `Job` pero no en la tabla SQLite.
**Porqué:** El filtro de salario se aplica antes de persistir. Los datos de salario son incompletos
(solo Himalayas y RemoteOK los exponen) y cambiarían con cada scrape.
**Descartado:** Persistir salario — complejidad de schema sin beneficio claro hoy.

---

## RemoteOK salary_min es anual (÷12 para mensualizar)

**Decisión:** `min_salary_usd_monthly = float(salary_min) / 12`
**Porqué:** Verificado en producción: RemoteOK devuelve `salary_min` como USD anual, no mensual.
Error detectado en code review (originalmente se guardaba sin dividir → valores 12x inflados).

---

## DB_PATH configurable via `.env`

**Decisión:** `DB_PATH: str = "worksearcher.db"` en `Settings`. Default relativo para dev local; en VPS se sobreescribe con ruta absoluta.
**Porqué:** Mantiene compatibilidad con dev local sin cambios, permite mover la BD fuera del repo en VPS.
**VPS:** `DB_PATH=/var/lib/worksearcher/worksearcher.db` en `.env`. `deploy/setup.sh` crea el directorio con `chown worksearcher`.

---

## HackerNews is_remote detectado desde texto

**Decisión:** `is_remote = "REMOTE" in plain_text.upper()` (substring en el comentario parseado).
**Porqué:** Hardcodear `is_remote=True` hacía que posts de ONSITE pasaran el filtro.
**Limitación conocida:** No detecta "remote-friendly", "hybrid remote", etc. — aceptado por simplicidad.

---

## Hardening de seguridad pre-VPS

**Decisión:** Bloque de fixes aplicados antes del primer deploy, identificados por revisión de seguridad automatizada.

| Fix | Archivo | Razón |
|-----|---------|-------|
| Quitar `--no-sandbox` de Chromium | `computrabajo_scraper.py` | Con proceso root, un exploit de renderer = root en VPS. Reemplazado por `--disable-gpu --disable-dev-shm-usage` |
| Usuario dedicado `worksearcher` | `deploy/setup.sh` | Principio de menor privilegio; activa el sandbox de Chromium |
| uv a `/usr/local/bin/uv` | `deploy/setup.sh` | `worksearcher` no tiene home → `$HOME/.local/bin` no existe en su PATH de cron |
| SHA256 en installer de uv | `deploy/setup.sh` | `curl \| sh` ejecuta código remoto como root sin verificar integridad |
| `requirements.hashes.lock` + `--require-hashes` | `deploy/setup.sh` | pip verifica hashes de los 38 paquetes PyPI en install; previene tampering |
| `field_validator` en `Job.url` | `models.py` | Rechaza `javascript:`, `data:`, `ftp:` de páginas scrapeadas antes de entrar a BD o WhatsApp |

**Por qué `field_validator` y no `AnyHttpUrl`:** `AnyHttpUrl` cambia `url` de `str` a objeto Pydantic, rompiendo `.startswith()`, `in`, y `==` en tests y scrapers. El validator logra el mismo objetivo de seguridad sin cambiar el tipo.

---

## Retry de notificación via columna `notified`

**Decisión:** Guardar jobs en DB con `notified=0`; marcar `notified=1` solo tras WhatsApp exitoso.
Al inicio del pipeline, reenviar los `notified=0` pendientes antes del nuevo scrape.
**Porqué:** Evita pérdida de jobs si WhatsApp falla después de guardar en BD.
**Descartado:** No persistir hasta confirmar envío — si el proceso muere entre guardar y enviar, se pierde.
