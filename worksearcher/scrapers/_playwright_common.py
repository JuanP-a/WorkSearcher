"""Shared Playwright helpers for the LatAm scrapers (bumeran, computrabajo, occ).

Extracted after the three scrapers were copy-pasted and silently diverged —
see refactor-017 spec for the code review findings that motivated this.
"""

_STEALTH_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-gpu",
    "--disable-dev-shm-usage",
]

_LINUX_CHROME_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def launch_stealth_browser(playwright):
    return playwright.chromium.launch(headless=True, args=_STEALTH_LAUNCH_ARGS)


def new_stealth_context(browser):
    context = browser.new_context(
        user_agent=_LINUX_CHROME_UA,
        viewport={"width": 1280, "height": 800},
        locale="es-MX",
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return context


def raise_if_blocked(page) -> None:
    if "403" in page.title() or "Forbidden" in page.title():
        raise RuntimeError("403 received — aborting")


def parse_title_and_company(raw_text: str) -> tuple[str, str]:
    """Parse (title, company) from a job card's inner_text.

    Assumes the title is the first line long enough to not be a badge/date
    artifact ("Nuevo", "Publicado hace 2 días", ...) and the company is the
    line immediately after it.
    """
    lines = [ln.strip() for ln in raw_text.split("\n") if ln.strip()]
    for i, line in enumerate(lines):
        if len(line) > 5 and not line.startswith("Publicado"):
            company = lines[i + 1] if i + 1 < len(lines) else ""
            return line, company
    return "", ""
