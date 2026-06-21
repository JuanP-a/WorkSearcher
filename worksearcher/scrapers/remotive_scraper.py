import httpx
import logging

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

REMOTIVE_API = "https://remotive.com/api/remote-jobs"


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(REMOTIVE_API)
            response.raise_for_status()
            data = response.json()

        listings = data.get("jobs", [])
        jobs = []
        for item in listings:
            try:
                job = Job(
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    location=item.get("candidate_required_location", "Remote"),
                    url=item.get("url", ""),
                    source=JobSource.REMOTIVE,
                    is_remote=True,
                    description=item.get("description", ""),
                )
                jobs.append(job)
            except Exception as exc:
                logger.warning("Remotive: skipping malformed job %s: %s", item.get("id", "?"), exc)
                continue

        logger.info("Remotive: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("Remotive scraper failed: %s", exc)
        return []
