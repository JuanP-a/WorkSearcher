import asyncio
import logging
import re

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.computrabajo.com.mx"

# Selectors tried in order — update if site changes structure
_ARTICLE_SELECTORS = "article.box_offer, article[data-code], article.offerBlock"
_TITLE_SELECTORS = "h2 a, a.js-o-link, [title]"
_COMPANY_SELECTORS = ".qt_location .fc_blue, .name_company, .company"


def _slug(keyword: str) -> str:
    slug = keyword.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    return re.sub(r"[\s]+", "-", slug)


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
                url = f"{_BASE_URL}/trabajo-de-{_slug(keyword)}"
                logger.debug("Computrabajo: fetching %s", url)
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)

                try:
                    page.wait_for_selector(_ARTICLE_SELECTORS, timeout=10_000)
                except PWTimeout:
                    logger.warning("Computrabajo: no job cards loaded for '%s'", keyword)
                    continue

                for article in page.query_selector_all(_ARTICLE_SELECTORS):
                    try:
                        title_el = article.query_selector(_TITLE_SELECTORS)
                        company_el = article.query_selector(_COMPANY_SELECTORS)
                        link_el = article.query_selector("a[href]")

                        title = title_el.inner_text().strip() if title_el else ""
                        company = company_el.inner_text().strip() if company_el else ""
                        href = link_el.get_attribute("href") if link_el else ""

                        if not title or not href:
                            continue

                        job_url = f"{_BASE_URL}{href}" if href.startswith("/") else href
                        if job_url in seen_urls:
                            continue
                        seen_urls.add(job_url)

                        jobs.append(Job(
                            title=title,
                            company=company,
                            location="Remote",
                            url=job_url,
                            source=JobSource.COMPUTRABAJO,
                            is_remote=True,
                        ))
                    except Exception as exc:
                        logger.warning("Computrabajo: skipping malformed card: %s", exc)
                        continue

            except Exception as exc:
                logger.warning("Computrabajo: keyword '%s' failed: %s", keyword, exc)
                continue

        browser.close()

    return jobs


async def scrape(config: Settings) -> list[Job]:
    try:
        jobs = await asyncio.to_thread(_blocking_scrape, config)
        logger.info("Computrabajo: %d jobs found", len(jobs))
        return jobs
    except Exception as exc:
        logger.error("Computrabajo scraper failed: %s", exc)
        return []
