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
            timeout=30,
            follow_redirects=True,
        ) as client:
            response = await client.get(_ISECJOBS_URL)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        job_links = soup.select("a.stretched-link[href^='/job/']")

        if not job_links:
            logger.warning("CyberSecJobs(isecjobs): no job links found — site structure may have changed")
            return []

        jobs = []
        for link in job_links:
            try:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or not href:
                    continue

                job_url = f"{_BASE_URL}{href}" if href.startswith("/") else href

                jobs.append(Job(
                    title=title,
                    company="",
                    location="Remote",
                    url=job_url,
                    source=JobSource.CYBERSECJOBS,
                    is_remote=True,
                ))
            except Exception as exc:
                logger.warning("CyberSecJobs(isecjobs): skipping malformed link: %s", exc)
                continue

        logger.info("CyberSecJobs(isecjobs): %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("CyberSecJobs scraper failed: %s", exc)
        return []
