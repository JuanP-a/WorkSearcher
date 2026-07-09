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

## Configuración completa via `.env` (feat/009-flexibility)

**Decisión:** Todo valor tuneable — selección de scrapers, términos de búsqueda LatAm, parámetros jobspy, timeouts, límites — se expone como campo de `Settings` configurable desde `.env`.
**Porqué:** Permite adaptar el pipeline a cualquier dominio, región o plataforma sin tocar código. `_SCRAPERS` lista hardcodeada → `_ALL_SCRAPERS` dict + `ENABLED_SCRAPERS` en `.env`.
**Campos añadidos:** `ENABLED_SCRAPERS`, `BUMERAN_SEARCH_TERMS`, `COMPUTRABAJO_SEARCH_TERMS`, `JOBSPY_SITES`, `JOBSPY_RESULTS_WANTED`, `JOBSPY_HOURS_OLD`, `SEARCH_LOCATION`, `HTTP_TIMEOUT_SECONDS`, `HIMALAYAS_RESULTS_LIMIT`, `MAX_JOBS_PER_MESSAGE`, `SCRAPER_TIMEOUT_SECONDS`.
**Coste:** +11 campos en `Settings` y `FakeSettings`; scrapers más verbosos al leer `config.*` en lugar de literales.

---

## Retry de notificación via columna `notified`

**Decisión:** Guardar jobs en DB con `notified=0`; marcar `notified=1` solo tras WhatsApp exitoso.
Al inicio del pipeline, reenviar los `notified=0` pendientes antes del nuevo scrape.
**Porqué:** Evita pérdida de jobs si WhatsApp falla después de guardar en BD.
**Descartado:** No persistir hasta confirmar envío — si el proceso muere entre guardar y enviar, se pierde.

---

## ADR-006 · Hardening de seguridad post-deploy (fix/009)

**Decisión:** Script `deploy/harden.sh` idempotente + drop-in SSH config, ejecutado una vez después de `setup.sh`.

**Porqué:** El deploy inicial cubría la app (uv, Playwright, worksearcher user) pero dejaba el servidor con defaults inseguros: root login por SSH habilitado, password auth habilitada, sin firewall, sin fail2ban, sin auto-patching. Estos son problemas del SO, no de la app — `setup.sh` se enfoca en app, `harden.sh` en el host.

**Qué aplica (idempotente):**

| Componente | Cambio | Porqué |
|---|---|---|
| `sshd_config.d/worksearcher.conf` | `PermitRootLogin no`, `PasswordAuthentication no`, sin forwarding | Root login + password auth = los dos ataques más comunes contra SSH expuesto |
| UFW | `deny incoming` por default, `allow OpenSSH` | Cerrar todos los puertos no usados sin listarlos uno por uno |
| fail2ban | sshd jail: 3 retries / 10 min → 1h ban | Mitigar brute-force sin depender de IP allowlist |
| `unattended-upgrades` | security patches auto, no reboot | Ubuntu no parchea solo por default; cvEs aparecen semanalmente |

**Por qué drop-in y no editar `/etc/ssh/sshd_config`:** `sshd_config.d/*.conf` es el patrón moderno (Ubuntu 22+ lo soporta nativamente). Mantiene los cambios aislados y reversibles con un `rm` + `systemctl reload ssh`.

**Por qué idempotente:** re-ejecutable en cualquier momento (CI, recovery, próximo VPS). No falla si ya está aplicado.

**Lo que NO está en el repo:**
- 2FA en Vultr (config de cuenta, no del servidor)
- SSH key del usuario (secreto, vive en el Mac del operador)
- Cambio de SSH port (debatible — añade fricción sin reducir superficie real contra un atacante dirigido; default 22 con fail2ban es suficiente para bots)

### ADR-006 addendum · Bugs encontrados en producción (fix/010)

Después del primer deploy del hardening, se encontraron 3 bugs que provocaron lockout y self-ban:

**Bug A · Drop-in sin prefijo numérico.**

El script copiaba a `/etc/ssh/sshd_config.d/worksearcher.conf`. En orden alfabético, `50-cloud-init.conf` carga antes que `worksearcher.conf`. sshd usa "first occurrence wins" para directivas — el `PasswordAuthentication yes` de cloud-init ganaba sobre nuestro `no`. Resultado: el endurecimiento era silenciosamente ignorado.

**Fix:** drop-in con prefijo `00-` carga antes que `50-cloud-init.conf`. El script además borra el archivo viejo sin prefijo si existe (idempotente para re-deploys).

**Bug B · Lockout total al aplicar `PermitRootLogin no`.**

El script original no creaba un usuario sudoer de backup. Si el operador perdía la SSH key de root (o si el archivo drop-in se rompía), no había forma de entrar — el Vultr web console tampoco deja loguear como root sin password cuando el sistema está hardened.

**Fix:** el script crea un usuario `deploy` con NOPASSWD sudo + copia de la `authorized_keys` de root, **antes** de aplicar las reglas SSH. Operador debe verificar que puede entrar como `deploy` y sudoear antes de cerrar la sesión root.

**Bug C · fail2ban autobaneo del operador.**

fail2ban corre 3 retries / 10 min → 1h ban. Después de unas pruebas con keys/passwords incorrectas, la IP del operador quedó baneada. SSH rechazaba conexiones con "Connection refused" (UFW reject) desde la Mac, mientras que el server veía todo OK.

**Fix:** en el VPS actual, `systemctl disable --now fail2ban` (decisión operativa, no de script). fail2ban vuelve a activarse cuando se configure `ignoreip` con la IP del operador. El checklist `docs/post-deploy-checklist.md` documenta esto.

**Lección general:** el script de hardening nunca debe asumir que el operador puede "arreglarlo después" si algo sale mal. Cada paso de endurecimiento debe ir precedido por su contraparte de recuperación.

### ADR-006 addendum v2 · Bugs encontrados después del merge (fix/012)

Después del primer merge de hardening (PR #14) y de la primera ejecución real del cron en producción, aparecieron 3 bugs nuevos:

**Bug D · Cron `No module named worksearcher` × 5.**

Síntoma: las primeras 5 ejecuciones del cron (cada 4h) fallaron silenciosamente con `No module named worksearcher` en el log. El pipeline no se ejecutaba; el operador no recibía WhatsApp durante ~20h.

Causa raíz: `pyproject.toml` no tiene sección `[build-system]`. Cuando el cron corría `/usr/local/bin/uv run python -m worksearcher`, uv detectaba el proyecto pero no podía construir/instalar el paquete local (sin build-system) — solo instalaba las dependencias pip (jobspy, playwright). El módulo `worksearcher` quedaba ausente en el site-packages del venv. `python -m worksearcher` fallaba.

Detalle secundario: la fix inicial de "agregar `cd /opt/worksearcher &&`" probó que el problema era de import resolution, no de cwd. `cd` solo ayudó a `python -m worksearcher` cuando se ejecutaba manualmente (porque Python encuentra paquetes en el cwd). Con `uv run`, el comando intermedio rompía el path.

**Fix:** cron usa el python del venv directamente, sin pasar por `uv run`:

```cron
0 */4 * * * HOME=/var/lib/worksearcher cd /opt/worksearcher && /opt/worksearcher/.venv/bin/python -m worksearcher run >> /var/log/worksearcher.log 2>&1
```

Workaround — la fix real (en próximo PR) es agregar `[build-system]` + `[tool.setuptools.packages.find]` a pyproject.toml y usar `uv sync` en setup.sh. Después de eso, el cron puede volver a `uv run` y estos workarounds se quitan.

**Bug E · Playwright binary en `/root/.cache/` en vez de `/home/worksearcher/.cache/`.**

Síntoma: OCC, Bumeran, Computrabajo crasheaban con:

```
BrowserType.launch: Executable doesn't exist at
/home/worksearcher/.cache/ms-playwright/chromium_headless_shell-1223/...
```

Causa raíz: `setup.sh` corría `playwright install chromium` como root. Playwright escribe el binario a `$HOME/.cache/ms-playwright/` — corriendo como root, eso terminaba en `/root/.cache/`. El pipeline (corriendo como `worksearcher`) buscaba el binario en `/home/worksearcher/.cache/` y no lo encontraba. El primer deploy enmascaró esto porque un operador chown-eó el cache a mano después del install — workaround frágil que se rompe en cualquier deploy fresco.

**Fix:** `setup.sh` hace `chown -R worksearcher:worksearcher $APP_DIR` ANTES del `playwright install`, y luego corre el install como `$SERVICE_USER` vía `sudo -u`. El usuario worksearcher tiene `/sbin/nologin` como shell, pero `sudo -u <user> bash -c '...'` lo bypasea y ejecuta en un bash no-login. `playwright install-deps` se queda como root (usa apt).

**Bug F · jobspy local pass con país aleatorio.**

Síntoma: el local pass (Celaya, Guanajuato) fallaba intermitentemente con `Invalid country string: 'sri lanka'` (o 'nepal', 'cameroon'). Cuando fallaba, el local pass devolvía 0 jobs. A veces pasaba y devolvía 4 jobs.

Causa raíz: jobspy, sin un kwarg `country` explícito, intenta parsear la string de `location` como nombre de país. Con una location en español como "Celaya, Guanajuato", el parser es no-determinístico — a veces acierta México y devuelve resultados, a veces elige un país random que no es el target real y falla.

**Fix:** local pass pasa `country="mexico"` explícito. `_blocking_scrape` ahora acepta un `country` opcional y solo lo incluye en los kwargs cuando está set (el remote pass sigue sin pasarlo). Cubierto por test `test_jobspy_local_pass_passes_country_mexico`.

**Lección general v2:** los bugs de deploy se manifiestan solo cuando el sistema corre en producción por primera vez. No alcanza con `bash -n` y tests unitarios — hay que correr el pipeline end-to-end en una instancia real y leer el log. La fix de Bug D la encontramos revisando `sudo tail -30 /var/log/worksearcher.log`; la de Bug E la encontramos cuando el manual run reportó los Playwright errors. La de Bug F la identificamos comparando logs de runs exitosos y fallidos.

---

## ADR-007 · Outreach en frío: extracción manual, sin envío automático

**Decisión:** el pipeline de outreach (`worksearcher outreach`, `specs/feat-018-outreach-empresas.md`) solo descubre empresas y extrae correo de RH. El envío del correo lo hace el usuario manualmente, fuera de la app.

**Porqué:** un sistema que manda correo automático a RH de terceros cae bajo reglas de comunicaciones comerciales no solicitadas (LFPDPPP en México) — requeriría aviso de privacidad, mecanismo de opt-out, identificación de remitente, etc. Tratando el sistema como herramienta de research/extracción personal (el usuario decide a quién y qué escribir), ese riesgo legal no aplica. Se evaluó explícitamente con el usuario antes de escribir código (ver brainstorming en la sesión que originó `specs/feat-018-outreach-empresas.md`).

**Descartado:** envío automático de correo — mismo pipeline pero disparando el email él mismo tras la extracción. Se descartó por el riesgo legal descrito arriba; si se revisita, necesitaría aviso de privacidad + opt-out + registro de consentimiento antes de siquiera considerarse.

**Consecuencia de diseño:** la tabla `companies` no tiene tracking de `contacted`/`bounced`/respuestas — eso lo lleva el usuario fuera de la app. El sistema solo trackea `notified` (si ya se le mostró el lead por WhatsApp), no el estado real del outreach.
