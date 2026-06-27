"""OCC scraper — remote + local (Celaya) jobs for Mexico.

Remote: /tipo-home-office-remoto/ path segment.
Local:  /en-{state}/en-{city}/ path segments when SEARCH_LOCAL_ENABLED.
"""

import asyncio
import logging
import threading

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource
from worksearcher.core.utils import slugify

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.occ.com.mx"


def _build_url(term: str, city: str = "", state: str = "") -> str:
    if city:
        return f"{_BASE_URL}/empleos/de-{slugify(term)}/en-{slugify(state)}/en-{slugify(city)}/"
    return f"{_BASE_URL}/empleos/de-{slugify(term)}/tipo-home-office-remoto/"


def _scrape_term(
    page,
    term: str,
    city: str,
    state: str,
    is_remote: bool,
    seen_urls: set[str],
    page_timeout_ms: int,
    selector_timeout_ms: int,
) -> list[Job]:
    from playwright.sync_api import TimeoutError as PWTimeout

    jobs: list[Job] = []
    url = _build_url(term, city, state)
    logger.debug("OCC: fetching %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=page_timeout_ms)

    if "403" in page.title() or "Forbidden" in page.title():
        raise RuntimeError("403 received — aborting")

    try:
        page.wait_for_selector("a[href*='/empleo/']", timeout=selector_timeout_ms)
    except PWTimeout:
        logger.warning("OCC: no job cards loaded for '%s'", term)
        return jobs

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

            title = next((ln for ln in lines if len(ln) > 3), "")
            company_idx = lines.index(title) + 1 if title in lines else -1
            company = lines[company_idx] if 0 < company_idx < len(lines) else ""

            if not title:
                continue

            jobs.append(
                Job(
                    title=title,
                    company=company,
                    location=city.title() if city else "Remote",
                    url=job_url,
                    source=JobSource.OCC,
                    is_remote=is_remote,
                )
            )
        except Exception as exc:
            logger.warning("OCC: skipping malformed link: %s", exc)
            continue

    return jobs


def _blocking_scrape(config: Settings, stop: threading.Event | None = None) -> list[Job]:
    from playwright.sync_api import sync_playwright

    jobs: list[Job] = []
    seen_urls: set[str] = set()

    local_city = config.MX_SEARCH_CITY.strip().lower() if config.SEARCH_LOCAL_ENABLED else ""
    local_state = config.MX_SEARCH_STATE.strip().lower() if local_city else ""

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

                pt = config.PLAYWRIGHT_PAGE_LOAD_TIMEOUT_MS
                st = config.PLAYWRIGHT_SELECTOR_TIMEOUT_MS

                # Remote pass
                page = context.new_page()
                try:
                    jobs.extend(
                        _scrape_term(
                            page, term, city="", state="", is_remote=True, seen_urls=seen_urls,
                            page_timeout_ms=pt, selector_timeout_ms=st,
                        )
                    )
                except RuntimeError as exc:
                    logger.warning("OCC (remote): %s — skipping remaining terms", exc)
                    page.close()
                    break
                except Exception as exc:
                    logger.warning("OCC: term '%s' remote failed: %s", term, exc)
                finally:
                    page.close()

                if local_city:
                    page = context.new_page()
                    try:
                        jobs.extend(
                            _scrape_term(
                                page,
                                term,
                                city=local_city,
                                state=local_state,
                                is_remote=False,
                                seen_urls=seen_urls,
                                page_timeout_ms=pt, selector_timeout_ms=st,
                            )
                        )
                    except RuntimeError as exc:
                        logger.warning("OCC (local): %s — skipping remaining terms", exc)
                        page.close()
                        break
                    except Exception as exc:
                        logger.warning("OCC: term '%s' local failed: %s", term, exc)
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
        stop.set()
        raise
    except Exception as exc:
        logger.error("OCC scraper failed: %s", exc)
        return []
