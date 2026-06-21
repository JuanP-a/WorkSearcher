import asyncio
import logging
import re

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.bumeran.com.mx"


def _slug(keyword: str) -> str:
    slug = keyword.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    return re.sub(r"[\s]+", "-", slug)


def _extract_jobs_from_next_data(data: dict) -> list[dict]:
    """Navigate __NEXT_DATA__ to find job listings — Bumeran uses Next.js."""
    props = data.get("props", {}).get("pageProps", {})
    for key in ("postings", "jobs", "avisos", "results", "data"):
        items = props.get(key)
        if items and isinstance(items, list):
            return items
    # Sometimes nested deeper
    for value in props.values():
        if isinstance(value, dict):
            for key in ("postings", "jobs", "avisos"):
                items = value.get(key)
                if items and isinstance(items, list):
                    return items
    return []


def _blocking_scrape(config: Settings) -> list[Job]:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    jobs: list[Job] = []
    seen_urls: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        })

        for keyword in config.keywords_list[:5]:
            try:
                url = f"{_BASE_URL}/empleos-busqueda-{_slug(keyword)}.html"
                logger.debug("Bumeran: fetching %s", url)
                page.goto(url, wait_until="networkidle", timeout=30_000)

                # Try __NEXT_DATA__ JSON extraction (most reliable for Next.js apps)
                try:
                    next_data = page.evaluate(
                        "JSON.parse(document.getElementById('__NEXT_DATA__').textContent)"
                    )
                    postings = _extract_jobs_from_next_data(next_data)

                    if not postings:
                        logger.warning("Bumeran: __NEXT_DATA__ found but no postings key for '%s'", keyword)

                    for posting in postings:
                        try:
                            title = (
                                posting.get("title") or
                                posting.get("titulo") or
                                posting.get("nombre", "")
                            )
                            company_raw = posting.get("company") or posting.get("empresa") or {}
                            company = (
                                company_raw.get("name") or company_raw.get("nombre", "")
                                if isinstance(company_raw, dict)
                                else str(company_raw)
                            )
                            url_path = (
                                posting.get("url") or
                                posting.get("slug") or
                                posting.get("link", "")
                            )
                            job_url = (
                                f"{_BASE_URL}{url_path}" if url_path.startswith("/")
                                else url_path
                            )
                            description = posting.get("description") or posting.get("descripcion", "")

                            if not title or not job_url or job_url in seen_urls:
                                continue
                            seen_urls.add(job_url)

                            jobs.append(Job(
                                title=title,
                                company=company,
                                location="Remote",
                                url=job_url,
                                source=JobSource.BUMERAN,
                                is_remote=True,
                                description=description,
                            ))
                        except Exception as exc:
                            logger.warning("Bumeran: skipping malformed posting: %s", exc)
                            continue

                except Exception as exc:
                    logger.warning("Bumeran: __NEXT_DATA__ extraction failed for '%s': %s", keyword, exc)

            except Exception as exc:
                logger.warning("Bumeran: keyword '%s' failed: %s", keyword, exc)
                continue

        browser.close()

    return jobs


async def scrape(config: Settings) -> list[Job]:
    try:
        jobs = await asyncio.to_thread(_blocking_scrape, config)
        logger.info("Bumeran: %d jobs found", len(jobs))
        return jobs
    except Exception as exc:
        logger.error("Bumeran scraper failed: %s", exc)
        return []
