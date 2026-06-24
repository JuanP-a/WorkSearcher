# Flujo de trabajo — WorkSearcher

## Hacer un cambio (feature o fix)

```
1. Crear spec en specs/<nombre>.md
   └─ Formato SDD: Outcomes, Scope, Constraints, Prior Decisions, Task Breakdown, Verification Criteria

2. Crear rama feature
   git checkout -b feat/<número>-<nombre-corto>

3. Para cada task del plan:
   a. Escribir test que falla (pytest -v)
   b. Confirmar que falla por la razón correcta
   c. Implementar lo mínimo para pasar
   d. Confirmar verde
   e. Commit: git commit -m "feat: descripción"

4. Verificar todo
   source .venv/bin/activate
   pytest -q                          # debe ser 0 failures
   uvx ruff check worksearcher/ tests/  # debe ser 0 errores

5. Push + PR a main
   git push -u origin <rama>
   gh pr create ...
```

---

## Añadir un scraper nuevo

1. Crear `worksearcher/scrapers/<plataforma>_scraper.py` con la interfaz:
   ```python
   async def scrape(config: Settings) -> list[Job]:
       ...  # devuelve [] en cualquier error
   ```
2. Añadir `<PLATAFORMA> = "<plataforma>"` a `JobSource` en `models.py`.
3. Añadir al array `_SCRAPERS` en `main.py`.
4. Añadir tests en `tests/test_scrapers.py` con fixture + `respx.mock`.
5. Actualizar tabla de plataformas en `CLAUDE.md`, `README.md`, `docs/arquitectura.md`.

---

## Añadir un filtro nuevo

1. Añadir función pura `is_<criterio>(job: Job, param) -> bool` en `filters.py`.
   - Regla: si el campo relevante es `None`, devolver `True` (fail-open).
2. Añadir parámetro opcional a `filter_jobs` con default `None`.
3. Añadir setting correspondiente a `config.py` (con default sensato).
4. Añadir el campo a `FakeSettings` en `tests/conftest.py`.
5. Pasar el nuevo param en la llamada a `filter_jobs` en `main.py`.
6. Añadir tests en `test_filters.py`: caso normal, caso borde, caso `None`.

---

## Setup local

```bash
# Prereqs: Python 3.12, uv, mise
cp .env.example .env
# Rellenar META_PHONE_NUMBER_ID, META_ACCESS_TOKEN, META_RECIPIENT_PHONE

uv venv
uv pip install -r requirements.txt
uv run playwright install chromium

# En Ubuntu/Debian también:
# playwright install-deps chromium

# Ejecutar pipeline completo:
uv run python -m worksearcher run

# Tests:
source .venv/bin/activate && pytest -q
```

---

## Deploy en VPS

[PENDIENTE: setup.sh no existe — pasos manuales basados en README y deuda-tecnica.md]

```bash
# En VPS (Ubuntu 22.04):
git clone <repo> /app
cd /app && uv venv && uv pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium          # ← necesario en Linux (DEVOPS-3)
cp .env.example .env && nano .env         # rellenar secrets

# Crontab (crontab -e):
0 */4 * * * cd /app && uv run python -m worksearcher run >> /var/log/worksearcher.log 2>&1

# Logrotate (DEVOPS-2 — pendiente):
# /etc/logrotate.d/worksearcher — daily, compress, 14 días

# BD en ubicación correcta (DEVOPS-7 — pendiente):
# Mover worksearcher.db a /var/lib/worksearcher/
```

---

## Checklist de "terminado"

- [ ] Tests pasan: `pytest -q` → 0 failures
- [ ] Linter limpio: `uvx ruff check worksearcher/ tests/` → 0 errors
- [ ] Spec cubierta: cada Verification Criteria tiene un test
- [ ] `FakeSettings` actualizado si `Settings` cambió
- [ ] Docs actualizados: `CLAUDE.md`, `README.md`, `docs/arquitectura.md`
- [ ] PR creado con descripción de cambios y test plan
- [ ] CI verde en GitHub Actions

---

## CI (GitHub Actions)

`.github/workflows/ci.yml` — dispara en push y PR a main:
1. Setup Python 3.12 + uv via `jdx/mise-action`
2. `uv pip install -r requirements.txt`
3. `pytest -q`
4. `uvx ruff check worksearcher/ tests/`

jobspy no se instala en CI (evita el `git+https://...` que puede ser lento/inestable).
Tests de jobspy_scraper no existen — el scraper se testea manualmente.
