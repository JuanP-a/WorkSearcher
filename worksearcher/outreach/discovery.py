import logging

import httpx

from worksearcher.config import Settings
from worksearcher.core.models import Company

logger = logging.getLogger(__name__)


def _build_query(lat: float, lon: float, radius_km: int, limit: int) -> str:
    radius_m = radius_km * 1000
    return (
        f"[out:json][timeout:60];"
        f'(node["website"](around:{radius_m},{lat},{lon});'
        f'way["website"](around:{radius_m},{lat},{lon}););'
        f"out center {limit};"
    )


async def discover_companies(config: Settings) -> list[Company]:
    """Discover businesses with a `website` tag near OUTREACH_LAT/LON via Overpass."""
    if config.OUTREACH_LAT is None or config.OUTREACH_LON is None:
        raise ValueError("OUTREACH_LAT and OUTREACH_LON must be set to run outreach discovery")

    query = _build_query(
        config.OUTREACH_LAT,
        config.OUTREACH_LON,
        config.OUTREACH_RADIUS_KM,
        config.OUTREACH_MAX_COMPANIES_PER_RUN,
    )

    try:
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(config.OUTREACH_OVERPASS_URL, data={"data": query})
            response.raise_for_status()
            payload = response.json()

        companies = []
        for element in payload.get("elements", []):
            try:
                tags = element.get("tags", {})
                name = tags.get("name")
                website = tags.get("website")
                if not name or not website:
                    continue

                center = element.get("center", {})
                latitude = element.get("lat", center.get("lat"))
                longitude = element.get("lon", center.get("lon"))
                if latitude is None or longitude is None:
                    continue

                companies.append(
                    Company(name=name, website=website, latitude=latitude, longitude=longitude)
                )
            except Exception as exc:
                logger.warning("Overpass: skipping malformed element: %s", exc)
                continue

        logger.info("Overpass: %d companies discovered", len(companies))
        return companies[: config.OUTREACH_MAX_COMPANIES_PER_RUN]

    except Exception as exc:
        logger.error("Overpass discovery failed: %s: %s", type(exc).__name__, exc)
        return []
