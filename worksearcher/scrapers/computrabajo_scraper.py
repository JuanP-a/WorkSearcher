"""Computrabajo scraper — remote + local (Celaya) jobs for Mexico."""

import asyncio
import logging

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource
from worksearcher.core.utils import slugify
from worksearcher.scrapers._playwright_common import (
    launch_stealth_browser,
    new_stealth_context,
    raise_if_blocked,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://mx.computrabajo.com"

_REMOTE_MARKERS = {"remoto", "home office", "teletrabajo"}


def _build_url(keyword: str, city: str = "") -> str:
    base = f"{_BASE_URL}/trabajo-de-{slugify(keyword)}"
    return f"{base}/en-{slugify(city)}" if city else base


def _scrape_keyword(
    page,
    keyword: str,
    city: str,
    is_remote: bool,
    seen_urls: set[str],
    page_timeout_ms: int,
    selector_timeout_ms: int,
) -> list[Job]:
    from playwright.sync_api import TimeoutError as PWTimeout

    jobs: list[Job] = []
    url = _build_url(keyword, city)
    logger.debug("Computrabajo: fetching %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=page_timeout_ms)
    raise_if_blocked(page)

    try:
        page.wait_for_selector("article.box_offer", timeout=selector_timeout_ms)
    except PWTimeout:
        logger.warning("Computrabajo: no job cards loaded for '%s'", keyword)
        return jobs

    for article in page.query_selector_all("article.box_offer"):
        try:
            title_el = article.query_selector("h2 a")
            company_el = article.query_selector("p.dFlex a")
            link_el = article.query_selector("h2 a")

            title = title_el.inner_text().strip() if title_el else ""
            company = company_el.inner_text().strip() if company_el else ""
            href = link_el.get_attribute("href") if link_el else ""

            if not title or not href:
                continue

            job_url = f"{_BASE_URL}{href}" if href.startswith("/") else href
            if job_url in seen_urls:
                continue
            seen_urls.add(job_url)

            article_text = article.inner_text().lower()
            if not city:
                if not any(m in article_text for m in _REMOTE_MARKERS):
                    continue

            jobs.append(
                Job(
                    title=title,
                    company=company,
                    location=city.title() if city else "Remote",
                    url=job_url,
                    source=JobSource.COMPUTRABAJO,
                    is_remote=is_remote,
                )
            )
        except Exception as exc:
            logger.warning("Computrabajo: skipping malformed card: %s", exc)
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

            for keyword in config.computrabajo_search_terms_list:
                pt = config.PLAYWRIGHT_PAGE_LOAD_TIMEOUT_MS
                st = config.PLAYWRIGHT_SELECTOR_TIMEOUT_MS

                page = context.new_page()
                try:
                    # Remote pass
                    jobs.extend(
                        _scrape_keyword(
                            page,
                            keyword,
                            city="",
                            is_remote=True,
                            seen_urls=seen_urls,
                            page_timeout_ms=pt,
                            selector_timeout_ms=st,
                        )
                    )
                except RuntimeError as exc:
                    logger.warning("Computrabajo (remote): %s — skipping remaining keywords", exc)
                    page.close()
                    break
                except Exception as exc:
                    logger.warning("Computrabajo: keyword '%s' remote failed: %s", keyword, exc)
                finally:
                    page.close()

                if local_city:
                    page = context.new_page()
                    try:
                        jobs.extend(
                            _scrape_keyword(
                                page,
                                keyword,
                                city=local_city,
                                is_remote=False,
                                seen_urls=seen_urls,
                                page_timeout_ms=pt,
                                selector_timeout_ms=st,
                            )
                        )
                    except RuntimeError as exc:
                        logger.warning(
                            "Computrabajo (local): %s — skipping remaining keywords", exc
                        )
                        page.close()
                        break
                    except Exception as exc:
                        logger.warning("Computrabajo: keyword '%s' local failed: %s", keyword, exc)
                    finally:
                        page.close()
        finally:
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
