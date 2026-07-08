import logging
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

# search_by_date, not search — /search ranks by text relevance, which can
# surface a years-old thread instead of the current month's (verified live:
# /search returned a March 2020 thread for this exact query).
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
HN_ITEMS_URL = "https://hn.algolia.com/api/v1/items/{thread_id}"


def _parse_hn_comment(text: str) -> tuple[str, str]:
    """Return (title, company) from HN job comment HTML.

    Pipe-delimited format: Company | Role | Location | REMOTE | ...
    Falls back to (full first line, "") if no pipe found.
    """
    plain = BeautifulSoup(text, "html.parser").get_text()
    first_line = plain.split("\n")[0].strip()
    parts = [p.strip() for p in first_line.split("|")]
    if len(parts) >= 2:
        return parts[1], parts[0]
    return first_line, ""


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "WorkSearcher/1.0"},
            timeout=config.HTTP_TIMEOUT_SECONDS,
        ) as client:
            search_resp = await client.get(
                HN_SEARCH_URL,
                params={
                    "query": "Ask HN: Who is hiring?",
                    "tags": "story,author_whoishiring",
                    "hitsPerPage": 1,
                },
            )
            search_resp.raise_for_status()
            hits = search_resp.json().get("hits", [])
            if not hits:
                logger.warning("HackerNews: no 'Who is hiring?' thread found")
                return []

            thread_id = hits[0]["objectID"]
            logger.info(
                "HackerNews: scraping thread %s — %s",
                thread_id,
                hits[0].get("title", ""),
            )

            items_resp = await client.get(HN_ITEMS_URL.format(thread_id=thread_id))
            items_resp.raise_for_status()
            thread = items_resp.json()

        jobs = []
        for child in thread.get("children", []):
            text = child.get("text")
            if not text:
                continue
            try:
                title, company = _parse_hn_comment(text)
                if not title:
                    continue
                job_id = child.get("id", "")
                created_at_i = child.get("created_at_i")
                posted_at = datetime.fromtimestamp(created_at_i, tz=UTC) if created_at_i else None
                plain_text = BeautifulSoup(text, "html.parser").get_text()
                is_remote = "REMOTE" in plain_text.upper()
                job = Job(
                    title=title,
                    company=company,
                    location="Remote" if is_remote else "On-site",
                    url=f"https://news.ycombinator.com/item?id={job_id}",
                    source=JobSource.HACKERNEWS,
                    is_remote=is_remote,
                    description=plain_text,
                    posted_at=posted_at,
                )
                jobs.append(job)
            except Exception as exc:
                logger.warning(
                    "HackerNews: skipping malformed comment %s: %s",
                    child.get("id", "?"),
                    exc,
                )
                continue

        logger.info("HackerNews: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("HackerNews scraper failed: %s", exc)
        return []
