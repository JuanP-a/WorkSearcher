import asyncio
import logging
from collections.abc import Callable, Coroutine

import click

from worksearcher.config import Settings
from worksearcher.core.deduplicator import deduplicate
from worksearcher.core.filters import filter_jobs
from worksearcher.core.models import Job
from worksearcher.notifier.whatsapp import send_digest
from worksearcher.scrapers import (
    bumeran_scraper,
    computrabajo_scraper,
    cybersecjobs_scraper,
    jobspy_scraper,
    remoteok_scraper,
    remotive_scraper,
    wwr_scraper,
)
from worksearcher.storage.database import (
    get_connection,
    get_seen_fingerprints,
    get_unnotified_jobs,
    init_db,
    mark_jobs_notified,
    save_jobs,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

_SCRAPERS: list[Callable[[Settings], Coroutine[None, None, list[Job]]]] = [
    jobspy_scraper.scrape,
    remoteok_scraper.scrape,
    remotive_scraper.scrape,
    wwr_scraper.scrape,
    cybersecjobs_scraper.scrape,
    computrabajo_scraper.scrape,
    bumeran_scraper.scrape,
]


async def _run_pipeline(config: Settings) -> None:
    logger.info("Pipeline started")

    # Scrape all platforms concurrently
    results = await asyncio.gather(
        *[scraper(config) for scraper in _SCRAPERS],
        return_exceptions=True,
    )
    all_jobs: list[Job] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("Scraper failed: %s", result)
        else:
            all_jobs.extend(result)
    logger.info("Scraped: %d total jobs", len(all_jobs))

    # Filter by keywords + remote + experience cap
    relevant = filter_jobs(all_jobs, config.keywords_list, config.MAX_YEARS_EXPERIENCE)
    logger.info("Relevant: %d jobs after filters (keywords + experience ≤%dy)", len(relevant), config.MAX_YEARS_EXPERIENCE)

    # Dedup + persist + notify
    conn = get_connection()
    try:
        init_db(conn)

        # Retry any jobs saved but not notified in a previous failed run
        unnotified = get_unnotified_jobs(conn)
        if unnotified:
            logger.info("Retrying notification for %d jobs from previous failed run", len(unnotified))
            if await send_digest(unnotified, config):
                mark_jobs_notified([j.fingerprint for j in unnotified], conn)

        candidate_fps = [j.fingerprint for j in relevant]
        seen = get_seen_fingerprints(candidate_fps, conn)
        new_jobs = deduplicate(relevant, seen)
        logger.info("New (unseen): %d jobs", len(new_jobs))

        if new_jobs:
            inserted = save_jobs(new_jobs, conn)
            logger.info("Inserted %d jobs into DB", inserted)
            sent = await send_digest(new_jobs, config)
            if sent:
                mark_jobs_notified([j.fingerprint for j in new_jobs], conn)
            else:
                logger.warning("Notification failed — jobs saved in DB but WhatsApp not delivered")
        else:
            logger.info("No new jobs — skipping notification")
    finally:
        conn.close()

    logger.info("Pipeline complete")


@click.group()
def cli() -> None:
    pass


@cli.command()
def run() -> None:
    """Run the full job search pipeline."""
    config = Settings()
    asyncio.run(_run_pipeline(config))


if __name__ == "__main__":
    cli()
