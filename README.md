# WorkSearcher

Buscador de trabajo automatizado. Scraping de múltiples plataformas, filtrado por keywords (dev + cybersecurity), notificación vía WhatsApp.

## Setup

```bash
cp .env.example .env
# Rellenar .env con tus tokens

pip install -r requirements.txt
playwright install chromium

python -m worksearcher run
```

## Cron (VPS)

```
0 */4 * * * cd /app && python -m worksearcher run >> /var/log/worksearcher.log 2>&1
```

## Docs

- `CLAUDE.md` — constitución del proyecto (stack, convenciones, ADRs)
- `specs/` — specs de features (SDD)
- `docs/` — documentación técnica
