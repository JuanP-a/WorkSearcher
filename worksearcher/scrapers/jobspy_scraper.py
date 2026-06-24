import asyncio
import logging
from datetime import UTC, datetime

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

_SOURCE_MAP: dict[str, JobSource] = {
    "linkedin": JobSource.LINKEDIN,
    "indeed": JobSource.INDEED,
    "glassdoor": JobSource.GLASSDOOR,
}


async def scrape(config: Settings) -> list[Job]:
    try:
        from jobspy import scrape_jobs  # import here — jobspy is slow to import

        def _blocking_scrape() -> list[Job]:
            results = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term=" OR ".join(config.jobspy_terms_list),
                location="Remote",
                results_wanted=50,
                hours_old=24,
                is_remote=True,
            )
            jobs = []
            for _, row in results.iterrows():
                try:
                    source_str = str(row.get("site", "")).lower()
                    source = _SOURCE_MAP.get(source_str)
                    if source is None:
                        logger.warning("jobspy: unknown source %r — skipping row", source_str)
                        continue
                    date_posted = row.get("date_posted")
                    posted_at = None
                    try:
                        if date_posted is not None:
                            posted_at = datetime(
                                date_posted.year,
                                date_posted.month,
                                date_posted.day,
                                tzinfo=UTC,
                            )
                    except Exception:
                        posted_at = None

                    job = Job(
                        title=str(row.get("title", "")),
                        company=str(row.get("company", "")),
                        location=str(row.get("location", "Remote")),
                        url=str(row.get("job_url", "")),
                        source=source,
                        is_remote=True,
                        description=str(row.get("description", "") or ""),
                        posted_at=posted_at,
                    )
                    jobs.append(job)
                except Exception as exc:
                    logger.warning("jobspy: skipping malformed row: %s", exc)
                    continue
            return jobs

        # jobspy uses requests (sync) internally — run in thread pool
        jobs = await asyncio.to_thread(_blocking_scrape)
        logger.info("jobspy: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("jobspy scraper failed: %s", exc)
        return []
