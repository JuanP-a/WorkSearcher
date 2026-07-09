import asyncio
import logging
from pathlib import Path

from worksearcher.config import Settings
from worksearcher.core.models import Company
from worksearcher.notifier.whatsapp import send_outreach_digest
from worksearcher.outreach.discovery import discover_companies
from worksearcher.outreach.email_extractor import extract_email
from worksearcher.storage.database import (
    get_connection,
    get_seen_company_fingerprints,
    get_unnotified_companies,
    init_db,
    mark_companies_notified,
    save_companies,
)

logger = logging.getLogger(__name__)


async def _extract_all(companies: list[Company], config: Settings) -> list[Company]:
    results = await asyncio.gather(
        *[extract_email(c, config) for c in companies], return_exceptions=True
    )
    extracted = []
    for company, result in zip(companies, results, strict=True):
        if isinstance(result, Exception):
            logger.warning("Failed to extract email for %s: %s", company.website, result)
            continue
        extracted_company, is_relevant = result
        if not is_relevant:
            logger.info("Not relevant, discarding: %s", extracted_company.website)
            continue
        extracted.append(extracted_company)
    return extracted


async def run_outreach_pipeline(config: Settings) -> None:
    """Weekly pipeline: discover companies, extract RH email, notify (manual send by user)."""
    if config.OUTREACH_LAT is None or config.OUTREACH_LON is None:
        logger.error("OUTREACH_LAT/OUTREACH_LON not configured — skipping outreach pipeline")
        return

    logger.info("Outreach pipeline started")
    discovered = await discover_companies(config)
    logger.info("Discovered: %d companies", len(discovered))

    extracted = await _extract_all(discovered, config)
    # Two Overpass elements (e.g. a node and a way) can represent the same
    # business — collapse same-batch duplicates before persisting/notifying.
    extracted = list({c.fingerprint: c for c in extracted}.values())

    conn = get_connection(Path(config.DB_PATH))
    try:
        init_db(conn)

        unnotified = get_unnotified_companies(conn)
        if unnotified:
            logger.info("Retrying notification for %d companies from previous run", len(unnotified))
            if await send_outreach_digest(unnotified, config):
                mark_companies_notified(
                    [
                        c.fingerprint
                        for c in unnotified[: config.OUTREACH_MAX_COMPANIES_PER_MESSAGE]
                    ],
                    conn,
                )

        candidate_fps = [c.fingerprint for c in extracted]
        seen = get_seen_company_fingerprints(candidate_fps, conn)
        new_companies = [c for c in extracted if c.fingerprint not in seen]
        logger.info("New (unseen) companies: %d", len(new_companies))

        if not new_companies:
            logger.info("No new companies — skipping notification")
            return

        inserted = save_companies(new_companies, conn)
        logger.info("Inserted %d companies into DB", inserted)

        notifiable = [c for c in new_companies if c.email is not None]
        if not notifiable:
            logger.info("No notifiable companies (no email found) — skipping notification")
            return

        sent = await send_outreach_digest(notifiable, config)
        if sent:
            mark_companies_notified(
                [c.fingerprint for c in notifiable[: config.OUTREACH_MAX_COMPANIES_PER_MESSAGE]],
                conn,
            )
        else:
            logger.warning(
                "Outreach notification failed — companies saved but WhatsApp not delivered"
            )
    finally:
        conn.close()

    logger.info("Outreach pipeline complete")
