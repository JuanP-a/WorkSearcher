import logging

import httpx
from bs4 import BeautifulSoup

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

# foorilla.com — "all coding" job board, filtered to the InfoSec & Privacy topic.
# isecjobs.com (the previous source) was shut down 2026-06-30.
_BASE_URL = "https://foorilla.com"
_INFOSEC_TOPIC_ID = "102"


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "WorkSearcher/1.0", "Referer": f"{_BASE_URL}/"},
            timeout=config.HTTP_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            home_response = await client.get(f"{_BASE_URL}/")
            home_response.raise_for_status()

            csrf_token = client.cookies.get("csrftoken")
            if not csrf_token:
                logger.warning("Foorilla(cybersecjobs): no csrftoken cookie — aborting")
                return []

            session_headers = {"X-CSRFToken": csrf_token, "HX-Request": "true"}

            topic_response = await client.post(
                f"{_BASE_URL}/topics/hiring/",
                data={"topic": _INFOSEC_TOPIC_ID},
                headers=session_headers,
            )
            topic_response.raise_for_status()

            region_response = await client.post(
                f"{_BASE_URL}/regions/hiring/",
                data={"remote_only": "on"},
                headers=session_headers,
            )
            region_response.raise_for_status()

            listing_response = await client.get(
                f"{_BASE_URL}/hiring/jobs/", headers={"HX-Request": "true"}
            )
            listing_response.raise_for_status()

        soup = BeautifulSoup(listing_response.text, "html.parser")
        items = soup.select("li.list-group-item")

        if not items:
            logger.warning(
                "Foorilla(cybersecjobs): no job items found — site structure may have changed"
            )
            return []

        jobs = []
        for item in items:
            try:
                link = item.select_one("a.stretched-link[hx-get^='/hiring/jobs/']")
                if not link:
                    continue

                title = link.get_text(strip=True)
                slug_path = link.get("hx-get", "")
                if not title or not slug_path:
                    continue

                jobs.append(
                    Job(
                        title=title,
                        company="",
                        location="Remote",
                        url=f"{_BASE_URL}{slug_path}",
                        source=JobSource.CYBERSECJOBS,
                        is_remote=True,
                    )
                )
            except Exception as exc:
                logger.warning("Foorilla(cybersecjobs): skipping malformed job item: %s", exc)
                continue

        logger.info("Foorilla(cybersecjobs): %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("CyberSecJobs scraper failed: %s", exc)
        return []
