import logging

import httpx
from bs4 import BeautifulSoup

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.getonbrd.com"


def _parse_category_html(html: str) -> list[Job]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for card in soup.select("a.results-item"):
        try:
            # -remote is appended to every job slug in a category regardless
            # of actual work mode — only this badge reliably signals fully
            # remote (vs. hybrid/on-site).
            if not card.select_one("i.perk-remote_full"):
                continue

            url = card.get("href", "")
            title_el = card.select_one("h4.results-list-title strong")
            company_el = card.select_one("div.results-list-info div.size0 strong")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            if not title or not url:
                continue

            jobs.append(
                Job(
                    title=title,
                    company=company,
                    location="Remote",
                    url=url,
                    source=JobSource.GETONBOARD,
                    is_remote=True,
                    description=card.get("title", ""),
                )
            )
        except Exception as exc:
            logger.warning("GetOnBoard: skipping malformed job card: %s", exc)
            continue

    return jobs


async def scrape(config: Settings) -> list[Job]:
    jobs: list[Job] = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(
        headers={"User-Agent": "WorkSearcher/1.0"},
        timeout=config.HTTP_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as client:
        for category in config.getonboard_categories_list:
            try:
                response = await client.get(f"{_BASE_URL}/jobs/{category}")
                response.raise_for_status()
            except Exception as exc:
                logger.warning("GetOnBoard: category '%s' failed: %s", category, exc)
                continue

            for job in _parse_category_html(response.text):
                if job.url in seen_urls:
                    continue
                seen_urls.add(job.url)
                jobs.append(job)

    logger.info("GetOnBoard: %d jobs found", len(jobs))
    return jobs
