import asyncio
import logging

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource
from worksearcher.core.utils import slugify

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.bumeran.com.mx"

_REMOTE_MARKERS = {"remoto", "home office", "teletrabajo", "trabajo remoto"}


def _blocking_scrape(config: Settings) -> list[Job]:
    from playwright.sync_api import sync_playwright

    jobs: list[Job] = []
    seen_urls: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = context.new_page()

            for term in config.bumeran_search_terms_list:
                try:
                    url = f"{_BASE_URL}/empleos-busqueda-{slugify(term)}.html"
                    logger.debug("Bumeran: fetching %s", url)
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    try:
                        page.wait_for_selector("a[href*='/empleos/']", timeout=10_000)
                    except Exception:
                        logger.warning("Bumeran: no job links found for '%s'", term)
                        continue

                    # Each job is an <a href="/empleos/..."> containing title + company in text
                    job_links = page.query_selector_all("a[href*='/empleos/']")
                    if not job_links:
                        logger.warning("Bumeran: no job links found for '%s'", term)
                        continue

                    for link in job_links:
                        try:
                            href = link.get_attribute("href") or ""
                            if not href or href in seen_urls:
                                continue

                            job_url = href if href.startswith("http") else f"{_BASE_URL}{href}"
                            seen_urls.add(href)

                            # Text lines: ["Publicado hace X días", "Job Title", "Company", "Location"]
                            raw = link.inner_text().strip()
                            lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]

                            title = next(
                                (
                                    ln
                                    for ln in lines
                                    if len(ln) > 5 and not ln.startswith("Publicado")
                                ),
                                "",
                            )
                            company_idx = lines.index(title) + 1 if title in lines else -1
                            company = lines[company_idx] if 0 < company_idx < len(lines) else ""

                            if not title:
                                continue

                            if not any(m in raw.lower() for m in _REMOTE_MARKERS):
                                continue

                            jobs.append(
                                Job(
                                    title=title,
                                    company=company,
                                    location="Remote",
                                    url=job_url,
                                    source=JobSource.BUMERAN,
                                    is_remote=True,
                                )
                            )
                        except Exception as exc:
                            logger.warning("Bumeran: skipping malformed link: %s", exc)
                            continue

                except Exception as exc:
                    logger.warning("Bumeran: term '%s' failed: %s", term, exc)
                    continue
        finally:
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
