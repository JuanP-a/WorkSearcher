"""Bumeran scraper — remote + local (Celaya) jobs for Mexico."""

import asyncio
import logging

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource
from worksearcher.core.utils import slugify
from worksearcher.scrapers._playwright_common import (
    launch_stealth_browser,
    new_stealth_context,
    parse_title_and_company,
    raise_if_blocked,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.bumeran.com.mx"

_REMOTE_MARKERS = {"remoto", "home office", "teletrabajo", "trabajo remoto"}


def _build_url(term: str, city: str = "") -> str:
    base = f"{_BASE_URL}/empleos-busqueda-{slugify(term)}"
    return f"{base}-en-{slugify(city)}.html" if city else f"{base}.html"


def _scrape_term(
    page,
    term: str,
    city: str,
    is_remote: bool,
    seen_urls: set[str],
    page_timeout_ms: int,
    selector_timeout_ms: int,
) -> list[Job]:
    jobs: list[Job] = []
    url = _build_url(term, city)
    logger.debug("Bumeran: fetching %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=page_timeout_ms)
    raise_if_blocked(page)
    try:
        page.wait_for_selector("a[href*='/empleos/']", timeout=selector_timeout_ms)
    except Exception:
        logger.warning("Bumeran: no job links found for '%s'", term)
        return jobs

    job_links = page.query_selector_all("a[href*='/empleos/']")
    if not job_links:
        logger.warning("Bumeran: no job links found for '%s'", term)
        return jobs

    for link in job_links:
        try:
            href = link.get_attribute("href") or ""
            if not href or href in seen_urls:
                continue

            job_url = href if href.startswith("http") else f"{_BASE_URL}{href}"
            seen_urls.add(href)

            raw = link.inner_text().strip()
            title, company = parse_title_and_company(raw)

            if not title:
                continue

            if not city:
                if not any(m in raw.lower() for m in _REMOTE_MARKERS):
                    continue

            jobs.append(
                Job(
                    title=title,
                    company=company,
                    location=city.title() if city else "Remote",
                    url=job_url,
                    source=JobSource.BUMERAN,
                    is_remote=is_remote,
                )
            )
        except Exception as exc:
            logger.warning("Bumeran: skipping malformed link: %s", exc)
            continue

    return jobs


def _blocking_scrape(config: Settings) -> list[Job]:
    from playwright.sync_api import sync_playwright

    jobs: list[Job] = []
    seen_urls: set[str] = set()
    local_city = config.MX_SEARCH_CITY.strip().lower() if config.SEARCH_LOCAL_ENABLED else ""

    with sync_playwright() as p:
        browser = launch_stealth_browser(p)
        try:
            context = new_stealth_context(browser)
            page = context.new_page()

            for term in config.bumeran_search_terms_list:
                pt = config.PLAYWRIGHT_PAGE_LOAD_TIMEOUT_MS
                st = config.PLAYWRIGHT_SELECTOR_TIMEOUT_MS

                try:
                    jobs.extend(
                        _scrape_term(
                            page,
                            term,
                            city="",
                            is_remote=True,
                            seen_urls=seen_urls,
                            page_timeout_ms=pt,
                            selector_timeout_ms=st,
                        )
                    )
                except RuntimeError as exc:
                    logger.warning("Bumeran (remote): %s — skipping remaining terms", exc)
                    break
                except Exception as exc:
                    logger.warning("Bumeran: term '%s' remote failed: %s", term, exc)
                    continue

                if local_city:
                    try:
                        jobs.extend(
                            _scrape_term(
                                page,
                                term,
                                city=local_city,
                                is_remote=False,
                                seen_urls=seen_urls,
                                page_timeout_ms=pt,
                                selector_timeout_ms=st,
                            )
                        )
                    except RuntimeError as exc:
                        logger.warning("Bumeran (local): %s — skipping remaining terms", exc)
                        break
                    except Exception as exc:
                        logger.warning("Bumeran: term '%s' local failed: %s", term, exc)
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
