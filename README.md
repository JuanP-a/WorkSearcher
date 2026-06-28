# WorkSearcher

Buscador de trabajo automatizado. Scraping de 11 plataformas, filtrado por keywords + fecha + blacklist + idioma + salario, notificación vía WhatsApp.

## Setup local

```bash
cp .env.example .env
# Rellenar .env con META_PHONE_NUMBER_ID, META_ACCESS_TOKEN, META_RECIPIENT_PHONE

uv venv
uv pip install -r requirements.txt          # deps sin hashes — solo para desarrollo local
uv run playwright install chromium

uv run python -m worksearcher run
```

## Deploy en VPS (Ubuntu 22.04)

```bash
git clone <repo> /opt/worksearcher
cd /opt/worksearcher
cp .env.example .env
# Editar .env: META_* secrets + DB_PATH=/var/lib/worksearcher/worksearcher.db

sudo bash deploy/setup.sh         # instala deps, playwright, logrotate, uv en /usr/local/bin
sudo bash deploy/harden.sh        # UFW, fail2ban, unattended-upgrades, SSH hardening
sudo -u worksearcher crontab -e   # pegar línea de crontab.example
```

`deploy/setup.sh` instala:
- dependencias del sistema
- uv `0.11.24` en `/usr/local/bin/uv` (accesible por cron sin PATH)
- paquetes Python desde `requirements.hashes.lock` (`--require-hashes`) + jobspy desde git SHA pinneado
- Chromium + `playwright install-deps chromium` (libs de sistema para Playwright)
- `/etc/logrotate.d/worksearcher` (rotación diaria, 14 días, comprimido)
- directorio `/var/lib/worksearcher/` con permisos para el usuario `worksearcher`

`deploy/harden.sh` aplica (idempotente):
- SSH: deshabilita root login y password auth (drop-in en `/etc/ssh/sshd_config.d/`)
- UFW: deny incoming por default, allow OpenSSH
- fail2ban: 3 reintentos fallidos en 10 min → ban de 1h
- `unattended-upgrades`: parches de seguridad auto-aplicados sin reboot

## Variables de entorno relevantes

Ver `.env.example` para la referencia completa con comentarios.

### Selección de plataformas

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ENABLED_SCRAPERS` | todos (9) | Lista separada por comas de scrapers activos |

### jobspy (LinkedIn / Indeed / Glassdoor)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `JOBSPY_SEARCH_TERMS` | 5 términos | Query enviada a jobspy (máx 5 términos) |
| `JOBSPY_SITES` | `linkedin,indeed,glassdoor` | Plataformas que jobspy consulta |
| `SEARCH_LOCATION` | `Remote` | Alcance geográfico (ej. `"Mexico City"`) |
| `JOBSPY_RESULTS_WANTED` | `50` | Resultados máximos por plataforma por ejecución |
| `JOBSPY_HOURS_OLD` | `24` | Solo jobs publicados en las últimas N horas |

### Scrapers LatAm

| Variable | Default | Descripción |
|----------|---------|-------------|
| `BUMERAN_SEARCH_TERMS` | 5 términos ES | Términos de búsqueda para Bumeran MX |
| `COMPUTRABAJO_SEARCH_TERMS` | 5 términos ES | Términos de búsqueda para Computrabajo MX |

### Filtros post-scraping

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SEARCH_KEYWORDS` | 23 términos | Filtro aplicado a todos los scrapers |
| `MAX_YEARS_EXPERIENCE` | `3` | Jobs que piden más años son descartados |
| `MAX_JOB_AGE_DAYS` | `30` | Jobs con `posted_at` mayor a N días son descartados |
| `BLACKLIST_KEYWORDS` | 18 términos | Keywords en título/descripción que descartan el job |
| `FILTER_LANGUAGES` | `en,es` | Idiomas permitidos (ISO 639-1, comma-separated) |
| `MIN_SALARY_USD_MONTHLY` | vacío | Salario mínimo mensual en USD; vacío = sin filtro |

### Notificaciones y rendimiento

| Variable | Default | Descripción |
|----------|---------|-------------|
| `MAX_JOBS_PER_MESSAGE` | `10` | Máx. empleos por mensaje WhatsApp |
| `HTTP_TIMEOUT_SECONDS` | `30` | Timeout HTTP para scrapers httpx |
| `SCRAPER_TIMEOUT_SECONDS` | `120` | Timeout por scraper en el pipeline |

### Almacenamiento

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DB_PATH` | `worksearcher.db` | Path a la BD SQLite; en VPS usar `/var/lib/worksearcher/worksearcher.db` |

## Docs

- `CLAUDE.md` — constitución del proyecto (stack, convenciones, ADRs)
- `specs/` — specs de features (SDD)
- `docs/` — documentación técnica
- `.env.example` — plantilla de configuración completa
- `deploy/` — scripts y configuraciones para VPS
