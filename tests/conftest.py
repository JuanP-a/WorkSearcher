"""Shared test fixtures and helpers."""

import pytest


class FakeSettings:
    """Implements the full Settings interface so tests don't diverge when new fields are added."""

    META_PHONE_NUMBER_ID = "123456789"
    META_ACCESS_TOKEN = "fake_token"
    META_RECIPIENT_PHONE = "521234567890"
    META_API_VERSION = "v21.0"
    keywords_list = ["python", "backend", "cybersecurity"]
    MAX_YEARS_EXPERIENCE = 3
    MAX_JOB_AGE_DAYS = 30
    blacklist_list: list = []
    filter_languages_list: list = ["en", "es"]
    MIN_SALARY_USD_MONTHLY = None
    DB_PATH = "worksearcher.db"
    jobspy_terms_list = ["python", "cybersecurity"]
    enabled_scrapers_list = [
        "jobspy",
        "remoteok",
        "remotive",
        "wwr",
        "cybersecjobs",
        "computrabajo",
        "bumeran",
        "himalayas",
        "hackernews",
        "getonboard",
    ]
    bumeran_search_terms_list = ["desarrollador", "programador"]
    computrabajo_search_terms_list = ["desarrollador", "programador"]
    occ_search_terms_list = ["desarrollador", "programador"]
    getonboard_categories_list = ["programming", "cybersecurity", "sysadmin-devops-qa"]
    jobspy_sites_list = ["linkedin", "indeed", "glassdoor"]
    JOBSPY_RESULTS_WANTED = 50
    JOBSPY_HOURS_OLD = 24
    SEARCH_LOCATION = "Remote"
    HTTP_TIMEOUT_SECONDS = 30
    HIMALAYAS_RESULTS_LIMIT = 50
    MAX_JOBS_PER_MESSAGE = 10
    WHATSAPP_HTTP_TIMEOUT_SECONDS = 15
    SCRAPER_TIMEOUT_SECONDS = 120
    PLAYWRIGHT_PAGE_LOAD_TIMEOUT_MS = 30_000
    PLAYWRIGHT_SELECTOR_TIMEOUT_MS = 10_000
    SEARCH_LOCAL_ENABLED = False
    MX_SEARCH_CITY = ""
    MX_SEARCH_STATE = ""
    OUTREACH_LAT = 20.1
    OUTREACH_LON = -100.8
    OUTREACH_RADIUS_KM = 80
    OUTREACH_MAX_COMPANIES_PER_RUN = 100
    OUTREACH_MAX_COMPANIES_PER_MESSAGE = 30
    OUTREACH_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    outreach_contact_paths_list = [
        "/contacto",
        "/trabaja-con-nosotros",
        "/bolsa-de-trabajo",
        "/careers",
        "/rh",
    ]

    @property
    def local_location(self) -> str:
        parts = [
            p.strip().title() for p in (self.MX_SEARCH_CITY, self.MX_SEARCH_STATE) if p.strip()
        ]
        return ", ".join(parts) if parts else ""


@pytest.fixture
def fake_settings() -> FakeSettings:
    return FakeSettings()
