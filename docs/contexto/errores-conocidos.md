# Errores conocidos y gotchas — WorkSearcher

## Críticos / Data-corrupting

### `cursor.rowcount` tras `executemany + INSERT OR IGNORE` es indefinido
**Archivo:** `worksearcher/storage/database.py:68`
CPython no garantiza `cursor.rowcount` después de `executemany`. Con `INSERT OR IGNORE`,
los duplicados silenciados tampoco cuentan. El log `"Inserted N jobs"` puede mostrar `-1`.
**Workaround actual:** Ninguno. El pipeline funciona correctamente; solo el log de conteo es incorrecto.
**Fix correcto:** `conn.execute("SELECT changes()").fetchone()[0]` inmediatamente después del `executemany`.

### `get_unnotified_jobs` descarta jobs si `JobSource` no reconoce el valor
**Archivo:** `worksearcher/storage/database.py:88`
El `except Exception: continue` silencia `ValueError` si la columna `source` tiene un valor
que ya no está en el enum (e.g. plataforma eliminada). El job queda en BD con `notified=0` para siempre.
**Workaround:** Ninguno. Si se elimina un `JobSource`, limpiar la BD manualmente.

---

## Comportamientos no obvios

### `langdetect` es no-determinista
Llamadas sucesivas a `detect_langs()` con el mismo texto pueden devolver resultados distintos.
**En tests:** siempre mockear `"worksearcher.core.filters.detect_langs"` — nunca llamar la función real.
**En producción:** el umbral de 0.8 mitiga inconsistencias, pero un mismo job podría pasar o fallar entre runs.

### `salary_min` de RemoteOK es USD anual, no mensual
La API devuelve `salary_min: 60000` para un job de $60k/año ($5k/mes).
El código ya divide por 12, pero cualquier fixture de test debe usar valores anuales realistas
(ej: `60000`), no `1500` (que sería $18k/año).

### `posted_at` de jobspy tiene granularidad de día (no hora)
`date_posted` del DataFrame de jobspy es `datetime.date`, no `datetime`. Se convierte a
`datetime(year, month, day, tzinfo=UTC)` — medianoche UTC. Esto introduce hasta 24h de imprecisión
en el filtro de antigüedad para jobs de LinkedIn/Indeed/Glassdoor.

### `JOBSPY_SEARCH_TERMS` tiene límite duro de 5 términos
El validator en `config.py` lanza `ValueError` en startup si hay más de 5.
El pipeline no arranca — no falla silenciosamente.

### HackerNews: "REMOTE" como substring (case-insensitive)
`is_remote` se detecta buscando `"REMOTE"` en el texto plano del comentario.
No detecta: "remote-friendly", "fully distributed", "async-first", "work from anywhere".
Jobs con esas frases se marcan `is_remote=False` y el pipeline los descarta en `is_relevant`.

### `worksearcher.db` — ubicación configurable via `DB_PATH`
La ruta por defecto (`worksearcher.db`) es relativa al cwd. En VPS se configura vía `.env`:
`DB_PATH=/var/lib/worksearcher/worksearcher.db`. `deploy/setup.sh` crea el directorio con el owner correcto.
En dev local, la BD queda en la raíz del repo (comportamiento anterior, sin cambio).

### Himalayas solo procesa salarios en USD
Si `currency != "USD"`, `min_salary_usd_monthly` queda en `None` aunque el salario esté disponible.
Esto es intencional (no hay conversión de divisas), pero puede hacer que jobs de EUR/GBP pasen
el filtro de salario incluso si pagan menos del mínimo configurado.

### Salario con `salaryPeriod` no reconocido (ej: "hourly") se descarta silenciosamente
El scraper de Himalayas solo maneja `"annual"` y `"monthly"`. Cualquier otro valor emite
un `logger.debug` y deja `min_salary_usd_monthly = None`. El job pasa el filtro de salario.

---

## Deuda técnica pendiente

Ver `docs/deuda-tecnica.md` para detalle completo. Sin items pendientes — todos los issues de VPS resueltos.

---

## Tests que no existen (cobertura conocida cero)

- `jobspy_scraper.py` — testear requiere mockear un DataFrame de pandas; nunca se hizo.
- Scrapers Playwright (`computrabajo`, `bumeran`) — solo se testean funciones puras extraídas;
  el flujo completo requiere browser real.
- `_run_pipeline` con config real (`.env`) — solo se testea con `FakeSettings` + mocks.
