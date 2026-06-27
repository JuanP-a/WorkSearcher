from typing import ClassVar

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    META_PHONE_NUMBER_ID: str
    META_ACCESS_TOKEN: str
    META_RECIPIENT_PHONE: str
    META_API_VERSION: str = "v21.0"

    # Post-scrape filter applied to ALL scrapers — broad, no limit
    SEARCH_KEYWORDS: str = (
        "python,javascript,typescript,react,node.js,"
        "frontend,backend,fullstack,software engineer,developer,web developer,"
        "cybersecurity,security engineer,SOC analyst,pentester,"
        "infosec,ethical hacker,red team,blue team,cloud security,"
        "devops,automation,SRE"
    )

    # Search query sent to LinkedIn/Indeed/Glassdoor via jobspy — max 5 terms
    JOBSPY_SEARCH_TERMS: str = "python,cybersecurity,software engineer,devops,javascript"

    _KNOWN_SCRAPERS: ClassVar[frozenset[str]] = frozenset(
        {
            "jobspy",
            "remoteok",
            "remotive",
            "wwr",
            "cybersecjobs",
            "computrabajo",
            "bumeran",
            "himalayas",
            "hackernews",
        }
    )

    ENABLED_SCRAPERS: str = (
        "jobspy,remoteok,remotive,wwr,cybersecjobs,computrabajo,bumeran,himalayas,hackernews"
    )

    # Spanish search terms for LatAm scrapers (Bumeran, Computrabajo)
    BUMERAN_SEARCH_TERMS: str = (
        "desarrollador,programador,backend,ciberseguridad,seguridad informatica"
    )
    COMPUTRABAJO_SEARCH_TERMS: str = (
        "desarrollador,programador,backend,ciberseguridad,seguridad informatica"
    )

    # jobspy (LinkedIn / Indeed / Glassdoor) tuning
    JOBSPY_SITES: str = "linkedin,indeed,glassdoor"
    JOBSPY_RESULTS_WANTED: int = 50
    JOBSPY_HOURS_OLD: int = 24
    SEARCH_LOCATION: str = "Remote"
    HTTP_TIMEOUT_SECONDS: int = 30
    HIMALAYAS_RESULTS_LIMIT: int = 50
    MAX_JOBS_PER_MESSAGE: int = 10
    SCRAPER_TIMEOUT_SECONDS: int = 120

    SCRAPE_INTERVAL_HOURS: int = 4
    MAX_YEARS_EXPERIENCE: int = 3

    MAX_JOB_AGE_DAYS: int = 30

    BLACKLIST_KEYWORDS: str = (
        "security clearance,active clearance,top secret,ts/sci,dod clearance,"
        "secret clearance,public trust,us citizens only,"
        "must be authorized to work in the us,us work authorization,"
        "must be a us citizen,green card required,"
        "sales executive,account executive,must relocate,relocation required,"
        "staffing agency,recruiting firm"
    )

    MIN_SALARY_USD_MONTHLY: int | None = None

    FILTER_LANGUAGES: str = "en,es"

    # Path to SQLite DB — override on VPS to keep DB outside repo
    DB_PATH: str = "worksearcher.db"

    @field_validator("MIN_SALARY_USD_MONTHLY", mode="before")
    @classmethod
    def allow_empty_salary(cls, v: object) -> object:
        if v == "":
            return None
        return v

    @field_validator("JOBSPY_SEARCH_TERMS")
    @classmethod
    def jobspy_terms_max_five(cls, v: str) -> str:
        terms = [t.strip() for t in v.split(",") if t.strip()]
        if len(terms) > 5:
            raise ValueError(f"JOBSPY_SEARCH_TERMS must have at most 5 terms, got {len(terms)}")
        return v

    @field_validator("ENABLED_SCRAPERS")
    @classmethod
    def validate_scraper_names(cls, v: str) -> str:
        names = {n.strip().lower() for n in v.split(",") if n.strip()}
        unknown = names - cls._KNOWN_SCRAPERS
        if unknown:
            raise ValueError(
                f"Unknown scrapers: {sorted(unknown)}. Known: {sorted(cls._KNOWN_SCRAPERS)}"
            )
        return v

    @property
    def keywords_list(self) -> list[str]:
        return [k.strip().lower() for k in self.SEARCH_KEYWORDS.split(",")]

    @property
    def jobspy_terms_list(self) -> list[str]:
        return [t.strip().lower() for t in self.JOBSPY_SEARCH_TERMS.split(",") if t.strip()]

    @property
    def enabled_scrapers_list(self) -> list[str]:
        return [n.strip().lower() for n in self.ENABLED_SCRAPERS.split(",") if n.strip()]

    @property
    def bumeran_search_terms_list(self) -> list[str]:
        return [t.strip().lower() for t in self.BUMERAN_SEARCH_TERMS.split(",") if t.strip()]

    @property
    def computrabajo_search_terms_list(self) -> list[str]:
        return [t.strip().lower() for t in self.COMPUTRABAJO_SEARCH_TERMS.split(",") if t.strip()]

    @property
    def jobspy_sites_list(self) -> list[str]:
        return [s.strip().lower() for s in self.JOBSPY_SITES.split(",") if s.strip()]

    @property
    def blacklist_list(self) -> list[str]:
        return [k.strip().lower() for k in self.BLACKLIST_KEYWORDS.split(",") if k.strip()]

    @property
    def filter_languages_list(self) -> list[str]:
        return [lang.strip().lower() for lang in self.FILTER_LANGUAGES.split(",") if lang.strip()]
