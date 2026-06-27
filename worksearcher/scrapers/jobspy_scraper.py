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
        from jobspy import scrape_jobs

        def _blocking_scrape(location: str, is_remote: bool) -> list[Job]:
            results = scrape_jobs(
                site_name=config.jobspy_sites_list,
                search_term=" OR ".join(config.jobspy_terms_list),
                location=location,
                results_wanted=config.JOBSPY_RESULTS_WANTED,
                hours_old=config.JOBSPY_HOURS_OLD,
                is_remote=is_remote,
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
                        is_remote=is_remote,
                        description=str(row.get("description", "") or ""),
                        posted_at=posted_at,
                    )
                    jobs.append(job)
                except Exception as exc:
                    logger.warning("jobspy: skipping malformed row: %s", exc)
                    continue
            return jobs

        all_jobs: list[Job] = []

        # Remote pass
        remote_jobs = await asyncio.to_thread(
            _blocking_scrape, config.SEARCH_LOCATION, True
        )
        all_jobs.extend(remote_jobs)
        logger.info("jobspy (remote): %d jobs found", len(remote_jobs))

        # Local pass — when SEARCH_LOCAL_ENABLED, also query with city location
        if config.SEARCH_LOCAL_ENABLED and config.local_location:
            local_jobs = await asyncio.to_thread(
                _blocking_scrape, config.local_location, False
            )
            all_jobs.extend(local_jobs)
            logger.info("jobspy (local): %d jobs found", len(local_jobs))

        return all_jobs

    except Exception as exc:
        logger.error("jobspy scraper failed: %s", exc)
        return []
