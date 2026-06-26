import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from worksearcher.config import Settings
from worksearcher.core.models import Job, JobSource

logger = logging.getLogger(__name__)

HIMALAYAS_API = "https://himalayas.app/jobs/api"


async def scrape(config: Settings) -> list[Job]:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "WorkSearcher/1.0"},
            timeout=config.HTTP_TIMEOUT_SECONDS,
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
                posted_at = None
                if pub_date is not None:
                    try:
                        # API returns RFC 2822 strings; fall back to Unix int for test fixtures
                        if isinstance(pub_date, (int, float)):
                            posted_at = datetime.fromtimestamp(pub_date, tz=UTC)
                        else:
                            posted_at = parsedate_to_datetime(str(pub_date))
                    except Exception:
                        pass

                currency = item.get("currency", "") or ""
                min_salary_raw = item.get("minSalary")
                salary_period = item.get("salaryPeriod", "") or ""
                min_salary_usd_monthly = None
                if currency == "USD" and min_salary_raw is not None:
                    if salary_period == "annual":
                        min_salary_usd_monthly = float(min_salary_raw) / 12
                    elif salary_period == "monthly":
                        min_salary_usd_monthly = float(min_salary_raw)
                    else:
                        logger.debug(
                            "Himalayas: unhandled salary period %r — skipping salary for %r",
                            salary_period,
                            item.get("title"),
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
                    min_salary_usd_monthly=min_salary_usd_monthly,
                )
                jobs.append(job)
            except Exception as exc:
                logger.warning(
                    "Himalayas: skipping malformed job %s: %s", item.get("title", "?"), exc
                )
                continue

        logger.info("Himalayas: %d jobs found", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("Himalayas scraper failed: %s", exc)
        return []
