import logging

import httpx
from bs4 import BeautifulSoup

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

# isecjobs.com — 21k+ cybersecurity jobs, remote filter built-in
_ISECJOBS_URL = "https://isecjobs.com/?remote=1"
_BASE_URL = "https://isecjobs.com"


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "WorkSearcher/1.0"},
            timeout=config.HTTP_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            response = await client.get(_ISECJOBS_URL)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        job_links = soup.select("a.stretched-link[href^='/job/']")

        if not job_links:
            logger.warning(
                "CyberSecJobs(isecjobs): no job links found — site structure may have changed"
            )
            return []

        jobs = []
        missing_company = 0
        for link in job_links:
            try:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or not href:
                    continue

                job_url = f"{_BASE_URL}{href}" if href.startswith("/") else href

                # isecjobs listing page doesn't always expose company — try common card patterns
                card = link.find_parent(class_=lambda c: c and "card" in c)
                company = ""
                if card:
                    for selector in ("small", ".text-muted", "p"):
                        el = card.select_one(selector)
                        if el and el.get_text(strip=True):
                            company = el.get_text(strip=True)
                            break
                if not company:
                    missing_company += 1

                jobs.append(
                    Job(
                        title=title,
                        company=company,
                        location="Remote",
                        url=job_url,
                        source=JobSource.CYBERSECJOBS,
                        is_remote=True,
                    )
                )
            except Exception as exc:
                logger.warning("CyberSecJobs(isecjobs): skipping malformed link: %s", exc)
                continue

        if missing_company:
            logger.warning(
                "CyberSecJobs(isecjobs): %d/%d jobs missing company name",
                missing_company,
                len(jobs),
            )

        logger.info("CyberSecJobs(isecjobs): %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("CyberSecJobs scraper failed: %s", exc)
        return []
