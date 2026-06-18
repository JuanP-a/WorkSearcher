import httpx
import logging

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

REMOTEOK_API = "https://remoteok.com/api"


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "WorkSearcher/1.0"},
            timeout=30,
        ) as client:
            response = await client.get(REMOTEOK_API)
            response.raise_for_status()
            data = response.json()

        # First item in RemoteOK API response is metadata — skip it
        listings = [item for item in data if isinstance(item, dict) and "position" in item]
        jobs = []
        for item in listings:
            try:
                job = Job(
                    title=item.get("position", ""),
                    company=item.get("company", ""),
                    location="Remote",
                    url=f"https://remoteok.com/remote-jobs/{item.get('slug', '')}",
                    source=JobSource.REMOTEOK,
                    is_remote=True,
                    description=item.get("description", ""),
                )
                jobs.append(job)
            except Exception:
                continue

        logger.info("RemoteOK: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("RemoteOK scraper failed: %s", exc)
        return []
