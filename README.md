# WorkSearcher

Buscador de trabajo automatizado. Scraping de 11 plataformas, filtrado por keywords + fecha + blacklist + idioma + salario, notificación vía WhatsApp.

## Setup local

```bash
cp .env.example .env
# Rellenar .env con META_PHONE_NUMBER_ID, META_ACCESS_TOKEN, META_RECIPIENT_PHONE

uv venv
uv pip install -r requirements.txt
uv run playwright install chromium

uv run python -m worksearcher run
```

## Deploy en VPS (Ubuntu 22.04)

```bash
git clone <repo> /opt/worksearcher
cd /opt/worksearcher
cp .env.example .env
# Editar .env: META_* secrets + DB_PATH=/var/lib/worksearcher/worksearcher.db

sudo bash deploy/setup.sh   # instala deps, playwright, logrotate, crea /var/lib/worksearcher/
crontab -e                  # pegar línea de crontab.example
```

`deploy/setup.sh` instala:
- dependencias del sistema
- uv + paquetes Python (desde `requirements.lock`)
- Chromium + `playwright install-deps chromium` (libs de sistema para Playwright)
- `/etc/logrotate.d/worksearcher` (rotación diaria, 14 días, comprimido)
- directorio `/var/lib/worksearcher/` para la DB

## Variables de entorno relevantes

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SEARCH_KEYWORDS` | 23 términos | Filtro post-scraping aplicado a todos los scrapers |
| `JOBSPY_SEARCH_TERMS` | 5 términos | Query enviada a LinkedIn/Indeed/Glassdoor (máx 5) |
| `MAX_YEARS_EXPERIENCE` | `3` | Jobs que piden más años son descartados |
| `MAX_JOB_AGE_DAYS` | `30` | Jobs con `posted_at` mayor a N días son descartados |
| `BLACKLIST_KEYWORDS` | 18 términos | Keywords en título/descripción que descartan el job |
| `FILTER_LANGUAGES` | `en,es` | Idiomas permitidos (ISO 639-1, comma-separated) |
| `MIN_SALARY_USD_MONTHLY` | vacío | Salario mínimo mensual en USD; vacío = sin filtro |
| `DB_PATH` | `worksearcher.db` | Path a la BD SQLite; en VPS usar `/var/lib/worksearcher/worksearcher.db` |
| `SCRAPE_INTERVAL_HOURS` | `4` | Referencia para configurar cron |

## Docs

- `CLAUDE.md` — constitución del proyecto (stack, convenciones, ADRs)
- `specs/` — specs de features (SDD)
- `docs/` — documentación técnica
- `.env.example` — plantilla de configuración completa
- `deploy/` — scripts y configuraciones para VPS
