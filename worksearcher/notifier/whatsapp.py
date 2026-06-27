import logging

import httpx

from worksearcher.config import Settings
from worksearcher.core.models import Job

logger = logging.getLogger(__name__)

_META_API_URL = "https://graph.facebook.com/{version}/{phone_id}/messages"


def _build_message(jobs: list[Job], max_jobs: int) -> str:
    lines = ["*WorkSearcher — nuevas ofertas:*\n"]
    for job in jobs[:max_jobs]:
        lines.append(f"• *{job.title}* @ {job.company}")
        lines.append(f"  [{job.source}] {job.url}\n")
    if len(jobs) > max_jobs:
        lines.append(f"_...y {len(jobs) - max_jobs} más guardadas en DB_")
    return "\n".join(lines)


async def send_digest(jobs: list[Job], config: Settings) -> bool:
    if not jobs:
        return False

    url = _META_API_URL.format(
        version=config.META_API_VERSION, phone_id=config.META_PHONE_NUMBER_ID
    )
    headers = {
        "Authorization": f"Bearer {config.META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": config.META_RECIPIENT_PHONE,
        "type": "text",
        "text": {"body": _build_message(jobs, config.MAX_JOBS_PER_MESSAGE)},
    }

    async with httpx.AsyncClient(
        timeout=config.WHATSAPP_HTTP_TIMEOUT_SECONDS, follow_redirects=False
    ) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info("WhatsApp digest sent: %d jobs", len(jobs))
            return True
        except httpx.HTTPStatusError as e:
            error_code = (
                e.response.json().get("error", {}).get("code") if e.response.content else None
            )
            logger.error("WhatsApp API error %s (code=%s)", e.response.status_code, error_code)
            return False
        except httpx.RequestError as e:
            logger.error("WhatsApp request failed: %s", e)
            return False
