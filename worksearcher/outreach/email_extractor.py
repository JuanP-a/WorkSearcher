import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from worksearcher.config import Settings
from worksearcher.core.models import Company

logger = logging.getLogger(__name__)

_USER_AGENT = "WorkSearcher/1.0"

# Text near a mailto: link that suggests it belongs to HR rather than
# sales/support — regex mailto: alone mostly surfaces contacto@/ventas@.
_HR_CONTEXT_KEYWORDS = (
    "recursos humanos",
    "trabaja con nosotros",
    "bolsa de trabajo",
    "vacantes",
    "careers",
    "hr",
    "reclutamiento",
)


def _extract_mailto_candidates(html: str) -> list[tuple[str, str]]:
    """Return (email, lowercased surrounding text) pairs for each mailto: link."""
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not href.lower().startswith("mailto:"):
            continue
        email = href[len("mailto:") :].split("?")[0].strip()
        if not email:
            continue
        context = anchor.get_text(" ", strip=True)
        if anchor.parent is not None:
            # Only the parent's own text nodes, not descendant tags' text —
            # otherwise a sibling <a>'s label bleeds into this anchor's
            # context when both share a parent with no wrapping element
            # (common in loosely-structured small-business HTML).
            direct_text = " ".join(
                s.strip() for s in anchor.parent.find_all(string=True, recursive=False) if s.strip()
            )
            context += " " + direct_text
        candidates.append((email, context.lower()))
    return candidates


def _is_hr_context(context: str) -> bool:
    return any(keyword in context for keyword in _HR_CONTEXT_KEYWORDS)


async def _robots_allows(client: httpx.AsyncClient, base_url: str, path: str) -> bool:
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = await client.get(robots_url)
        if response.status_code >= 400:
            return True  # no robots.txt published — nothing to respect
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser.can_fetch(_USER_AGENT, urljoin(base_url + "/", path.lstrip("/")))
    except Exception as exc:
        logger.warning("Failed to fetch robots.txt for %s: %s — allowing crawl", base_url, exc)
        return True


async def extract_email(company: Company, config: Settings) -> Company:
    """Crawl the company's home page + configured contact paths for an RH email.

    Returns a copy of `company` with `email`/`email_is_hr_context` set, or
    `status="no_email_found"` if no mailto: link was found anywhere allowed.
    """
    base_url = company.website.rstrip("/")
    paths = ["", *config.outreach_contact_paths_list]
    fallback: tuple[str, bool] | None = None

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=config.HTTP_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as client:
        for path in paths:
            if not await _robots_allows(client, base_url, path):
                logger.info("robots.txt disallows %s%s — skipping", base_url, path)
                continue

            try:
                response = await client.get(f"{base_url}{path}")
                if response.status_code >= 400:
                    continue
                candidates = _extract_mailto_candidates(response.text)
            except Exception as exc:
                logger.warning("Failed to crawl %s%s: %s", base_url, path, exc)
                continue

            for email, context in candidates:
                if _is_hr_context(context):
                    return company.model_copy(
                        update={"email": email, "email_is_hr_context": True, "status": "pending"}
                    )
                if fallback is None:
                    fallback = (email, False)

    if fallback is not None:
        email, is_hr_context = fallback
        return company.model_copy(
            update={"email": email, "email_is_hr_context": is_hr_context, "status": "pending"}
        )

    return company.model_copy(update={"status": "no_email_found"})
