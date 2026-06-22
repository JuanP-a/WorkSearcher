from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    META_PHONE_NUMBER_ID: str
    META_ACCESS_TOKEN: str
    META_RECIPIENT_PHONE: str

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

    SCRAPE_INTERVAL_HOURS: int = 4
    MAX_YEARS_EXPERIENCE: int = 3

    @field_validator("JOBSPY_SEARCH_TERMS")
    @classmethod
    def jobspy_terms_max_five(cls, v: str) -> str:
        terms = [t.strip() for t in v.split(",") if t.strip()]
        if len(terms) > 5:
            raise ValueError(f"JOBSPY_SEARCH_TERMS must have at most 5 terms, got {len(terms)}")
        return v

    @property
    def keywords_list(self) -> list[str]:
        return [k.strip().lower() for k in self.SEARCH_KEYWORDS.split(",")]

    @property
    def jobspy_terms_list(self) -> list[str]:
        return [t.strip().lower() for t in self.JOBSPY_SEARCH_TERMS.split(",") if t.strip()]
