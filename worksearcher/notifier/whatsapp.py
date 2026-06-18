import httpx
import logging

from worksearcher.config import Settings
from worksearcher.core.models import Job

logger = logging.getLogger(__name__)

_META_API_URL = "https://graph.facebook.com/v18.0/{phone_id}/messages"
_MAX_JOBS_PER_MESSAGE = 10


def _build_message(jobs: list[Job]) -> str:
    lines = ["*WorkSearcher — nuevas ofertas:*\n"]
    for job in jobs[:_MAX_JOBS_PER_MESSAGE]:
        lines.append(f"• *{job.title}* @ {job.company}")
        lines.append(f"  [{job.source}] {job.url}\n")
    if len(jobs) > _MAX_JOBS_PER_MESSAGE:
        lines.append(f"_...y {len(jobs) - _MAX_JOBS_PER_MESSAGE} más guardadas en DB_")
    return "\n".join(lines)


async def send_digest(jobs: list[Job], config: Settings) -> None:
    if not jobs:
        return

    url = _META_API_URL.format(phone_id=config.META_PHONE_NUMBER_ID)
    headers = {
        "Authorization": f"Bearer {config.META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": config.META_RECIPIENT_PHONE,
        "type": "text",
        "text": {"body": _build_message(jobs)},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()

    logger.info("WhatsApp digest sent: %d jobs", len(jobs))
