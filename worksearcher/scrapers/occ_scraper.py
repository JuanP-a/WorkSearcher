import asyncio
import logging
import threading

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource
from worksearcher.core.utils import slugify

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.occ.com.mx"


def _build_url(term: str) -> str:
    return f"{_BASE_URL}/empleos/de-{slugify(term)}/tipo-home-office-remoto/"


def _blocking_scrape(config: Settings, stop: threading.Event | None = None) -> list[Job]:
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright

    jobs: list[Job] = []
    seen_urls: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ],
        )
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="es-MX",
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            for term in config.occ_search_terms_list:
                if stop and stop.is_set():
                    logger.warning("OCC: scrape cancelled before term '%s'", term)
                    break
                page = context.new_page()
                try:
                    url = _build_url(term)
                    logger.debug("OCC: fetching %s", url)
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)

                    if "403" in page.title() or "Forbidden" in page.title():
                        logger.warning("OCC: 403 received — skipping remaining terms")
                        break

                    try:
                        # OCC individual job URLs use /empleo/ (singular)
                        page.wait_for_selector("a[href*='/empleo/']", timeout=10_000)
                    except PWTimeout:
                        logger.warning("OCC: no job cards loaded for '%s'", term)
                        continue

                    job_links = page.query_selector_all("a[href*='/empleo/']")
                    for link in job_links:
                        try:
                            href = link.get_attribute("href") or ""
                            if not href or href in seen_urls:
                                continue

                            job_url = href if href.startswith("http") else f"{_BASE_URL}{href}"
                            seen_urls.add(href)

                            raw = link.inner_text().strip()
                            lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]

                            # OCC links may contain short UI strings before the title;
                            # > 3 chars filters badges/icons without hiding 4-char titles
                            title = next((ln for ln in lines if len(ln) > 3), "")
                            company_idx = lines.index(title) + 1 if title in lines else -1
                            company = lines[company_idx] if 0 < company_idx < len(lines) else ""

                            if not title:
                                continue

                            jobs.append(
                                Job(
                                    title=title,
                                    company=company,
                                    location="Remote",
                                    url=job_url,
                                    source=JobSource.OCC,
                                    is_remote=True,
                                )
                            )
                        except Exception as exc:
                            logger.warning("OCC: skipping malformed link: %s", exc)
                            continue

                except Exception as exc:
                    logger.warning("OCC: term '%s' failed: %s", term, exc)
                finally:
                    page.close()
        finally:
            browser.close()

    return jobs


async def scrape(config: Settings) -> list[Job]:
    logger.info("OCC: starting scrape for %d terms", len(config.occ_search_terms_list))
    stop = threading.Event()
    try:
        jobs = await asyncio.to_thread(_blocking_scrape, config, stop)
        logger.info("OCC: %d jobs found", len(jobs))
        return jobs
    except asyncio.CancelledError:
        # Signal the Playwright thread to stop starting new terms after wait_for cancels us.
        stop.set()
        raise
    except Exception as exc:
        logger.error("OCC scraper failed: %s", exc)
        return []
