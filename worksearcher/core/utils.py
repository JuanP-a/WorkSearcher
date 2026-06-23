import re


def slugify(keyword: str) -> str:
    """Convert a keyword to a URL-safe slug (lowercase, spaces→dashes, no special chars)."""
    slug = keyword.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    return re.sub(r"\s+", "-", slug)
