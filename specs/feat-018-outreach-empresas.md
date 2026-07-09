# feat-018: Outreach en frío — extracción de correo de RH por coordenadas

## 1. Propósito
Pipeline **separado** del buscador de vacantes: dado un punto (lat/lon) y un
radio en `.env`, descubre empresas medianamente grandes en la zona (con o sin
vacante publicada) y extrae el correo de RH/contacto de su sitio web, para que
el usuario haga outreach en frío **manualmente**. El sistema solo extrae y
notifica — no envía correo a las empresas.

## 2. Comportamiento esperado
- **Discovery**: query a Overpass API (OpenStreetMap) con `around:radius,lat,lon`
  buscando nodos/ways con tag `website` presente (proxy de "negocio
  medianamente grande" — un changarro sin sitio web no entra). Radio y coords
  vienen de `.env` (`OUTREACH_LAT`, `OUTREACH_LON`, `OUTREACH_RADIUS_KM=80`).
- **Extracción de correo**: por cada empresa descubierta, `httpx` GET a la home
  + rutas comunes configurables (`OUTREACH_CONTACT_PATHS`, default
  `/contacto,/trabaja-con-nosotros,/bolsa-de-trabajo,/careers,/rh`). Se
  respeta `robots.txt` del sitio antes de crawlear (via `urllib.robotparser`).
  Parseo con BS4: se buscan enlaces `mailto:` y direcciones en texto plano;
  se prioriza el correo cuyo contexto (texto cercano, atributos) matchee
  keywords de RH (`recursos humanos, rh, trabaja con nosotros, bolsa de
  trabajo, vacantes, careers, hr, reclutamiento`). Si no hay match de
  contexto pero sí hay al menos un correo, se usa el primero encontrado como
  fallback (`email_is_hr_context: bool` en el modelo indica cuál fue).
- Empresa sin correo encontrado tras crawlear todas las rutas → se guarda con
  `status=no_email_found` (visible para diagnóstico, no se notifica).
- **Persistencia**: tabla `companies` nueva, **sin expiración** (a diferencia
  de `jobs`/`MAX_JOB_AGE_DAYS`) — un negocio local no "vence" en 30 días.
  Fingerprint = `sha256(name+website)`. Dedup igual que jobs: candidatos ya
  vistos (por fingerprint) no se re-notifican ni re-crawlean.
- **Notificación**: WhatsApp digest **separado** del de vacantes (mensaje,
  función y header distintos — `send_outreach_digest`, no
  `send_digest`), truncado a `OUTREACH_MAX_COMPANIES_PER_MESSAGE=30`. Empresas
  que exceden el tope quedan `notified=0`, se reintentan en la próxima corrida
  (mismo patrón `get_unnotified_jobs`/`mark_jobs_notified` ya usado para jobs).
- **Cadencia**: semanal, corrida propia vía `worksearcher outreach` (comando
  CLI nuevo), cron separado del de 4h de `worksearcher run`. No comparte
  ciclo con el pipeline de vacantes.
- Tope superior de empresas descubiertas por corrida:
  `OUTREACH_MAX_COMPANIES_PER_RUN` (default 100) — evita que un radio de 80km
  en zona densa dispare un Overpass query/crawl desproporcionado.
- Si Overpass falla (timeout/rate-limit) o una empresa individual falla el
  crawl, se loguea warning y se continúa (mismo patrón resiliente que
  scrapers de jobs — no aborta la corrida completa).

## 3. Scope
**In**: modelo `Company`, tabla `companies` + CRUD, discovery vía Overpass,
extracción de correo vía httpx+BS4 con heurística de contexto RH, respeto de
`robots.txt`, notifier WhatsApp separado, comando CLI `outreach`, config
fields nuevos, tests unitarios de heurística/fingerprint/dedup con fixtures
(sin mockear Overpass/crawl real — sigue convención del proyecto de
verificación en vivo para I/O externo).

**Out**: envío automático de correo (manual, fuera del sistema). Tracking de
`contacted`/`bounced`/respuestas (lo lleva el usuario fuera de la app).
Tiling de bbox para radios grandes en zonas muy densas (single Overpass query
por ahora — mejora futura si `OUTREACH_MAX_COMPANIES_PER_RUN` se satura
seguido). Clasificación de tamaño de empresa más allá del proxy `website` tag.
Reintentos/backoff sofisticados contra Overpass (un intento, falla = log +
corrida vacía, igual que otros scrapers).

## 4. Decisiones de diseño
- **Extracción manual, no envío automático.** Decisión explícita del usuario
  — reduce drásticamente el riesgo legal (LFPDPPP de comunicaciones
  comerciales no aplica; el sistema es una herramienta de research personal,
  no un remitente). Documentado como ADR — ver `docs/contexto/decisiones.md`.
- **Pipeline y módulo separados de `scrapers/`/`Job`.** `Company` no es una
  vacante — cadencia, expiración y notificación distintas. Nuevo paquete
  `worksearcher/outreach/` en vez de mezclar con `worksearcher/scrapers/`
  (que es específicamente para fuentes de `Job`).
- **Tabla `companies` sin expiración.** A diferencia de jobs, un negocio local
  sigue siendo un lead válido indefinidamente — no hay equivalente a
  `MAX_JOB_AGE_DAYS`.
- **Tag `website` de OSM como proxy de tamaño — limitación conocida.** OSM no
  tiene un tag confiable de número de empleados. Se documenta como limitación
  aceptada, no se intenta resolver con una fuente de pago (mantiene ADR-003,
  costo cero).
- **Heurística de contexto RH antes que regex `mailto:` puro.** Regex solo
  trae mayoría de `contacto@`/`ventas@` sin relación a RH — se prioriza
  contexto textual cercano al enlace.
- **`robots.txt` respetado en el crawl.** Higiene ética/legal mínima al
  crawlear cientos de sitios de terceros en un radio de 80km.
- **Radio 80km, cadencia semanal, tope 30/mensaje** — decididos por el
  usuario tras discutir escala (80km ≈ 4x área de la propuesta inicial de
  20km, compensado con `OUTREACH_MAX_COMPANIES_PER_RUN` y cadencia semanal
  en vez de cada 4h).

## 5. Criterios de verificación
- [ ] `Company.fingerprint` estable para mismo `(name, website)`, distinto si
      cambia cualquiera de los dos
- [ ] `Settings().outreach_contact_paths_list` default
      `["/contacto", "/trabaja-con-nosotros", "/bolsa-de-trabajo", "/careers", "/rh"]`
- [ ] `Settings().OUTREACH_RADIUS_KM == 80` por default
- [ ] Heurística de contexto RH: con fixture HTML con 2 `mailto:` (uno junto a
      "Recursos Humanos", otro junto a "Ventas"), extrae el de RH y marca
      `email_is_hr_context=True`
- [ ] Sin ningún match de contexto RH pero con al menos un `mailto:`, usa el
      primero encontrado y marca `email_is_hr_context=False`
- [ ] Sin ningún `mailto:` en ninguna ruta, `status="no_email_found"`, no se
      notifica
- [ ] `robots.txt` que deshabilita crawl de una ruta → esa ruta se salta, no
      se golpea
- [ ] Tabla `companies` no tiene columna de expiración/edad
- [ ] Dedup: empresa con fingerprint ya visto no se re-notifica
- [ ] Digest WhatsApp de outreach usa header distinto al de jobs
      (verificable por string literal del mensaje)
- [ ] Tope `OUTREACH_MAX_COMPANIES_PER_MESSAGE=30` trunca el mensaje;
      excedentes quedan `notified=0` para siguiente corrida
- [ ] Comando `worksearcher outreach` ejecuta el pipeline completo
      end-to-end contra fixtures (discovery + extracción mockeadas)
- [ ] Todos los tests existentes siguen pasando (no regresiones)
- [ ] `ruff check` + `ruff format` sin violaciones

## 6. Archivos afectados
| Acción | Archivo |
|--------|---------|
| Modify | `worksearcher/core/models.py` (nuevo `Company`) |
| Modify | `worksearcher/config.py` (campos `OUTREACH_*`) |
| Create | `worksearcher/outreach/__init__.py` |
| Create | `worksearcher/outreach/discovery.py` (Overpass) |
| Create | `worksearcher/outreach/email_extractor.py` (crawl + heurística RH) |
| Create | `worksearcher/outreach/pipeline.py` (orquesta discovery → extracción → dedup → save → notify) |
| Modify | `worksearcher/storage/database.py` (tabla `companies` + CRUD) |
| Modify | `worksearcher/notifier/whatsapp.py` (`send_outreach_digest`) |
| Modify | `worksearcher/main.py` (comando CLI `outreach`) |
| Create | `tests/test_outreach.py` |
| Modify | `tests/test_database.py` |
| Modify | `.env.example` |
| Modify | `CLAUDE.md` |
| Modify | `docs/contexto/decisiones.md` (ADR-007: outreach manual, sin envío automático) |
