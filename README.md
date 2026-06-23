# WorkSearcher

Buscador de trabajo automatizado. Scraping de 9 plataformas, filtrado por keywords (dev + cybersecurity + automation), notificación vía WhatsApp.

## Setup

```bash
cp .env.example .env
# Rellenar .env con META_PHONE_NUMBER_ID, META_ACCESS_TOKEN, META_RECIPIENT_PHONE

uv venv
uv pip install -r requirements.txt
uv run playwright install chromium

uv run python -m worksearcher run
```

## Variables de entorno relevantes

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SEARCH_KEYWORDS` | 23 términos | Filtro post-scraping aplicado a todos los scrapers |
| `JOBSPY_SEARCH_TERMS` | 5 términos | Query enviada a LinkedIn/Indeed/Glassdoor (máx 5) |
| `MAX_YEARS_EXPERIENCE` | `3` | Jobs que piden más años son descartados |
| `SCRAPE_INTERVAL_HOURS` | `4` | Referencia para configurar cron |

## Cron (VPS)

```
0 */4 * * * cd /app && uv run python -m worksearcher run >> /var/log/worksearcher.log 2>&1
```

## Docs

- `CLAUDE.md` — constitución del proyecto (stack, convenciones, ADRs)
- `specs/` — specs de features (SDD)
- `docs/` — documentación técnica
- `.env.example` — plantilla de configuración completa
