import asyncio
import logging
from collections.abc import Callable, Coroutine
from pathlib import Path

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
    getonboard_scraper,
    hackernews_scraper,
    himalayas_scraper,
    jobspy_scraper,
    occ_scraper,
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

_ALL_SCRAPERS: dict[str, Callable[[Settings], Coroutine[None, None, list[Job]]]] = {
    "jobspy": jobspy_scraper.scrape,
    "remoteok": remoteok_scraper.scrape,
    "remotive": remotive_scraper.scrape,
    "wwr": wwr_scraper.scrape,
    "cybersecjobs": cybersecjobs_scraper.scrape,
    "computrabajo": computrabajo_scraper.scrape,
    "bumeran": bumeran_scraper.scrape,
    "himalayas": himalayas_scraper.scrape,
    "hackernews": hackernews_scraper.scrape,
    "occ": occ_scraper.scrape,
    "getonboard": getonboard_scraper.scrape,
}


async def _run_pipeline(config: Settings) -> None:
    logger.info("Pipeline started")

    # Scrape all platforms concurrently — 120s cap per scraper prevents a hung
    # Playwright browser from blocking the pipeline until the next cron fires on top
    async def _scrape_with_timeout(
        scraper: Callable[[Settings], Coroutine[None, None, list[Job]]],
    ) -> list[Job]:
        try:
            return await asyncio.wait_for(scraper(config), timeout=config.SCRAPER_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.error(
                "Scraper %s timed out after %ds", scraper.__name__, config.SCRAPER_TIMEOUT_SECONDS
            )
            return []

    active_scrapers = [_ALL_SCRAPERS[name] for name in config.enabled_scrapers_list]
    results = await asyncio.gather(
        *[_scrape_with_timeout(scraper) for scraper in active_scrapers],
        return_exceptions=True,
    )
    all_jobs: list[Job] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("Scraper failed: %s", result)
        else:
            all_jobs.extend(result)
    logger.info("Scraped: %d total jobs", len(all_jobs))

    require_remote = not config.SEARCH_LOCAL_ENABLED
    relevant = filter_jobs(
        all_jobs,
        config.keywords_list,
        max_years_experience=config.MAX_YEARS_EXPERIENCE,
        max_job_age_days=config.MAX_JOB_AGE_DAYS,
        blacklist=config.blacklist_list,
        allowed_languages=config.filter_languages_list,
        min_salary_usd_monthly=config.MIN_SALARY_USD_MONTHLY,
        require_remote=require_remote,
    )
    logger.info(
        "Relevant: %d jobs after filters (keywords + experience + date + blacklist + language + salary)",
        len(relevant),
    )

    # Two scrapers (or two passes of the same scraper, e.g. jobspy remote+local)
    # can surface the identical posting. Neither copy is in the DB yet, so
    # deduplicate() below wouldn't catch it — collapse same-batch duplicates
    # here or the WhatsApp digest shows the job twice.
    relevant = list({j.fingerprint: j for j in relevant}.values())

    # Dedup + persist + notify
    conn = get_connection(Path(config.DB_PATH))
    try:
        init_db(conn)

        # Retry any jobs saved but not notified in a previous failed run
        unnotified = get_unnotified_jobs(conn)
        if unnotified:
            logger.info(
                "Retrying notification for %d jobs from previous failed run", len(unnotified)
            )
            if await send_digest(unnotified, config):
                mark_jobs_notified(
                    [j.fingerprint for j in unnotified[: config.MAX_JOBS_PER_MESSAGE]], conn
                )

        candidate_fps = [j.fingerprint for j in relevant]
        seen = get_seen_fingerprints(candidate_fps, conn)
        new_jobs = deduplicate(relevant, seen)
        logger.info("New (unseen): %d jobs", len(new_jobs))

        if new_jobs:
            inserted = save_jobs(new_jobs, conn)
            logger.info("Inserted %d jobs into DB", inserted)
            sent = await send_digest(new_jobs, config)
            if sent:
                mark_jobs_notified(
                    [j.fingerprint for j in new_jobs[: config.MAX_JOBS_PER_MESSAGE]], conn
                )
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
