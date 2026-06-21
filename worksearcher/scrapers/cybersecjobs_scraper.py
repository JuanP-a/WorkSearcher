import logging

import httpx
from bs4 import BeautifulSoup

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

CJS_URL = "https://cybersecjobs.com"

# CSS selectors tried in order — update if site changes structure
_JOB_CARD_SELECTORS = [
    "article.job_listing",
    "li.job_listing",
    ".job-listing",
    ".job-post",
    "article.job",
]


def _find_job_cards(soup: BeautifulSoup) -> list:
    for selector in _JOB_CARD_SELECTORS:
        cards = soup.select(selector)
        if cards:
            logger.debug("CyberSecJobs: matched selector '%s' (%d cards)", selector, len(cards))
            return cards
    return []


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (compatible; WorkSearcher/1.0)"},
            timeout=30,
            follow_redirects=True,
        ) as client:
            response = await client.get(CJS_URL)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        cards = _find_job_cards(soup)

        if not cards:
            logger.warning(
                "CyberSecJobs: no job cards found — site structure may have changed. "
                "Check selectors in cybersecjobs_scraper.py"
            )
            return []

        jobs = []
        for card in cards:
            try:
                title_el = card.find(["h2", "h3", "h4"]) or card.find(class_=lambda c: c and "title" in c)
                link_el = card.find("a", href=True)
                company_el = card.find(class_=lambda c: c and "company" in c)

                title = title_el.get_text(strip=True) if title_el else ""
                href = link_el["href"] if link_el else ""
                company = company_el.get_text(strip=True) if company_el else ""

                if not title or not href:
                    continue

                job_url = href if href.startswith("http") else f"{CJS_URL}{href}"

                jobs.append(Job(
                    title=title,
                    company=company,
                    location="Remote",
                    url=job_url,
                    source=JobSource.CYBERSECJOBS,
                    is_remote=True,
                ))
            except Exception as exc:
                logger.warning("CyberSecJobs: skipping malformed card: %s", exc)
                continue

        logger.info("CyberSecJobs: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("CyberSecJobs scraper failed: %s", exc)
        return []
