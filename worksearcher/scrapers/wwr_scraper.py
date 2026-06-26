import logging
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import httpx

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

WWR_RSS_URL = "https://weworkremotely.com/remote-jobs.rss"


def _parse_title_and_company(raw: str) -> tuple[str, str]:
    """Parse 'Category: Job Title at Company' → (title, company)."""
    if ": " in raw:
        raw = raw.split(": ", 1)[1]
    if " at " in raw:
        parts = raw.rsplit(" at ", 1)
        return parts[0].strip(), parts[1].strip()
    return raw.strip(), ""


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "WorkSearcher/1.0"},
            timeout=config.HTTP_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(WWR_RSS_URL)
            response.raise_for_status()

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            logger.error("WWR: RSS parse error: %s", exc)
            return []

        channel = root.find("channel")
        if channel is None:
            logger.warning("WWR: no <channel> in RSS response")
            return []

        jobs = []
        for item in channel.findall("item"):
            try:
                title_raw = item.findtext("title", "")
                # <link> in RSS 2.0 is text between tags; fallback to <guid>
                link = item.findtext("link", "") or item.findtext("guid", "")
                description = item.findtext("description", "")
                pub_date_raw = item.findtext("pubDate", "")

                title, company = _parse_title_and_company(title_raw)
                if not title or not link:
                    continue

                posted_at = None
                if pub_date_raw:
                    try:
                        posted_at = parsedate_to_datetime(pub_date_raw)
                    except Exception:
                        pass

                jobs.append(
                    Job(
                        title=title,
                        company=company,
                        location="Remote",
                        url=link,
                        source=JobSource.WWR,
                        is_remote=True,
                        description=description,
                        posted_at=posted_at,
                    )
                )
            except Exception as exc:
                logger.warning("WWR: skipping malformed item: %s", exc)
                continue

        logger.info("WWR: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("WWR scraper failed: %s", exc)
        return []
