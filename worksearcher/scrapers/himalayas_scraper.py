import logging
from datetime import datetime, timezone

import httpx

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

HIMALAYAS_API = "https://himalayas.app/jobs/api"


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "WorkSearcher/1.0"},
            timeout=30,
        ) as client:
            response = await client.get(HIMALAYAS_API, params={"limit": 50})
            response.raise_for_status()
            data = response.json()

        listings = data.get("jobs", [])
        jobs = []
        for item in listings:
            try:
                # Determine location from restrictions
                restrictions = item.get("locationRestrictions", [])
                location = restrictions[0] if restrictions else "Remote"

                # Prefer applicationLink, fall back to guid
                url = item.get("applicationLink", "") or item.get("guid", "")

                pub_date = item.get("pubDate")
                posted_at = (
                    datetime.fromtimestamp(pub_date, tz=timezone.utc) if pub_date else None
                )

                job = Job(
                    title=item.get("title", ""),
                    company=item.get("companyName", ""),
                    location=location,
                    url=url,
                    source=JobSource.HIMALAYAS,
                    is_remote=True,
                    description=item.get("description", ""),
                    posted_at=posted_at,
                )
                jobs.append(job)
            except Exception as exc:
                logger.warning("Himalayas: skipping malformed job %s: %s", item.get("title", "?"), exc)
                continue

        logger.info("Himalayas: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("Himalayas scraper failed: %s", exc)
        return []
