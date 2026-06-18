# Design: WorkSearcher — Automated Job Searcher

**Date:** 2026-06-18
**Status:** Approved
**Author:** JuanP-a

## Context

Automated job search tool for a computer systems engineer (dev + cybersecurity) seeking remote work in LatAm and globally. Built on Option B: modular service + WhatsApp notifications + SQLite. Low-cost constraint: ~€3-4/month total (VPS only).

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  Scrapers   │───▶│   Pipeline   │───▶│  Notifier   │
│ (per board) │    │ filter+dedup │    │  WhatsApp   │
└─────────────┘    └──────┬───────┘    └─────────────┘
                          │
                   ┌──────▼───────┐
                   │   SQLite DB  │
                   │  (history)   │
                   └──────────────┘
                          ▲
                   ┌──────┴───────┐
                   │  cron job    │
                   │  (every 4h)  │
                   └──────────────┘
```

**Functional core / imperative shell:**
- Shell: scrapers (I/O), DB reads/writes, WhatsApp API calls
- Core: filtering logic, deduplication, job matching (pure functions, no I/O)

## Module Breakdown

| Module | Responsibility |
|---|---|
| `scrapers/jobspy_scraper.py` | LinkedIn, Indeed, Glassdoor via jobspy |
| `scrapers/remoteok_scraper.py` | RemoteOK public JSON API |
| `scrapers/remotive_scraper.py` | Remotive public JSON API |
| `scrapers/computrabajo_scraper.py` | Computrabajo via playwright |
| `scrapers/cybersecjobs_scraper.py` | CyberSecJobs via httpx + BS4 |
| `core/models.py` | Pydantic Job model |
| `core/filters.py` | Keyword matching, remote check (pure) |
| `core/deduplicator.py` | hash(title + company + url) |
| `storage/database.py` | SQLite CRUD + ON CONFLICT DO NOTHING |
| `notifier/whatsapp.py` | Meta Cloud API sender |
| `config.py` | Pydantic Settings from .env |
| `main.py` | Click CLI orchestrator |

## Data Model

```python
class Job(BaseModel):
    title: str
    company: str
    location: str
    url: str
    source: str          # "linkedin" | "remoteok" | "computrabajo" | ...
    is_remote: bool
    description: str
    posted_at: datetime | None
    fingerprint: str     # hash(title + company + url) — dedup key
```

## Pipeline Flow

1. cron triggers `python -m worksearcher run`
2. All scrapers run concurrently (`asyncio.gather`)
3. Results merged into flat list of `Job` objects
4. Filter: keywords match (dev OR cyber) AND remote=True
5. Dedup: discard jobs with fingerprint already in DB
6. Persist new jobs to SQLite
7. If new jobs > 0: send WhatsApp digest

## Cost Breakdown

| Item | Cost |
|---|---|
| Hetzner CX11 VPS (2GB/2CPU) | ~€3.29/month |
| Meta Cloud API | €0 (free tier) |
| Webshare proxies | €0 (free tier, 10 proxies) |
| jobspy | €0 |
| **Total** | **~€3-4/month** |

## Key Technical Decisions

- **No Postgres**: SQLite is sufficient, zero infra cost
- **No APScheduler**: system cron is simpler and survives reboots  
- **Meta Cloud API over whatsapp-web.js**: official API, no ban risk, free tier covers personal use
- **jobspy for major boards**: handles LinkedIn/Indeed scraping, maintained by community
- **asyncio for scrapers**: parallel scraping reduces wall-clock time

## Patterns Adopted from Reference Repos

- **readytotouch**: batch upsert with `ON CONFLICT DO NOTHING`, enum-based source tracking
- **oxylabs**: Pydantic models at boundary, playwright anti-detection args, scraper/persistence separation, Click CLI

## Deployment

```
VPS: Hetzner CX11
OS: Ubuntu 22.04
Crontab: 0 */4 * * * cd /app && python -m worksearcher run >> /var/log/worksearcher.log 2>&1
```
